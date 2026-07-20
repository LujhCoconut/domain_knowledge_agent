# vLLM Scheduler 源码分析

Continuous batching 调度器，控制哪些 request 参与每步 GPU forward、分配多少 tokens 和 KV cache blocks。

> 源码路径：`vllm/v1/core/sched/scheduler.py`（2366 行），远程开发机 `/home/ljh/vllm/`

## 子主题

| 主题 | 关键词 | 技术点 | 关键源码 |
|------|--------|--------|----------|
| 三队列模型 | scheduler, continuous batching, KV cache | three-queue scheduling, break-vs-continue guard, num_computed_tokens guard re-trigger | `scheduler.py:64-167` `__init__` |
| schedule() 退出路径 | prefill, block allocation | allocate_slots preemption, WAITING_FOR_REMOTE_KVS blocked state | `scheduler.py:335-856` `schedule()` |
| Step 生命周期 | engine, forward pass, GPU | busy loop stepping, non_block execute_model, update_from_output state machine | `core.py:439-468` `step()` |
| exists→get 时间窗口 | scheduler, KV connector, cache hit | guard re-trigger on allocate failure, full_sequence_must_fit | `scheduler.py:596-615`, `scheduler.py:741-766` |

---

## 三队列模型

### 数据结构

`scheduler.py:155-167`：

```python
class Scheduler:
    self.requests: dict[str, Request] = {}                     # 所有 request 的总仓库

    self.waiting = create_request_queue(self.policy)           # PriorityQueue
    self.skipped_waiting = create_request_queue(self.policy)   # PriorityQueue
    self.running: list[Request] = []                           # 普通 list
```

`scheduler.py:103-107` — 调度约束：

```python
self.max_num_running_reqs = self.scheduler_config.max_num_seqs
self.max_num_scheduled_tokens = (
    self.scheduler_config.max_num_scheduled_tokens
    if self.scheduler_config.max_num_scheduled_tokens
    else self.scheduler_config.max_num_batched_tokens
)
```

- **`running` 是 list**：decode 阶段每个 RUNNING request 每步只生成 1 token，按固定顺序遍历即可
- **`waiting` 和 `skipped_waiting` 是 PriorityQueue**：prefill 需大量 tokens/blocks，不能同时调度，用优先级队列选最该调度的那个

### Request 状态机

`vllm/v1/request.py:315-331`：

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

`request.py:338` — `is_finished(status)` 判定：`status > RequestStatus.PREEMPTED`。

状态迁移：

```
WAITING  ←─────────────────────────── PREEMPTED
   │                                      ▲
   │ allocate 通过后                      │ _preempt_request():
   │ request.status = RUNNING             │   request.status = PREEMPTED
   ▼                                      │   num_computed_tokens = 0
RUNNING ──────────────────────────────────┘   waiting.prepend_request(request)
   │
   │ 完成 / abort / error
   ▼
FINISHED_*
```

`scheduler.py:954-968`（`_preempt_request`）：

```python
assert request.status == RequestStatus.RUNNING
self.kv_cache_manager.free(request)
self.encoder_cache_manager.free(request)
request.status = RequestStatus.PREEMPTED
request.num_computed_tokens = 0
# ...
self.waiting.prepend_request(request)
```

被抢占的 request 放回 waiting 头部（`prepend` 而非 `append`），`num_computed_tokens` 重置为 0。

### Blocked waiting 子状态

`scheduler.py:1625-1632`：

```python
@staticmethod
def _is_blocked_waiting_status(status: RequestStatus) -> bool:
    return status in (
        RequestStatus.WAITING_FOR_STRUCTURED_OUTPUT_GRAMMAR,
        RequestStatus.WAITING_FOR_REMOTE_KVS,
        RequestStatus.WAITING_FOR_STREAMING_REQ,
    )
```

这些是 blocked 子状态，不在 `waiting` 而在 `skipped_waiting` 中。`schedule()` 处理时若状态未解除（`_try_promote_blocked_waiting_request` 返回 False），pop 出来放入 `step_skipped_waiting` 本步不调度。

`scheduler.py:1634-1636` — 入队规则：

```python
def _enqueue_waiting_request(self, request: Request) -> None:
    if self._is_blocked_waiting_status(request.status):
        self.skipped_waiting.add_request(request)
    else:
        self.waiting.add_request(request)
```

`scheduler.py:1638-1648` — 队列选择（FCFS 和 PRIORITY 两种策略）：

```python
def _select_waiting_queue_for_scheduling(self) -> RequestQueue | None:
    if self.policy == SchedulingPolicy.FCFS:
        return self.skipped_waiting or self.waiting or None
    if self.waiting and self.skipped_waiting:
        waiting_req = self.waiting.peek_request()
        skipped_req = self.skipped_waiting.peek_request()
        return self.waiting if waiting_req < skipped_req else self.skipped_waiting
    return self.waiting or self.skipped_waiting or None
```

FCFS 模式下优先挑 `skipped_waiting` 中的（它们被 skip 过，应优先重试）。PRIORITY 下比较两个队列头部的优先级。

---

## schedule() 完整流程

`scheduler.py:335-856`。核心结构分两阶段：decode（遍历 running list）→ prefill（从 waiting 逐个尝试）。

### 阶段 1：遍历 RUNNING requests（decode）

`scheduler.py:372-490`：

```python
def schedule(self) -> SchedulerOutput:
    token_budget = self.max_num_scheduled_tokens
    # ... pause 检查 ...

    # ═══ 阶段 1: 遍历 RUNNING ═══
    req_index = 0
    while req_index < len(self.running) and token_budget > 0:
        request = self.running[req_index]
        num_new_tokens = (
            request.num_tokens_with_spec
            + request.num_output_placeholders
            - request.num_computed_tokens
        )
        # long_prefill_token_threshold clamp
        num_new_tokens = min(num_new_tokens, token_budget)
        # max_model_len clamp
        if num_new_tokens == 0:
            req_index += 1
            continue

        new_blocks = self.kv_cache_manager.allocate_slots(request, num_new_tokens, ...)
        if new_blocks is None:
            # 预占策略：preempt 最低优先级的 running request
            if self.policy == SchedulingPolicy.PRIORITY:
                preempted_req = max(self.running, key=...)
                self.running.remove(preempted_req)
            else:
                preempted_req = self.running.pop()
            self._preempt_request(preempted_req, ...)
            # 不 break，while 循环继续重试当前 request
```

decode 阶段每次只需 1 个 block（1 token），几乎总成功。若分配失败则抢占一个 RUNNING request 腾空间，继续重试。

### 阶段 2：从 waiting 中逐个尝试 prefill

`scheduler.py:554-842` — 这是 exists() 被调用的位置，也是 15-17s 窗口的根源。

```python
    # ═══ 阶段 2: 处理 WAITING ═══
    while (self.waiting or self.skipped_waiting) and token_budget > 0:
        if len(self.running) == self.max_num_running_reqs:
            break                                    # ① break

        request = request_queue.peek_request()

        # blocked status 检查
        if self._is_blocked_waiting_status(request.status) \
           and not self._try_promote_blocked_waiting_request(request):
            request_queue.pop_request()
            step_skipped_waiting.prepend_request(request)
            continue                                   # ② continue

        # max_loras 约束
        if (self.lora_config and request.lora_request and ...):
            request_queue.pop_request()
            step_skipped_waiting.prepend_request(request)
            continue                                   # ③ continue

        # ── 缓存命中查询 ──
        if request.num_computed_tokens == 0:           # ★ guard 条件
            new_computed_blocks, num_new_local = \
                self.kv_cache_manager.get_computed_blocks(request)
            if self.connector is not None:
                ext_tokens, load_kv_async = \
                    self.connector.get_num_new_matched_tokens(
                        request, num_new_local_computed_tokens)
                if ext_tokens is None:                 # async lookup 未就绪
                    request_queue.pop_request()
                    step_skipped_waiting.prepend_request(request)
                    continue                           # ④ continue
            num_computed_tokens = num_new_local + ext_tokens

        # ── 计算需要的新 token 数 ──
        num_new_tokens = request.num_tokens - num_computed_tokens

        # chunked prefill 未启用且 token 不够 → 中止
        if (not self.scheduler_config.enable_chunked_prefill
            and num_new_tokens > token_budget):
            break                                       # ⑤ break

        num_new_tokens = min(num_new_tokens, token_budget)

        # encoder 调度
        if request.has_encoder_inputs:
            # ... 可能中途 num_new_tokens == 0 → break   # ⑥ break

        # mamba block aligned split
        if self.need_mamba_block_aligned_split:
            num_new_tokens = self._mamba_block_aligned_split(...)
            if num_new_tokens == 0:
                break                                    # ⑦ break

        # ── 分配 KV cache blocks ──
        new_blocks = self.kv_cache_manager.allocate_slots(
            request, num_new_tokens,
            full_sequence_must_fit=self.scheduler_reserve_full_isl,
        )
        if new_blocks is None:
            break                                        # ⑧ ★ break

        # ── 成功 → 通知 connector + 移入 running ──
        if self.connector is not None:
            self.connector.update_state_after_alloc(request, ...,
                num_external_computed_tokens)

        request_queue.pop_request()
        request.num_computed_tokens = num_computed_tokens  # ★ guard 不再触发
        request.status = RequestStatus.RUNNING
        self.running.append(request)
```

### break vs continue 总结

| # | 源码行号 | 退出原因 | 类型 |
|---|----------|----------|------|
| ① | L556 | `len(running) == max_num_running_reqs` | `break` |
| ② | L568 | blocked waiting status 未解除 | `continue` |
| ③ | L582 | max_loras 饱和 | `continue` |
| ④ | L612 | `ext_tokens is None`（async lookup 未就绪） | `continue` |
| ⑤ | L696 | `!enable_chunked_prefill && num_new_tokens > token_budget` | `break` |
| ⑥ | L712 | encoder 调度后 `num_new_tokens == 0` | `break` |
| ⑦ | L739 | mamba block split 后 `num_new_tokens == 0` | `break` |
| ⑧ | L760 | **`allocate_slots()` 返回 None** | `break` |

**`allocate_slots` 失败用 `break` 而非 `continue`**：block 池碎片化是系统性的——第一个 prefill 分配失败，下一个大概率也成不了。与其逐个试到失败，不如直接中止，下次 step 重来。

**`continue` 的三条路径（②③④）**的共同点：它们只与当前 request 的特定状态有关（blocked、lora、async lookup），不影响队列中其他 request 的可调度性。

---

## Step 生命周期

`vllm/v1/engine/core.py:439-468`：

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

**Step** = `schedule() → execute_model() → update_from_output()` 一次循环，在 `core.py:1214` 的 `run_busy_loop()` 中无限循环。

`scheduler.py:970-986`（`_update_after_schedule`）——每步结束后推进 token 计数：

```python
def _update_after_schedule(self, scheduler_output: SchedulerOutput) -> None:
    num_scheduled_tokens = scheduler_output.num_scheduled_tokens
    for req_id, num_scheduled_token in num_scheduled_tokens.items():
        request = self.requests[req_id]
        request.num_computed_tokens += num_scheduled_token
```

---

## 源码位置汇总

| 文件 | 行号 | 内容 |
|------|------|------|
| `vllm/v1/core/sched/scheduler.py` | 64-167 | `Scheduler.__init__`：队列、约束、connector 创建 |
| `vllm/v1/core/sched/scheduler.py` | 103-107 | `max_num_running_reqs`、`max_num_scheduled_tokens` |
| `vllm/v1/core/sched/scheduler.py` | 155-167 | `waiting`、`skipped_waiting`、`running` 队列初始化 |
| `vllm/v1/core/sched/scheduler.py` | 335-856 | `schedule()` 完整方法 |
| `vllm/v1/core/sched/scheduler.py` | 372-490 | 阶段 1：遍历 RUNNING（decode） |
| `vllm/v1/core/sched/scheduler.py` | 554-842 | 阶段 2：WAITING 处理（prefill try） |
| `vllm/v1/core/sched/scheduler.py` | 596-615 | exists guard 条件 + `get_num_new_matched_tokens` 调用点 |
| `vllm/v1/core/sched/scheduler.py` | 741-766 | `allocate_slots` + break |
| `vllm/v1/core/sched/scheduler.py` | 803-822 | 成功：`status = RUNNING` + `num_computed_tokens` 赋值 |
| `vllm/v1/core/sched/scheduler.py` | 954-968 | `_preempt_request` |
| `vllm/v1/core/sched/scheduler.py` | 970-986 | `_update_after_schedule` |
| `vllm/v1/core/sched/scheduler.py` | 1625-1648 | `_is_blocked_waiting_status` + `_select_waiting_queue_for_scheduling` |
| `vllm/v1/engine/core.py` | 439-468 | `step()` |
| `vllm/v1/request.py` | 315-331 | `RequestStatus` 枚举 |
