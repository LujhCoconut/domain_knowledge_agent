# vLLM 源码分析

vLLM (Apache-2.0) 是一个高吞吐量 LLM 推理引擎，核心创新包括 PagedAttention、continuous batching、prefix caching。本文档关注 v1 引擎的调度器架构、KV connector 框架及其与外部 KV store（如 Mooncake）的交互机制。

> 分析版本：vLLM main 分支（2026-06 前后），源码路径 `/home/ljh/vllm/`（远程开发机）

---

## Scheduler: Continuous Batching 的三层队列模型

### 背景

vLLM v1 的 `Scheduler`（`vllm/v1/core/sched/scheduler.py`）是推理引擎的核心调度器，每步决定哪些 request 参与 GPU forward、分配多少 tokens 和 KV cache blocks。它使用三队列模型区分不同生命周期的 request。

### 核心数据结构

```python
# vllm/v1/core/sched/scheduler.py

class Scheduler:
    # ① 所有 request 的总仓库
    self.requests: dict[str, Request] = {}

    # ② 三层队列
    self.waiting = create_request_queue(self.policy)       # PriorityQueue（可 FCFS 或 PRIORITY）
    self.skipped_waiting = create_request_queue(self.policy)  # PriorityQueue
    self.running: list[Request] = []                       # 普通 list，按 arrival order

    # ③ 调度约束
    self.max_num_running_reqs = 80     # 最多同时 RUNNING
    self.max_num_scheduled_tokens = ...  # 每步 token 预算上限
```

### Request 状态机

```
    WAITING  ←─────────────────────────── PREEMPTED
       │                                      ▲
       │ schedule() 成功（allocate 通过）       │ preempt()
       ▼                                      │
    RUNNING ──────────────────────────────────┘
       │
       │ 完成 / abort / error
       ▼
    FINISHED_STOPPED / FINISHED_ABORTED / FINISHED_ERROR
```

- **WAITING**：在 `waiting` 或 `skipped_waiting` 队列中，等待首次被调度
- **RUNNING**：在 `running` list 中，每步参与 GPU forward（decode 每步 1 token）
- **PREEMPTED**：KV cache block 不够时被抢占，`num_computed_tokens` 重置为 0
- `WAITING_FOR_REMOTE_KVS`：特殊子状态，KV 正在从远端加载（PD 分离场景），暂存在 `skipped_waiting`

### schedule() 完整流程

```python
def schedule(self) -> SchedulerOutput:
    # ═══ 阶段 1: 遍历 RUNNING requests（decode 阶段） ═══
    for request in self.running:
        num_new_tokens = 1  # 或少量 spec decode tokens
        allocate_slots(num_new_tokens)  # 分配 1 个新 block
        # → 几乎总是成功（每次只需 1 个 block）

    # ═══ 阶段 2: 从 waiting 中逐个尝试 prefill ═══
    while token_budget > 0 and len(running) < max_num_running_reqs:
        request = 从 waiting 或 skipped_waiting 头部取出

        # ── 2a. 缓存命中查询 ──
        if request.num_computed_tokens == 0:       # ★ guard 条件
            local_hit = 本地 KV cache lookup
            external_hit = connector.get_num_new_matched_tokens()  # ← 外部 store 查询（Mooncake）
            num_computed = local_hit + external_hit

        # ── 2b. 计算需要的新 token 数 ──
        num_new_tokens = request.num_tokens - num_computed

        # ── 2c. 分配 KV cache blocks ──
        new_blocks = self.kv_cache_manager.allocate_slots(
            request, num_new_tokens,
            full_sequence_must_fit=True  # prefill 必须一次性拿到所有 blocks
        )
        if new_blocks is None:
            break  # ← ★ 退出整个 while！跳过所有后续 waiting requests

        # ── 2d. 成功 → 移入 running ──
        request.num_computed_tokens = num_computed   # ★ 由此 guard 不再触发
        request.status = RUNNING
        running.append(request)
```

### 关键的 break vs continue 差异

`schedule()` 中有多条退出路径，语义不同：

| 退出原因 | 类型 | 影响 |
|----------|------|------|
| `max_num_running_reqs` 达到上限 | `break` | 整个 while 退出 |
| blocked waiting status (`WAITING_FOR_REMOTE_KVS` 等) | `continue` | 仅跳过当前 request，继续下一个 |
| `max_loras` 约束 | `continue` | 仅跳过当前 request |
| async lookup 未就绪（`ext_tokens is None`） | `continue` | 仅跳过当前 request |
| `enable_chunked_prefill=false` 且 `num_new_tokens > token_budget` | `break` | 整个 while 退出 |
| **`allocate_slots()` 返回 None** | **`break`** | **整个 while 退出 ← 最常见** |
| Mamba block split 后 `num_new_tokens=0` | `break` | 整个 while 退出 |

**核心设计**：`allocate_slots` 失败用 `break` 而非 `continue`。因为 block 池碎片化通常是系统性的——如果第一个 prefill 分配失败了，下一个大概率也成不了。与其逐个试到失败，不如直接中止，下次 step 重新开始。

---

## Step 的生命周期

### 定义

**Step** = `schedule() → execute_model() → update_from_output()` 的完整一次循环。

```python
# vllm/v1/engine/core.py
def step(self):
    # ① 调度：决定这步谁跑、跑多少 tokens
    scheduler_output = self.scheduler.schedule()

    # ② 执行：GPU forward pass（异步提交到 GPU stream）
    future = self.model_executor.execute_model(scheduler_output, non_block=True)

    # ③ 等待 GPU 完成 + sample tokens
    model_output = future.result()

    # ④ 更新状态：处理完成/失败的 request、释放 blocks
    engine_core_outputs = self.scheduler.update_from_output(scheduler_output, model_output)
```

在 `run_busy_loop()` 中无限循环。每步耗时主要由 GPU forward pass 决定（大模型 70B+，单步 ~1-2s）。

### 每步执行完毕后

```python
# _update_after_schedule()
for req_id, num_scheduled_token in num_scheduled_tokens.items():
    request.num_computed_tokens += num_scheduled_token  # 推进 token 计数
```

decode request 每步 `num_computed_tokens += 1`，prefill request 每步 `num_computed_tokens += num_new_tokens`。

---

## exists() → get() 间的 15-17s 窗口

### 现象

在 vLLM + Mooncake 三层 KV pool (HBM/DRAM/SSD) 场景下，vLLM scheduler 在 Phase 1 调用 `batch_is_exist()`（exists 时刻）到 worker 在 Phase 3 实际调用 `batch_get_into_multi_buffers()`（get 时刻），中间隔了 **15-17 秒**。

### 根因：allocate_slots 反复失败 + guard 条件导致每步重复 exists()

**前提**：一个 32K token 的大 prefill request 需要 ~250 个 KV cache blocks（一次性分配）。80 个 decode request 每步只释放少量 blocks。

```
Step 0:
  schedule():
    request.num_computed_tokens == 0  ← guard 满足
    exists() ← ★ T0（首次外部 store 查询）
    num_computed = ext_tokens
    allocate_slots(32K) → None! break ❌
    # request.num_computed_tokens 仍然 = 0 ← 没执行到赋值那行

Step 1:
  schedule():
    request.num_computed_tokens == 0  ← guard 仍然满足（因为上次没赋值）
    exists() ← ★ 再次查询！
    allocate_slots(32K) → None! break ❌

... 重复 3-25 步 ...

Step K:
  schedule():
    exists() ← ★ 第 K 次查询
    allocate_slots(32K) → 终于成功！✅
    request.num_computed_tokens = num_computed  ← 赋值了！
    request.status = RUNNING
    running.append(request)

Step K+1:
  schedule():
    # request 已在 running 中，走 decode 路径（num_computed_tokens > 0）
    # guard 不再触发，不会再调 exists()

  GPU forward ← ★ 这个 request 终于参与了
  get_finished() → batch_get_into_multi_buffers() ← ★ get() 时刻
```

**总等待 = K × 每步耗时 = 3~25 × 1~2s ≈ 3~50s，中位数 15~17s**。

### 为什么 allocate_slots 每步都失败

| | decode request | prefill request |
|---|---|---|
| 每步需要的 tokens | 1 | 几千到几万 |
| 需要的 KV cache blocks | 1 | 几十到几百 |
| `full_sequence_must_fit` | N/A（已持有 blocks） | **True**（必须一次性全分配） |
| 失败概率 | ~0 | **高**（block 碎片化/容量不足） |

block 池供给侧：
- 每步完成的 decode request: 2-5 个
- 每个完成释放的 blocks: 10-50 个
- 每步释放总量: 20-250 blocks（分散、不连续）

prefill 需要连续 block 空间 → 碎片化导致需要多步累积才够分配。

### 影响

因为 `batch_is_exist()` 每步都被重复调用（同一个 request 同一批 key），如果每次都触发 SSD prefetch，会产生 prefetch storm（B1 bug）。Mooncake PR #2646 的 `PrefetchThrottle`（dedup TTL=30s）压制了重复触发——30s 窗口内同一 key 只触发一次真正的 SSD→DRAM 搬迁。

---

## KV Connector 框架

### 角色分离

vLLM 的 KV connector 分为两个角色，运行在不同进程中：

| 角色 | 进程 | 职责 |
|------|------|------|
| `SCHEDULER` | Scheduler 进程 | `get_num_new_matched_tokens()`（exists）、`update_state_after_alloc()`、`build_connector_meta()` |
| `WORKER` | GPU Worker 进程 | `start_load_kv()`（no-op for MooncakeStore）、`get_finished()`（实际 KV 加载）、`save_kv_layer()`（no-op） |

**Scheduler 和 Worker 之间通过 ZMQ IPC 通信**：
- Scheduler 的 `LookupKeyClient` → ZMQ REQ → Worker rank 0 的 `LookupKeyServer`
- 传输 `block_hashes`，返回 `hit_length`（外部 store 里有多少 token 已在 cache 中）

### 异步加载的两阶段设计

```
Phase 1 (Scheduler):
  get_num_new_matched_tokens() → lookup() → batch_is_exist()
  → 返回: "外部 store 有 N 个 token 的 KV"

Phase 2 (GPU forward):
  # 本次 forward 不包含这个新 prefill request
  # 前一步的 get_finished() 已经将 KV 加载入队到后台线程

Phase 3 (Worker — 在 get_finished() 中):
  # 后台线程从 store (DRAM/SSD) → GPU memory
  kv_recv_thread.add_request(req_meta)
  → batch_get_into_multi_buffers() ← 实际数据加载

  # 下一步 forward 此 request 才参与
```

**核心**：被调度的 request 不在当前 step 参与 forward——`get_finished()` 在 forward **之后**才将新 request 的 `ReqMeta` 入队到后台加载线程，下一个 step 的 forward 才用到这些 KV 数据。这实现了 compute 和 data transfer 的 overlap。

### 为什么不阻塞 forward

`get_finished()` 放在 `finally` 块中，在 GPU forward 完成后执行：

```python
# vllm/v1/worker/kv_connector_model_runner_mixin.py
with self.maybe_get_kv_connector_output(scheduler_output) as kv_output:
    # start_load_kv() ← MooncakeStore 下是 no-op
    # ★ GPU forward 在这里执行 ★
finally:
    # get_finished() ← 收尾：新请求入队 + 检查已完成加载
    output.finished_recving = kv_connector.get_finished(finished_req_ids)
```

后台 `kv_recv_thread` 在 forward 期间并行运行 → compute 和 transfer overlap。

### 关键源码位置

| 文件 | 关键内容 |
|------|----------|
| `vllm/v1/core/sched/scheduler.py:64-167` | Scheduler `__init__`：队列初始化 |
| `vllm/v1/core/sched/scheduler.py:335-856` | `schedule()`：完整调度循环 |
| `vllm/v1/core/sched/scheduler.py:586-660` | `exists()` 调用点（`get_num_new_matched_tokens`） |
| `vllm/v1/core/sched/scheduler.py:713-800` | `allocate_slots` + `break` 路径 |
| `vllm/v1/engine/core.py:439-480` | `step()`：完整 step 循环 |
| `vllm/v1/worker/kv_connector_model_runner_mixin.py:43-125` | `_get_kv_connector_output`：start_load + get_finished |
| `vllm/v1/request.py:315-331` | `RequestStatus` 枚举 |
| ` .../mooncake/store/scheduler.py` | MooncakeStore 的 scheduler 侧 exists/lookup |
| ` .../mooncake/store/worker.py` | MooncakeStore 的 worker 侧 save/load |
