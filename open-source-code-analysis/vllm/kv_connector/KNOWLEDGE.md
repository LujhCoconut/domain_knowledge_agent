# vLLM KV Connector 源码分析

KV connector 框架是 vLLM 与外部 KV store（Mooncake、NIXL、LMCache 等）的接口层，负责将外部存储的 KV cache 集成到 vLLM 的调度和加载流程中。

> 源码路径：`vllm/distributed/kv_transfer/kv_connector/v1/`、`vllm/v1/worker/kv_connector_model_runner_mixin.py`、MooncakeStore 实现于 `.../mooncake/store/`

## 子主题

| 主题 | 关键词 | 技术点 | 关键源码 |
|------|--------|--------|----------|
| 角色分离 | KV connector, scheduler, worker | role separation (SCHEDULER/WORKER), ZMQ REQ/REP IPC | `scheduler.py:117-127` |
| Scheduler 侧 exists 调用链 | MooncakeStore, lookup | ZMQ lookup, batch_is_exist, cross-TP-rank consistency | `mooncake/store/worker.py:1390-1451` |
| Worker 侧异步加载 | async loading, background thread | get_finished deferred enqueue, compute-transfer overlap | `kv_connector_model_runner_mixin.py:78-103` |
| exists→get 窗口 | scheduler, KV connector | guard re-trigger, full_sequence_must_fit, allocate_slots break | `scheduler.py:596-615`, `scheduler.py:741-766` |

---

## 角色分离

KV connector 分两个角色，运行在不同进程中。

`vllm/v1/core/sched/scheduler.py:117-127`（Scheduler 侧创建）：

```python
if self.vllm_config.kv_transfer_config is not None:
    self.connector = KVConnectorFactory.create_connector(
        config=self.vllm_config,
        role=KVConnectorRole.SCHEDULER,
        kv_cache_config=self.kv_cache_config,
    )
```

| 角色 | 进程 | 定义的接口方法 |
|------|------|---------------|
| `SCHEDULER` | Scheduler 进程 | `get_num_new_matched_tokens()`、`update_state_after_alloc()`、`build_connector_meta()` |
| `WORKER` | GPU Worker 进程 | `start_load_kv()`、`get_finished()`、`save_kv_layer()`、`wait_for_save()` |

---

## Scheduler 侧：exists() 调用链

### 入口：get_num_new_matched_tokens

`scheduler.py:596-615`——在 `schedule()` 的 prefill 阶段，`request.num_computed_tokens == 0` 条件满足时调用：

```python
if request.num_computed_tokens == 0:           # ★ guard
    new_computed_blocks, num_new_local = \
        self.kv_cache_manager.get_computed_blocks(request)
    if self.connector is not None:
        ext_tokens, load_kv_async = \
            self.connector.get_num_new_matched_tokens(
                request, num_new_local_computed_tokens)
        if ext_tokens is None:                 # async lookup 未就绪
            request_queue.pop_request()
            step_skipped_waiting.prepend_request(request)
            continue                           # ← continue，下步重试
    num_computed_tokens = num_new_local + ext_tokens
```

`ext_tokens is None` 时 `continue`（非 `break`），意为"这个 request 的 async lookup 还没返回，跳过它处理下一个，下步再试"。这对其他 waiting request 没有影响。

### MooncakeStore Scheduler 实现

`mooncake/store/scheduler.py:74-170`——`get_num_new_matched_tokens`：

```python
def get_num_new_matched_tokens(
    self, request: Request, num_computed_tokens: int,
) -> tuple[int | None, bool]:
    token_len = request.num_tokens // self._block_size * self._block_size
    if token_len < self._block_size:
        return 0, False

    num_external_hit_tokens = self.client.lookup(
        request.request_id, token_len, request.block_hashes,
        non_block=self.lookup_async,
    )
    if num_external_hit_tokens is None:
        return None, False            # async lookup in flight → 下步重试

    # ...
    need_to_allocate = num_external_hit_tokens - num_computed_tokens
    return need_to_allocate, self.load_async
```

### Scheduler → Worker 通信：ZMQ IPC

Scheduler 的 `LookupKeyClient` → ZMQ REQ → Worker rank 0 的 `LookupKeyServer`。

`mooncake/store/worker.py:1490-1530`——`LookupKeyServer`：

```python
class LookupKeyServer:
    def __init__(self, store_worker: MooncakeStoreWorker, vllm_config: VllmConfig):
        socket_path = get_zmq_rpc_path_lookup(vllm_config)
        # ...
```

`worker.py:1390-1451`——`lookup` 方法（ZMQ 请求的实际处理）：

```python
def lookup(self, token_len: int, block_hashes: Sequence[BlockHash]) -> int:
    candidate_keys: list[str] = []
    candidate_meta: list[tuple[int, bytes]] = []
    for g_idx, db in enumerate(self.token_dbs):
        group_hashes = self.coord.block_hashes_for_spec(block_hashes, spec)
        for chunk_id, h in enumerate(group_hashes):
            for key_prefix in key_prefixes:
                candidate_keys.append(PoolKey.build_key_string(key_prefix, hash_hex))
            candidate_meta.append((g_idx, bytes(h)))

    res = self.store.batch_is_exist(candidate_keys)

    # 每个 (group, hash) 在所有 TP×PP rank 上都存在才算 hit
    ranks_per_candidate = self._lookup_expected_per_key
    exists_set = {
        (g_idx, hash_bytes)
        for i, (g_idx, hash_bytes) in enumerate(candidate_meta)
        if all(res[i * ranks_per_candidate + j] == 1
               for j in range(ranks_per_candidate))
    }
    _masks, hit_length = self.coord.find_longest_cache_hit(
        block_hashes, token_len, ExternalCachedBlockPool(exists_set))
    return hit_length
```

**关键**：`all(res[i * ranks_per_candidate + j] == 1 for j in range(ranks_per_candidate))`——一个 (group, hash) 只有在**所有 TP×PP rank 上都存在**才算外部缓存命中。这避免了跨 rank 不一致导致的 partial load。

### update_state_after_alloc

`scheduler.py:766-780`——`allocate_slots` 成功后通知 connector：

```python
if self.connector is not None:
    self.connector.update_state_after_alloc(
        request,
        self.kv_cache_manager.get_blocks(request_id),
        num_external_computed_tokens,
    )
```

`mooncake/store/scheduler.py:120-150`——具体实现：将 load_spec 标记为 `can_load=True`，这样 `build_connector_meta` 时才会生成包含 `load_spec` 的 `ReqMeta`。

---

## Worker 侧：异步加载的两阶段设计

### _get_kv_connector_output context manager

`vllm/v1/worker/kv_connector_model_runner_mixin.py:78-103`：

```python
@contextmanager
def _get_kv_connector_output(
    scheduler_output: "SchedulerOutput",
    wait_for_save: bool = True,
    defer_finalize: bool = False,
) -> Generator[KVConnectorOutput, None, None]:
    output = KVConnectorOutput()
    kv_connector = get_kv_transfer_group()
    kv_connector.bind_connector_metadata(scheduler_output.kv_connector_metadata)
    kv_connector.start_load_kv(get_forward_context())
    try:
        yield output                               # ★ GPU forward 在这里执行
    finally:
        if wait_for_save and not defer_finalize:
            kv_connector.wait_for_save()
        output.finished_sending, output.finished_recving = (
            kv_connector.get_finished(             # ← 收尾
                scheduler_output.finished_req_ids))
        output.invalid_block_ids = kv_connector.get_block_ids_with_load_errors()
        # ...
```

### 为什么 get_finished 在 finally 中

GPU forward 在 `yield output` 期间异步执行。`get_finished()` 放在 `finally` 块中，在 forward 完成后调用。

时序：

```
Step K:
  schedule()                        ← allocate 成功，build_connector_meta 包含新 request
  start_load_kv()                   ← MooncakeStore 是 no-op
  ════════ GPU forward ═══════     ← 本次不包含这个新 request
  get_finished()                    ← ReqMeta 入队到 kv_recv_thread
    → 后台线程从 store → GPU memory

Step K+1:
  schedule()                        ← request 已在 running 中
  ════════ GPU forward ═══════     ← ★ 这个 request 参与 forward
  get_finished()                    ← 检查加载完成
```

**设计意图**：被调度的 request 不在当前 step 参与 forward。`get_finished()` 在 forward 之后才将新 request 的 `ReqMeta` 入队，下一个 step 的 forward 才用到——GPU compute 和 data transfer 实现 overlap。

### MooncakeStore 的 get_finished

`mooncake/store/connector.py`（MooncakeStoreConnector）：

```python
def get_finished(self, finished_req_ids: set[str]):
    metadata = self._get_connector_metadata()
    return self.connector_worker.get_finished(finished_req_ids, metadata)
```

`mooncake/store/worker.py:1266-1325`——`MooncakeStoreWorker.get_finished`：
- 处理 preemption：`kv_send_thread.delete_finished_stored_request(req_id)`
- 收集已完成 store 的请求：`kv_send_thread.get_and_clear_finished_requests()`
- 将新 `ReqMeta` 入队到 `kv_recv_thread.add_request(req_meta)`

### 后台线程模型

`mooncake/store/worker.py:350-430`——基类 `KVTransferThread(threading.Thread)`：

```python
class KVTransferThread(threading.Thread):
    def __init__(self, ...):
        self.request_queue: queue.Queue[ReqMeta] = queue.Queue()
        self.stored_requests: dict[str, int] = {}   # req_id → 剩余还需完成的 job 数
```

两个子类：
- `KVCacheStoreSendingThread`（`worker.py:437`）：save 路径，将 GPU KV cache → Mooncake Store
- `KVCacheStoreRecvingThread`（`worker.py:713`）：load 路径，从 Mooncake Store → GPU memory

---

## exists() → get() 间的窗口

### 根因

`num_computed_tokens` 只在 `allocate_slots` 成功后赋值（`scheduler.py:817`），成功前的每一步 guard `request.num_computed_tokens == 0` 都满足，`get_num_new_matched_tokens()` 每步重复调用。

```
Step 0:
  request.num_computed_tokens == 0 → guard 满足
  get_num_new_matched_tokens() → T0 时刻
  allocate_slots() → None → break
  # num_computed_tokens 仍然是 0

Step 1:
  request.num_computed_tokens == 0 → guard 仍然满足
  get_num_new_matched_tokens() → 再次调用
  allocate_slots() → None → break

...

Step K:
  get_num_new_matched_tokens() → 第 K 次调用
  allocate_slots() → 成功 ✅
  request.num_computed_tokens = num_computed_tokens ← 赋值，guard 不再触发
```

窗口长度取决于 `allocate_slots` 的 `full_sequence_must_fit` 约束下、大 prefill 需要多步 block 累积才能成功。

---

## 源码位置汇总

| 文件 | 行号 | 内容 |
|------|------|------|
| `vllm/v1/core/sched/scheduler.py` | 117-127 | Scheduler 侧 connector 创建 |
| `vllm/v1/core/sched/scheduler.py` | 596-615 | `get_num_new_matched_tokens` 调用点（exists） |
| `vllm/v1/core/sched/scheduler.py` | 766-780 | `update_state_after_alloc` 调用点 |
| `vllm/v1/core/sched/scheduler.py` | 929-930 | `build_connector_meta` 调用点 |
| `vllm/v1/worker/kv_connector_model_runner_mixin.py` | 78-103 | `_get_kv_connector_output` context manager |
| `vllm/v1/worker/kv_connector_model_runner_mixin.py` | 64-71 | `finalize_kv_connector` |
| `.../mooncake/store/scheduler.py` | 74-170 | `get_num_new_matched_tokens` |
| `.../mooncake/store/scheduler.py` | 120-150 | `update_state_after_alloc` |
| `.../mooncake/store/scheduler.py` | 166-260 | `build_connector_meta` |
| `.../mooncake/store/worker.py` | 350-430 | `KVTransferThread` 基类 |
| `.../mooncake/store/worker.py` | 437-510 | `KVCacheStoreSendingThread` |
| `.../mooncake/store/worker.py` | 713-858 | `KVCacheStoreRecvingThread` |
| `.../mooncake/store/worker.py` | 1266-1325 | `get_finished` |
| `.../mooncake/store/worker.py` | 1390-1451 | `lookup`（exists 实际执行） |
| `.../mooncake/store/worker.py` | 1490-1530 | `LookupKeyServer` |
| `.../mooncake/store/connector.py` | — | `MooncakeStoreConnector`（调度器+worker 统一入口） |
