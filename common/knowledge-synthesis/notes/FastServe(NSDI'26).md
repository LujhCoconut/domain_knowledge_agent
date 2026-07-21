# FastServe(NSDI'26)

- **来源**: 23rd USENIX Symposium on Networked Systems Design and Implementation (NSDI '26)
- **作者**: Bingyang Wu*, Yinmin Zhong*, Zili Zhang*, Shengyu Liu, Fangyue Liu, Yuanhang Sun, Gang Huang, Xuanzhe Liu, Xin Jin† — School of Computer Science, Peking University (* equal contribution, † corresponding author)
- **URL**: https://www.usenix.org/system/files/nsdi26-wu-bingyang.pdf
- **一句话 TL;DR**: 利用 LLM 推理的 autoregressive pattern 提供 token 粒度的抢占式调度，配合 skip-join MLFQ 和 proactive KV cache swapping，消除 FCFS 的 head-of-line blocking，吞吐相比 vLLM 最高提升 6.1×。
- **资料类型**: 论文-系统（NSDI'26）

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| MLFQ (Multi-Level Feedback Queue) | 经典 OS 调度算法：多级优先级队列，job 从高优先级开始，超时为降到下一级 | 核心调度框架——无需先知 job 大小即可逼近 SRPT |
| Skip-Join | 新 job 不总是从最高优先级开始，而是根据 input length 直接加入合适优先级的队列 | 核心创新——利用 input length 已知的信息来减少降级次数 |
| Semi Information-Agnostic | 输出长度未知但输入长度已知——LLM 推理的独特信息状态 | 调度问题设定——介于全知（SRPT）和全盲（经典 MLFQ）之间 |
| KV Cache | Transformer 推理中缓存的 Key-Value 张量，避免每步重算 | 抢占式调度的核心内存开销来源 |
| ENST (Estimated Next Scheduled Time) | 预测 job 下一次被调度执行的时间 | 决定 KV cache swap 顺序的指标 |
| Proactive Swapping | 在 job 需要执行前预先 swap in KV cache，与当前执行重叠 | 隐藏 PCIe 传输延迟的关键技术 |
| Head-of-Line Blocking | 长 job 堵塞短 job，导致队列延迟占端到端 90%+ | 核心要解决的问题 |

## 背景与动机

### LLM 推理的独特特性

- **Autoregressive 生成**: 每步生成一个 token，迭代直到 `<EOS>`
- **Prefill + Decode 两阶段**: 第一个 iteration（prefill）处理全部 input tokens，计算量大；后续 iteration（decode）每次只处理一个 token，计算量小
- **执行时间不可预测**: 输出长度未知 → 总执行时间不确定

### 现有系统的 Head-of-Line Blocking

- Orca/vLLM 用 FCFS + run-to-completion：一旦调度就一直跑到完
- 真实 workload（ShareGPT/Alpaca）输出长度重尾分布 → 长 job 堵塞短 job
- **Queuing delay 占端到端延迟 90%+**——优化 execution time 不够，必须优化 queuing delay
- Chunked prefill 拆分长 input 但错误定位了核心问题——**长 output 是更频繁的瓶颈**

### 为什么 MLFQ 不能直接用于 LLM

- 经典 MLFQ: 所有 job 先入最高优先级队列 →
- Prefill 时间长（如 input 1024 tokens → 数倍于 decode token 时间）→ job 在第一轮就耗尽 quantum → 如果在 prefill 中途抢占→ 中间激活被丢弃重算 → 浪费计算

## 问题定义

**要解决什么**: LLM serving 场景中 FCFS 导致的 head-of-line blocking，在不预知输出长度的 semi information-agnostic 设定下用抢占式调度最小化平均延迟。

**现有工作为什么不够**:
- FCFS (vLLM/Orca): HOL blocking → queuing delay 占 90%
- SRPT: 需要预知 job 大小 → LLM 输出长度不可知 → 不可用
- 经典 MLFQ: 未考虑 LLM 两阶段执行模式 → prefill 被干扰
- Fixed Priority (by input length): 忽略 output length 长尾 → 长输出 job 饥饿

## 方案介绍

### 架构总览

```
Host                         GPU Cluster
┌──────────┐   ┌─────────────────────────────────┐
│ REST API │   │  Scheduler                      │
│ Frontend │──▶│  ┌───────────────────────────┐  │
└──────────┘   │  │  Skip-Join MLFQ          │  │
               │  │  Q1(q1) → Q2(q2) → ...   │  │
               │  └──────────┬────────────────┘  │
               │             │ pick batch        │
               │  ┌──────────▼────────────────┐  │
               │  │  Distributed Exec Engine  │  │
               │  │  (TP + PP)                │  │
               │  └──────────┬────────────────┘  │
               │             │                   │
               │  ┌──────────▼────────────────┐  │
               │  │  KV Cache Manager         │  │
               │  │  (Proactive Swap)         │  │
               │  └───────────────────────────┘  │
               └─────────────────────────────────┘
```

### 关键模块

#### 1. Skip-Join MLFQ Scheduler

**核心思想**: 利用 semi information-agnostic 设定—input length 已知—来优化 MLFQ 的初始 placement。

- **Skip-Join**: 新 job 到来时，profile 其 prefill 时间 `t_init` → 加入满足 `q_i ≥ t_init` 的最高优先级队列 → 跳过更高优先级队列（减少无意义降级）
- **Demotion**: Job 在当前队列耗尽 quantum → 降级到优先级低 η 级的队列（FastServe 用 η=2，即 quantum 翻倍）
- **Starvation Prevention**: 周期性检查饥饿 job（等待时间 ≥ α）→ 提升到 Q1 → 保障尾延迟

**与三个 baseline 的对比**:
| Scheduler | 假设 | 优点 | 缺点 |
|-----------|------|------|------|
| FCFS | 无 | 简单 | HOL blocking |
| Naive MLFQ | 全盲 | 无 | prefill 被抢占→浪费计算 |
| Fixed Priority | input length | prefill 主导时好 | output 长尾时差 |
| **Skip-Join MLFQ** | **semi 盲** | **全方位适应** | 需要 profile |

**关键效果**: 在不同 input/output length ratio 下（0.25–256×），skip-join MLFQ 始终最优——比 FCFS up to 8.9×，比 naive MLFQ up to 1.87×，比 Fixed Priority up to 13.9×。

#### 2. Proactive KV Cache Management

**问题**: 抢占式调度增加系统内存中 job 数→ KV cache 开销爆炸 → 单 job (OPT-175B, 512 input) = 2.3 GB KV cache → preempted jobs 的 KV cache 也要保留 → 7× FCFS 内存

**三个 strawman 及其问题**:
- **Defer 新 job**（vLLM 做法）: 退化为 FCFS → HOL blocking 重现
- **Kill+Recompute 低优先级 job**: 浪费计算 + livelock 风险
- **Reactive swapping** (out of GPU → host → reload on resume): PCIe 传输在关键路径上 → switching overhead 超 execution time

**解决方案: Proactive Swapping**:
- 预测 job 的 ENST (Estimated Next Scheduled Time)
  - `ENST(i) = min(T_promote(i), T_execute(i))`
  - `T_execute(i)` = 所有更高优先级 job 的 quantum 之和 / batch_size
- ENST 最小的 job 优先 swap in，最大的优先 swap out
- 与当前执行**流水线重叠**→ swap overhead 不在关键路径
- 预留 idle KV cache slots 应对 burst arrival

**效果**: swapping time < 5% total latency，比 Recompute 快 2.7×，比 Reactive 快 1.7×。

**ENST 的设计巧思**: 不是简单的"优先级低=swapout"——starvation prevention 可能突然提升低优先级 job → ENST 捕获了这种可能性。

#### 3. 分布式 Serving 支持

- **TP (Tensor Parallelism)**: intra-node，split operators
- **PP (Pipeline Parallelism)**: inter-node，各 stage 独立调度 → 需要在 stage 级别保持 MLFQ 语义
- **分布式 KV cache**: 各 stage 独立执行 offload/upload → 上一 stage 传输中间结果时并行传输 KV cache → 进一步隐藏 swap 延迟

## 实现

- 2.9K 行 Python (REST API + scheduler)
- 8.1K 行 C++/CUDA (distributed execution engine)
- 支持 Orca 的 iteration-level scheduling + vLLM 的 PagedAttention
- 自定义 CUDA kernels 实现 C++ 级性能

## 证据与评估

### 测试环境

- **硬件**: AWS p4d.24xlarge (8× A100 40GB, NVLink, PCIe 4.0×16)
- **模型**: OPT-13B/66B/175B, Llama3-8B (GQA)
- **Workload**: ShareGPT + Alpaca 数据集，Poisson arrival
- **SLO**: 0.3s/token (10× decode iteration latency)

### 主要实验结果

#### End-to-End Throughput (Figure 11)

| 对比 baseline | ShareGPT | Alpaca |
|---------------|----------|--------|
| vs FasterTransformer | 31.5–74.9× | 9.5–15.8× |
| vs vLLM | 2.1–6.1× | 2.75–3.5× |
| vs FastServe-FCFS | 2–4× | 1.6–2× |

**数据解读**: FastServe-FCFS（同实现、无调度优化）已超 vLLM → C++ 实现效率。Skip-join MLFQ 额外带来 2-6×（取决于模型和工作负载）。**OPT-175B 上差距最大** → 大模型每 token 时间长 → HOL blocking 更严重 → 抢占收益更大。

#### Tail Latency (Figure 12)

- FastServe 不但降低平均延迟，也降低 P95 tail latency
- vs vLLM: up to 8.1× P95 吞吐
- **Starvation prevention 有效**: long jobs 排队延迟也被减少（不再被前面的 long jobs 堵塞）

#### Goodput (Figure 13)

- P95 goodput (5×/10×/20× SLO): FastServe 比 vLLM 高 1.66–1.82×

#### Large Batch Size (Figure 14)

- Batch=64: 1.43× vLLM
- Batch=128: 1.51× vLLM
- **大 batch 下仍有收益** → skip-join MLFQ 的调度优势不受 batch size 影响

#### GQA Architecture (Figure 15)

- Llama3-8B: 2.1× vLLM (ShareGPT), 3.0× (Alpaca)
- **证明方法对 GQA 也有效** → 不限于 MHA

#### Chunked Prefill vs FastServe (Figure 18)

- FastServe 比 vLLM+Chunked-Prefill 高 1.5×
- **Chunked prefill 不能完全消除 HOL blocking** → 只拆分长 input，不处理长 output

#### 消融实验 (Figure 16)

在不同 input/output ratio (0.25–256×) 下:
- FCFS: 持续差 → HOL blocking 与 ratio 无关
- Naive MLFQ: ratio 高时差（prefill 被抢占）
- Fixed Priority: ratio 低时差（忽略 output 影响）
- Skip-Join MLFQ: 始终最优 → **自适应两阶段执行模式**

#### Proactive Swapping 消融 (Figure 17)

- vs Recompute: 2.7×
- vs Reactive: 1.7×
- Swapping time < 5% total latency

## 整体评估

### 真正的新意

1. **Semi information-agnostic 设定是 LLM serving 的精确刻画**: 不是全盲（经典 MLFQ 假设），也不是全知（SRPT 假设）——input 已知但 output 未知。这一信息不对称是 LLM 推理独有的，此前无人清晰定义。
2. **Skip-join 是从已知信息中廉价提取价值的优雅方法**: 不是写 ML 模型预测 output length，而是利用 profiling 得到的 deterministic prefill time——简单、可靠、零预测误差。
3. **Proactive swapping = 将 "swap what" (ENST) 和 "when to swap" (ahead of time, pipelined) 作为联合决策**: 不仅考虑空间维度（谁的 cache 换出），还考虑时间维度（什么时候做这操作）

### 优点

- 问题定义清晰：queuing 占 90% → 优化调度而非执行
- 简单的解决方案：MLFQ + skip-join = 数十行代码，但效果显著
- 消融实验完整：每个设计点都有对比
- Sensitivity 分析全面：不同模型大小、不同 ratio、GQA、大 batch
- 工程完整：11K 行 C++/Python，支持 REST API + TP + PP

### 缺点

- **ENST 公式的假设**: 假设更高优先级的 job 都不提前完成且被依次降级到当前优先级——这个假设可能保守或激进
- **Starvation threshold α = 300ms**: 这个值的选择可能对 workload 敏感
- **无真实生产 trace**: 实验用 Poisson arrival + ShareGPT/Alpaca → 真实负载可能有更强的时间相关性和 burst
- **无与 disaggregated serving 的对比**: Splitwise/DistServe/LoongServe 通过拆解 prefill/decode 消除干扰——FastServe 只对比了 vLLM/FT

### 局限与假设

- 假设 profiling 准确（prefill/decode 时间预测正确）→ GPU 性能变化（温度降频、共享资源竞争）可能引入误差
- ENST 公式忽略了新 job arrival 导致的优先级重建
- Proactive swapping 需要预留 KV cache slots → 降低了有效 batch size 上限

### 适用条件

- 在线交互式 LLM serving（在线教育、对话、代码补全）
- Workload 有显著的输入/输出长度差异（重尾分布）
- GPU 内存紧张，需要 swap KV cache
- Single instance → 多 instance 场景由 Llumnix 处理

### 可复用启发

1. **"Semi information-agnostic"是一大类系统问题的通用设定**: 任何 "部分信息已知、部分信息不可预测" 的调度问题 → 像 FastServe 一样，利用已知信息优化初始决策（skip-join），用 feedback (demotion/promotion) 处理未知部分
2. **"抢占粒度 = 应用的自然原子边界"**: LLM 每 token 是自然抢占点 → 不需要强制中断 → 零重算开销。可推广到任何有自然 yield point 的应用
3. **"Proactive I/O 重叠是最被低估的性能优化之一"**: 用 ENST 预测未来需求 → 提前准备 → 与当前计算重叠。适用于任何有"异步 prefetch/sync"模式的系统
4. **"不要用 ML 预测一切——确定性信息比统计模型更可靠"**: Prefill 时间可以直接 profile → 不需要 ML 模型。简单、零误差、可解释。对 input length 做 skip-join 比用 ML 预测 output length 做 SRPT-approx 更实用
5. **Pipeline parallelism 打破传统 MLFQ 语义**: 每个 stage 独立调度 → 同一个 job 在不同 stage 可能被不同的 job 打断 → 引入"pending state 的最高优先级"规则来保持 MLFQ 近似

### Discussion 中值得关注的扩展方向

- Multi-instance 场景(与 Llumnix 互补)
- 更长 context window 下的 KV cache 管理
- MoE 模型的 expert selection 可能引入额外的调度维度
