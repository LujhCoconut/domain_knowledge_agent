# vLLM Worker / GPU Model Runner 源码分析

GPU worker 侧的执行流程：model runner 的 forward pass、KV connector 集成、batch_get 数据加载。

> 源码路径：
> - `vllm/v1/worker/gpu_model_runner.py`（7529 行）
> - `vllm/v1/worker/kv_connector_model_runner_mixin.py`
> - 远程开发机：`/home/ljh/vllm/`

---

## execute_model 流程

`gpu_model_runner.py:4034-4070`——`execute_model` 入口，接收 `SchedulerOutput`：

```python
kv_connector_metadata = scheduler_output.kv_connector_metadata
assert kv_connector_metadata is not None
get_kv_transfer_group().handle_preemptions(kv_connector_metadata)
```

`gpu_model_runner.py:4273-4276`——KV connector output 的 context manager 嵌套在 forward 外层：

```python
self.maybe_get_kv_connector_output(
    scheduler_output,
    defer_finalize=defer_kv_connector_finalize,
) as kv_connector_output,
    # GPU forward 在 context manager 的 yield 块内执行
```

`gpu_model_runner.py:4356`——执行完成后保存 output：

```python
self.kv_connector_output = kv_connector_output
```

`gpu_model_runner.py:4544`——spec decode 场景下延迟 finalize：

```python
if defer_kv_connector_finalize:
    self.finalize_kv_connector()
```

---

## KV connector 与 forward pass 的时序关系

`mixin.py:78-103`（`_get_kv_connector_output`）：

```python
@contextmanager
def _get_kv_connector_output(scheduler_output, ...):
    kv_connector.bind_connector_metadata(scheduler_output.kv_connector_metadata)
    kv_connector.start_load_kv(get_forward_context())
    try:
        yield output             # ★ GPU forward 在这里执行
    finally:
        kv_connector.wait_for_save()
        output.finished_sending, output.finished_recving = (
            kv_connector.get_finished(scheduler_output.finished_req_ids))
        output.invalid_block_ids = kv_connector.get_block_ids_with_load_errors()
        output.kv_connector_stats = kv_connector.get_kv_connector_stats()
        output.kv_cache_events = kv_connector.get_kv_connector_kv_cache_events()
        output.kv_connector_worker_meta = kv_connector.build_connector_worker_meta()
        kv_connector.clear_connector_metadata()
```

**`start_load_kv` 先于 forward 调用**：某些 connector（如 NIXL）在此发起 RDMA 读，然后 GPU kernel 等待数据到达。MooncakeStore 的 `start_load_kv` 是 no-op——它依赖后台线程的异步加载。

**`get_finished` 在 forward 之后 (finally)**：
- 对**已有**请求：检查后台加载线程是否完成（`finished_recving` 集合）
- 对**新**请求：将本步 build 的 `ReqMeta` 入队到后台线程，开始加载

`gpu_model_runner.py:4549-4560`——将 KV connector output 打包到 `ModelRunnerOutput`：

```python
kv_connector_output = self.kv_connector_output
self.kv_connector_output = None
# ...
return ModelRunnerOutput(..., kv_connector_output=kv_connector_output)
```

---

## Scheduler 侧回到 update_from_output

`scheduler.py:1313-1336`——Model runner 返回后处理 KV connector 的结果：

```python
kv_connector_output = model_runner_output.kv_connector_output
# ...
if kv_connector_stats and self.connector:
    kv_stats = self.connector.get_kv_connector_stats()
    kv_connector_stats = kv_connector_stats.aggregate(kv_stats)

if kv_connector_output and kv_connector_output.invalid_block_ids:
    # 处理 load 失败的 blocks，标记对应 request 需要重算
```

`scheduler.py:2165-2189`（`_update_from_kv_xfer_finished`）——更新 request 状态：

```python
def _update_from_kv_xfer_finished(self, kv_connector_output: KVConnectorOutput):
    self.connector.update_connector_output(kv_connector_output)

    for req_id in kv_connector_output.finished_recving or ():
        # request 的 KV 加载完成，可以继续 decode
        ...

    for req_id in kv_connector_output.finished_sending or ():
        # request 的 KV 保存完成，可以释放 blocks
        ...
```

---

## MooncakeStore 的后台加载

### KVCacheStoreRecvingThread

`mooncake/store/worker.py:713-858`——加载线程的 `_handle_request`：

```python
class KVCacheStoreRecvingThread(KVTransferThread):
    def _handle_request(self, req_meta: ReqMeta):
        load_spec = req_meta.load_spec
        if load_spec is None or not load_spec.can_load:
            return

        # 计算需要加载的 token 范围
        token_len = load_spec.kvpool_cached_tokens
        # ... 构造 keys + 目标 GPU 地址 ...

        res = self.store.batch_get_into_multi_buffers(
            keys, addrs, sizes,
        )
        # 加载失败时记录 block IDs → scheduler 后续标记重算
```

### KVCacheStoreSendingThread

`mooncake/store/worker.py:437-660`——保存线程的 `_handle_request`：

```python
class KVCacheStoreSendingThread(KVTransferThread):
    def _handle_request(self, req_meta: ReqMeta):
        # 1. 计算 store_mask（per-group reachable mask）
        store_masks = self.coord.store_mask(token_len, ...)

        # 2. 构造 keys（PoolKey）+ addresses（GPU memory）
        for g_idx, db in enumerate(self.token_databases):
            for chunk_idx, (start, end, key) in \
                enumerate(db.process_tokens(token_len, req_meta.block_hashes)):
                # ... 按 mask 过滤 + TP striding ...

        # 3. Dedup：batch_is_exist 检查哪些 key 已存在
        exists_states = self.store.batch_is_exist(keys)

        # 4. 写入 store
        res = self.store.batch_put_from_multi_buffers(
            keys, addrs, sizes, self.replicate_config,
        )
```

`worker.py:576`——save 路径的 `batch_is_exist` 调用（dedup），未传 `ExistOptions`：

```python
exists_states = self.store.batch_is_exist(keys)
```

---

## MooncakeStore Worker 初始化

`mooncake/store/worker.py:920-1011`——`MooncakeStoreWorker.__init__`：

```python
class MooncakeStoreWorker:
    def __init__(self, vllm_config: VllmConfig, kv_cache_config: KVCacheConfig):
        # 加载 mooncake.json 配置
        store_config = MooncakeStoreConfig.load_from_config()
        self.store = MooncakeDistributedStore()
        ret = self.store.setup(...)          # 连接 master、transfer engine

        # 创建 token database（每个 attention group 一个）
        self.token_databases = [...]         # ChunkedTokenDatabase

        # 创建后台传输线程
        self.kv_send_thread = KVCacheStoreSendingThread(...)
        self.kv_recv_thread = KVCacheStoreRecvingThread(...)
        self.kv_send_thread.start()
        self.kv_recv_thread.start()

        # 启动 lookup server（ZMQ IPC，供 scheduler 调用）
        if tp_rank == 0:
            self.lookup_server = LookupKeyServer(self, vllm_config)
```

---

## 源码位置汇总

| 文件 | 行号 | 内容 |
|------|------|------|
| `vllm/v1/worker/gpu_model_runner.py` | 4034-4070 | `execute_model` 入口 + connector metadata |
| `vllm/v1/worker/gpu_model_runner.py` | 4273-4276 | `maybe_get_kv_connector_output` 调用 |
| `vllm/v1/worker/gpu_model_runner.py` | 4544-4560 | 延迟 finalize + 打包 ModelRunnerOutput |
| `vllm/v1/worker/kv_connector_model_runner_mixin.py` | 43-47 | `kv_connector_no_forward` |
| `vllm/v1/worker/kv_connector_model_runner_mixin.py` | 51-103 | `maybe_get_kv_connector_output` + `_get_kv_connector_output` |
| `vllm/v1/worker/kv_connector_model_runner_mixin.py` | 64-71 | `finalize_kv_connector` |
| `vllm/v1/core/sched/scheduler.py` | 1313-1336 | `update_from_output` 中处理 KV connector |
| `vllm/v1/core/sched/scheduler.py` | 2165-2189 | `_update_from_kv_xfer_finished` |
| `.../mooncake/store/worker.py` | 350-430 | `KVTransferThread` 基类 |
| `.../mooncake/store/worker.py` | 437-660 | `KVCacheStoreSendingThread`（save/dedup/exists） |
| `.../mooncake/store/worker.py` | 713-858 | `KVCacheStoreRecvingThread`（load/batch_get） |
| `.../mooncake/store/worker.py` | 920-1011 | `MooncakeStoreWorker.__init__` |
