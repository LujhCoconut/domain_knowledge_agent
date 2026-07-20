# vLLM 源码分析

vLLM (Apache-2.0) 是一个高吞吐量 LLM 推理引擎，核心创新包括 PagedAttention、continuous batching、prefix caching。本文档关注 v1 引擎的调度器架构、KV connector 框架及其与外部 KV store 的交互机制。

> 分析版本：vLLM main 分支（2026-06），源码路径 `/home/ljh/vllm/`（远程开发机）

---

## Scheduler：Continuous Batching 的三队列模型

### 背景

`Scheduler`（`vllm/v1/core/sched/scheduler.py`）是推理引擎的核心调度器，每步决定哪些 request 参与 GPU forward、分配多少 tokens 和 KV cache blocks。

### 核心数据结构

源码 `scheduler.py:155-167`：

```python
class Scheduler:
    # ① 所有 request 的总仓库
    self.requests: dict[str, Request] = {}

    # ② 三层队列
    self.waiting = create_request_queue(self.policy)          # PriorityQueue
    self.skipped_waiting = create_request_queue(self.policy)  # PriorityQueue
    self.running: list[Request] = []                          # 普通 list

    # ③ 调度约束
    self.max_num_running_reqs = self.scheduler_config.max_num_seqs
    self.max_num_scheduled_tokens = (
        self.scheduler_config.max_num_scheduled_tokens
        if self.scheduler_config.max_num_scheduled_tokens
        else self.scheduler_config.max_num_batched_tokens
    )
```

**`running` 是 list 不是队列**——decode 阶段每个 RUNNING request 每步只生成 1 个 token，调度器按固定顺序遍历各分配 1 token+block，不需要挑选。

**`waiting` 和 `skipped_waiting` 是优先级队列**——prefill 需要大量 tokens 和 blocks，不能全体同时上，用优先级队列选出最应该被调度的一个来尝试。

### Request 状态机

源码 `vllm/v1/request.py:315-331`：

```python
class RequestStatus(enum.IntEnum):
    WAITING = enum.auto()
    WAITING_FOR_STRUCTURED_OUTPUT_GRAMMAR = enum.auto()
    WAITING_FOR_REMOTE_KVS = enum.auto()
    WAITING_FOR_STREAMING_REQ = enum.auto()
    RUNNING = enum.auto()
    PREEMPTED = enum.auto()
    FINISHED_STOPPED = enum.auto()
    FINISHED_LENGTH_CAPPED = enum.auto()
    FINISHED_ABORTED = enum.auto()
    FINISHED_IGNORED = enum.auto()
    FINISHED_ERROR = enum.auto()
    FINISHED_REPETITION = enum.auto()
```

状态迁移：

```
    WAITING  ←─────────────────────────── PREEMPTED
       │                                      ▲
       │ schedule() 中 allocate 通过后         │ _preempt_request():
       │ request.status = RUNNING              │   request.status = PREEMPTED
       ▼                                      │   num_computed_tokens = 0
    RUNNING ──────────────────────────────────┘   waiting.prepend_request(request)
       │
       │ 完成 / abort / error
       ▼
    FINISHED_STOPPED / FINISHED_ABORTED / FINISHED_ERROR / ...
```

源码 `scheduler.py:954-968`（`_preempt_request`）：

```python
assert request.status == RequestStatus.RUNNING
self.kv_cache_manager.free(request)
self.encoder_cache_manager.free(request)
request.status = RequestStatus.PREEMPTED
request.num_computed_tokens = 0
# ...
self.waiting.prepend_request(request)
```

被抢占的 request 放回 waiting 队列头部（`prepend` 而非 `append`），`num_computed_tokens` 重置为 0——下次 `schedule()` 会重新走 exists() 路径。

`WAITING_FOR_REMOTE_KVS`、`WAITING_FOR_STRUCTURED_OUTPUT_GRAMMAR`、`WAITING_FOR_STREAMING_REQ` 是 blocked 子状态，统一放在 `skipped_waiting` 队列中。

源码 `scheduler.py:1625-1632`：

```python
@staticmethod
def _is_blocked_waiting_status(status: RequestStatus) -> bool:
    return status in (
        RequestStatus.WAITING_FOR_STRUCTURED_OUTPUT_GRAMMAR,
        RequestStatus.WAITING_FOR_REMOTE_KVS,
        RequestStatus.WAITING_FOR_STREAMING_REQ,
    )
```

### schedule() 完整流程

源码 `scheduler.py:335-856`，核心结构：

```python
def schedule(self) -> SchedulerOutput:
    token_budget = self.max_num_scheduled_tokens

    # ═══ 阶段 1: 遍历 RUNNING requests（decode 阶段） ═══
    # scheduler.py:372-490
    req_index = 0
    while req_index < len(self.running) and token_budget > 0:
        request = self.running[req_index]
        num_new_tokens = (
            request.num_tokens_with_spec
            + request.num_output_placeholders
            - request.num_computed_tokens
        )
        # ... long_prefill_token_threshold clamp ...
        num_new_tokens = min(num_new_tokens, token_budget)
        # ... max_model_len clamp ...
        if num_new_tokens == 0:
            req_index += 1
            continue

        # 分配 slots（decode 阶段每次 1 block，几乎总成功）
        new_blocks = self.kv_cache_manager.allocate_slots(
            request, num_new_tokens, ...
        )
        if new_blocks is None:
            # 预占策略：preempt 最低优先级 request 或 pop 最后一个
            if self.policy == SchedulingPolicy.PRIORITY:
                preempted_req = max(self.running, key=...)
                self.running.remove(preempted_req)
            else:
                preempted_req = self.running.pop()
            self._preempt_request(preempted_req, ...)
            # 不立即 break，while 循环继续重试当前 request

    # ═══ 阶段 2: 从 waiting 中逐个尝试 prefill ═══
    # scheduler.py:554-842
    while (self.waiting or self.skipped_waiting) and token_budget > 0:
        if len(self.running) == self.max_num_running_reqs:
            break                                    # ← break

        request = request_queue.peek_request()

        # blocked status 检查
        if self._is_blocked_waiting_status(request.status) \
           and not self._try_promote_blocked_waiting_request(request):
            request_queue.pop_request()
            step_skipped_waiting.prepend_request(request)
            continue                                   # ← continue

        # max_loras 约束
        if (self.lora_config and request.lora_request and ...):
            request_queue.pop_request()
            step_skipped_waiting.prepend_request(request)
            continue                                   # ← continue

        # ── 2a. 缓存命中查询 ──
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
                    continue                           # ← continue
            num_computed_tokens = num_new_local + ext_tokens

        # ── 2b. 计算需要的新 token 数 ──
        num_new_tokens = request.num_tokens - num_computed_tokens

        # chunked prefill 未启用且 token 不够 → 中止
        if (not self.scheduler_config.enable_chunked_prefill
            and num_new_tokens > token_budget):
            break                                       # ← break

        num_new_tokens = min(num_new_tokens, token_budget)

        # encoder 调度
        if request.has_encoder_inputs:
            # ... 可能中途 num_new_tokens == 0 → break   # ← break

        # mamba block aligned split
        if self.need_mamba_block_aligned_split:
            num_new_tokens = self._mamba_block_aligned_split(...)
            if num_new_tokens == 0:
                break                                    # ← break

        # ── 2c. 分配 KV cache blocks ──
        new_blocks = self.kv_cache_manager.allocate_slots(
            request,
            num_new_tokens,
            num_new_computed_tokens=num_new_local_computed_tokens,
            new_computed_blocks=new_computed_blocks,
            num_external_computed_tokens=num_external_computed_tokens,
            full_sequence_must_fit=self.scheduler_reserve_full_isl,
        )
        if new_blocks is None:
            break                                        # ← ★ break

        # ── 2d. 成功 → 通知 connector + 移入 running ──
        if self.connector is not None:
            self.connector.update_state_after_alloc(
                request, ...,
                num_external_computed_tokens)

        request_queue.pop_request()
        request.num_computed_tokens = num_computed_tokens  # ★ 由此 guard 不再触发
        request.status = RequestStatus.RUNNING
        self.running.append(request)
```

### break vs continue 分类

源码中共 5 条 `break` 路径、3 条 `continue` 路径：

| 源码位置 | 退出原因 | 类型 | 影响 |
|----------|----------|------|------|
| L556 | `len(running) == max_num_running_reqs` | `break` | 退出整个 while |
| L568 | blocked waiting status 未解除 | `continue` | 仅跳过当前 request |
| L582 | `max_loras` 饱和 | `continue` | 仅跳过当前 request |
| L612 | `ext_tokens is None`（async lookup 未就绪） | `continue` | 仅跳过当前 request |
| L696 | `!enable_chunked_prefill && num_new_tokens > token_budget` | `break` | 退出整个 while |
| L712 | encoder 调度后 `num_new_tokens == 0` | `break` | 退出整个 while |
| L739 | mamba block split 后 `num_new_tokens == 0` | `break` | 退出整个 while |
| L760 | **`allocate_slots()` 返回 None** | `break` | 退出整个 while |

**`allocate_slots` 失败用 `break` 而非 `continue`**——block 池碎片化通常是系统性的，如果第一个 prefill 分配失败，下一个大概率也成不了。

**`continue` 的三条路径的共同点**：它们只与当前 request 的特定状态有关（blocked status、lora、async lookup），不影响其他 request 的可调度性。

---

## Step 的生命周期

### 定义

源码 `vllm/v1/engine/core.py:439-468`：

```python
def step(self) -> tuple[dict[int, EngineCoreOutputs], bool]:
    if not self.scheduler.has_requests():
        return {}, False
    scheduler_output = self.scheduler.schedule()
    future = self.model_executor.execute_model(scheduler_output, non_block=True)
    grammar_output = self.scheduler.get_grammar_bitmask(scheduler_output)
    with (...):
        model_output = future.result()
        if model_output is None:
            model_output = self.model_executor.sample_tokens(grammar_output)
    self._process_aborts_queue()
    engine_core_outputs = self.scheduler.update_from_output(
        scheduler_output, model_output)
    return engine_core_outputs, scheduler_output.total_num_scheduled_tokens > 0
```

**Step** = `schedule() → execute_model() → update_from_output()` 的完整一次循环。在 `run_busy_loop()`（`core.py:1214`）中无限循环。

### _update_after_schedule

源码 `scheduler.py:970-986`：

```python
def _update_after_schedule(self, scheduler_output: SchedulerOutput) -> None:
    num_scheduled_tokens = scheduler_output.num_scheduled_tokens
    for req_id, num_scheduled_token in num_scheduled_tokens.items():
        request = self.requests[req_id]
        request.num_computed_tokens += num_scheduled_token
        request.is_prefill_chunk = request.num_computed_tokens < (
            request.num_tokens + request.num_output_placeholders
        )
```

decode request 每步 `num_computed_tokens += 1`，prefill request 每步 `num_computed_tokens += num_new_tokens`。

---

## exists() → get() 间的时间窗口

### 窗口的根因： allocate_slots 反复失败 + guard 条件导致每步重复调用 exists()

**关键条件**：

1. 源码 `scheduler.py:596` —— `request.num_computed_tokens == 0` 是 `get_num_new_matched_tokens()`（即 exists）的 guard：

```python
if request.num_computed_tokens == 0:
    # ...
    if self.connector is not None:
        ext_tokens, load_kv_async = \
            self.connector.get_num_new_matched_tokens(...)
```

2. 源码 `scheduler.py:760` —— `allocate_slots()` 失败时 `break`，代码执行不到 `scheduler.py:817` 的赋值：

```python
if new_blocks is None:
    break           # ← 退出，下面几行不执行

# ...
request.num_computed_tokens = num_computed_tokens   # ← 这行执行不到
```

这两点组合产生了一个循环：`num_computed_tokens` 始终为 0 → 每步 guard 都满足 → 每步都调 `get_num_new_matched_tokens()`（exists） → 每步 allocate 都失败 → return。

```
Step 0:
  schedule():
    request.num_computed_tokens == 0  ← guard 满足
    connector.get_num_new_matched_tokens() → T0 时刻
    allocate_slots() → None → break
    # num_computed_tokens 仍然是 0

Step 1:
  schedule():
    request.num_computed_tokens == 0  ← guard 仍然满足
    connector.get_num_new_matched_tokens() → 再次调用
    allocate_slots() → None → break

...

Step K:
  schedule():
    connector.get_num_new_matched_tokens() → 第 K 次调用
    allocate_slots() → 成功 ✅
    request.num_computed_tokens = num_computed_tokens  ← 赋值

Step K+1:
  schedule():
    # num_computed_tokens > 0，guard 不再触发

  get_finished():
    # ReqMeta 入队到 kv_recv_thread，开始从 store 加载 KV
```

具体窗口长度取决于 `allocate_slots` 多少步后成功。——`full_sequence_must_fit` 约束下，大 prefill 需要一次性拿到所有 KV cache blocks，而 block 池的释放来自 running 中 decode request 的逐步完成，速率取决于并发度、output length 和 block 碎片化程度。

### 为什么 allocate_slots 可能多步都失败

`allocate_slots` 源码调用点 `scheduler.py:741-760`：

```python
new_blocks = self.kv_cache_manager.allocate_slots(
    request, num_new_tokens,
    full_sequence_must_fit=self.scheduler_reserve_full_isl,
)
```

`full_sequence_must_fit=True` 意味 prefill 必须一次性拿到全部 blocks，不允许部分分配。decode request 每次只需 1 block，几乎总成功。

---

## KV Connector 框架

### 角色分离

KV connector 分两个角色，运行在不同进程中。源码 `vllm/v1/core/sched/scheduler.py:117-127`：

```python
if self.vllm_config.kv_transfer_config is not None:
    self.connector = KVConnectorFactory.create_connector(
        config=self.vllm_config,
        role=KVConnectorRole.SCHEDULER,
        kv_cache_config=self.kv_cache_config,
    )
```

| 角色 | 进程 | 调用方法 |
|------|------|----------|
| `SCHEDULER` | Scheduler 进程 | `get_num_new_matched_tokens()`、`update_state_after_alloc()`、`build_connector_meta()` |
| `WORKER` | GPU Worker 进程 | `start_load_kv()`、`get_finished()`、`save_kv_layer()`、`wait_for_save()` |

Scheduler 和 Worker 通过 ZMQ IPC 通信。以 MooncakeStore 为例：

- Scheduler: `LookupKeyClient` → ZMQ REQ → Worker rank 0 的 `LookupKeyServer`
- 传输 `block_hashes`，返回 `hit_length`（外部 store 中已缓存的 token 数）

源码 `mooncake/store/worker.py:1390-1451`（`lookup` 方法）：

```python
def lookup(self, token_len: int, block_hashes: Sequence[BlockHash]) -> int:
    # 逐 group 构造 candidate keys
    candidate_keys: list[str] = []
    candidate_meta: list[tuple[int, bytes]] = []
    for g_idx, db in enumerate(self.token_dbs):
        group_hashes = self.coord.block_hashes_for_spec(block_hashes, spec)
        for chunk_id, h in enumerate(group_hashes):
            hash_hex = h.hex()
            for key_prefix in key_prefixes:
                candidate_keys.append(
                    PoolKey.build_key_string(key_prefix, hash_hex))
            candidate_meta.append((g_idx, bytes(h)))

    # 外部 store 查询
    res = self.store.batch_is_exist(candidate_keys)

    # 每个 (group, hash) 在所有 TP×PP rank 上都存在才算 hit
    exists_set = {
        (g_idx, hash_bytes)
        for i, (g_idx, hash_bytes) in enumerate(candidate_meta)
        if all(
            res[i * ranks_per_candidate + j] == 1
            for j in range(ranks_per_candidate))
    }
    _masks, hit_length = self.coord.find_longest_cache_hit(
        block_hashes, token_len, ExternalCachedBlockPool(exists_set))
    return hit_length
```

### 异步加载的两阶段设计

源码 `vllm/v1/worker/kv_connector_model_runner_mixin.py:78-103`：

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
            kv_connector.get_finished(             # ★ 收尾：入队新请求 + 检查完成
                scheduler_output.finished_req_ids))
        output.invalid_block_ids = kv_connector.get_block_ids_with_load_errors()
        output.kv_connector_stats = kv_connector.get_kv_connector_stats()
        output.kv_cache_events = kv_connector.get_kv_connector_kv_cache_events()
        output.kv_connector_worker_meta = kv_connector.build_connector_worker_meta()
        if not defer_finalize:
            kv_connector.clear_connector_metadata()
```

```python
# gpu_model_runner.py:4273
self.maybe_get_kv_connector_output(
    scheduler_output, defer_finalize=defer_kv_connector_finalize,
) as kv_connector_output,
    # GPU forward 在这个 context manager 的 yield 块内执行
```

**时序**：

```
Step K:
  schedule()                    ← 分配成功，build_connector_meta 包含新 request
  start_load_kv()               ← 对 MooncakeStore 是 no-op
  ════════ GPU forward ═══════  ← 本次不包含这个新 request
  get_finished()                ← ReqMeta 入队到 kv_recv_thread
    → 后台线程开始从 store 加载 KV → GPU memory

Step K+1:
  schedule()                    ← request 已在 running 中
  start_load_kv()
  ════════ GPU forward ═══════  ← ★ 这个 request 终于参与了
  get_finished()                ← 检查加载是否完成
```

**核心设计意图**：`get_finished()` 在 forward **之后**才将新 request 入队到后台加载线程，下一个 step 的 forward 才用到这些 KV 数据——实现了 GPU compute 和 data transfer 的 overlap。

---

### 关键源码位置

| 文件 | 行号 | 关键内容 |
|------|------|----------|
| `vllm/v1/core/sched/scheduler.py` | 64-167 | Scheduler `__init__`：队列初始化 |
| `vllm/v1/core/sched/scheduler.py` | 335-856 | `schedule()`：完整调度循环 |
| `vllm/v1/core/sched/scheduler.py` | 554-556 | WAITING while 入口 + max_num_running_reqs break |
| `vllm/v1/core/sched/scheduler.py` | 568-573 | blocked waiting status → continue |
| `vllm/v1/core/sched/scheduler.py` | 596-615 | `get_num_new_matched_tokens` 调用点（exists guard） |
| `vllm/v1/core/sched/scheduler.py` | 741-766 | `allocate_slots` + break |
| `vllm/v1/core/sched/scheduler.py` | 803-822 | 成功: `request.status = RUNNING` + `num_computed_tokens` 赋值 |
| `vllm/v1/core/sched/scheduler.py` | 954-968 | `_preempt_request` |
| `vllm/v1/core/sched/scheduler.py` | 970-986 | `_update_after_schedule` |
| `vllm/v1/core/sched/scheduler.py` | 1625-1648 | `_is_blocked_waiting_status` + `_select_waiting_queue_for_scheduling` |
| `vllm/v1/engine/core.py` | 439-468 | `step()` |
| `vllm/v1/worker/kv_connector_model_runner_mixin.py` | 78-103 | `_get_kv_connector_output` context manager |
| `vllm/v1/request.py` | 315-331 | `RequestStatus` 枚举 |
| ` .../mooncake/store/scheduler.py` | 74-170 | `get_num_new_matched_tokens` → `lookup` |
| ` .../mooncake/store/worker.py` | 510-660 | `KVCacheStoreSendingThread._handle_request`（save + exists） |
| ` .../mooncake/store/worker.py` | 759-858 | `KVCacheStoreRecvingThread._handle_request`（load/get） |
| ` .../mooncake/store/worker.py` | 1390-1451 | `MooncakeStoreWorker.lookup`（exists for external cache hit） |
