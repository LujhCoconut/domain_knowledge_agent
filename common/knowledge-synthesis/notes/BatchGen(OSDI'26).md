# BatchGen(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-xu-tairan.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: BatchGen 用「序列协程」模型重新设计批量推理架构——sequence 可在 module 边界 yield、跨 GPU combine/partition/migrate，突破 MoE 稀疏性和长尾解码造成的 GPU 利用率瓶颈，BCT 最高降低 2.3×。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| Batch Completion Time (BCT) | 从 batch 提交到所有 sequence 处理完毕的总时间 | 批量推理的核心优化目标，替代交互式推理的 TTFT/TPOT |
| Sequence Coroutine | 将每个 sequence 建模为可暂停、合并、分区、迁移的协程 | BatchGen 的核心抽象——打破传统"sequence 固定绑定 GPU"的限制 |
| Yield Point | Module 边界（如 attention→MoE）处暂停执行的位置 | 允许 scheduler 累积更多 sequence 后再 batch 执行下游 module |
| Intra-forward yield | 单次 forward pass 内的 yield（如 attention 后 yield，MoE 前 combine） | 为稀疏 MoE 层提供更大的 batch size |
| Inter-forward yield | 跨 forward pass 的 yield（如 decode 迭代间） | 用于长尾 straggler 管理、内存换出和 refill |
| COMBINE / PARTITION / MIGRATE | 合并多 sequence→批量执行 / 拆分单 sequence→多 GPU / 迁移 state→其他 GPU | 协程四原语中的三个运行时操作 |
| Refill | 在 decode 阶段 GPU 空闲时，注入新的 prefill sequence | 防止 decode 长尾导致 GPU 空闲 |
| O_N_LONG_TAIL callback | 检测到剩余 sequence 数量低且长度大时的回调 | 触发 PARTITION 将 straggler sequence 分布到多 GPU 加速 |
| Paged KV-cache | 按 page（如 64 tokens）管理 KV-cache 分配 | 动态 sequence 管理的基础——YIELD 时已 checkpoint 到 host memory 的 page 可安全恢复 |

## 背景与动机

**批量推理已成为 AI 计算最大、增长最快的模式**：离线推理、合成数据生成、模型评测、test-time scaling、RL rollout 主导了 AI 部署的计算预算。但现有推理引擎（vLLM、SGLang、TensorRT-LLM）均继承自交互式 serving 的延迟优先模型——

**三个根本性不匹配**：
1. **Intra-sequence imbalance**：MoE 稀疏性导致 attention 和 expert 层需要不同的 batch size 才能饱和 GPU。Attention 小 batch 就饱和，MoE 层需要极大 batch。固定绑定 → 瓶颈层决定整层效率。
2. **Inter-sequence imbalance**：Test-time scaling + reasoning 产生严重长尾——DeepSeek-R1 的 P99 输出长度是 P95 的 3.78×，最大值是 9.2×。straggler 决定 BCT。
3. **利用率崩溃**：现有引擎（含 disaggregated 变体）在批量推理中损失了约 10%–70% 的可达 GPU 性能。

## 问题定义

**如何设计一个以"批量完成时间最小化"为目标的推理系统架构，从根本上解决 MoE 稀疏性导致的 per-expert batch 不足和长尾解码导致的 GPU 闲置？**

现有方案的局限：
- **Interactive engines**（vLLM/SGLang）：sequence 固定绑定 GPU，forward pass 原子执行。即使 continuous batching 也仅重组 micro-batch，sequence 本身无法跨设备迁移或分解。
- **Disaggregated inference**（DistServe/Splitwise）：将 prefill/decode 分离到不同 GPU，但仍静态放置。MegaScale-Infer 进一步分离 attention/expert，但 placement 仍固定。
- **Offloading systems**（FlexGen/DeepSpeed/MoE-Lightning）：不区分 attention 和 MoE 的 batch 需求差异，无法为 expert 层形成足够大的 batch。

## 方案介绍

### 核心抽象：Sequence Coroutine

```
传统模型：Sequence → 固定 GPU → 原子执行所有 layer → 直到完成
BatchGen：Sequence → Coroutine → [Yield → Scheduler → Combine/Partition/Migrate] → Resume → ...
```

四个协程原语：

| 原语 | 语义 | 用途 |
|------|------|------|
| **YIELD** | 暂停 sequence，checkpoint 中间状态，释放 GPU | 在 attention 后 suspension，等待更多 sequence combine 后批量运行 MoE |
| **COMBINE** | 合并多个 yielded sequence 的 hidden states 为一个 batch | 为稀疏 MoE 层增加 expert-level batch size |
| **PARTITION** | 将单 sequence 通过 tensor parallelism 分布在多 GPU 上 | 加速长尾 straggler |
| **MIGRATE** | 跨设备迁移 KV-cache + metadata | 负载均衡、故障恢复、内存压力卸载 |

### Yield Point 选择（MoE 模型）

三个选项的 trade-off：
- **A (Attention+MoE 合一)**：最小中间状态但限制了 expert batch 和并发
- **B (Attention 和 MoE 分离)** ✅ BatchGen 采用：允许在 MoE 层组合大量 sequence 的 hidden states → 形成饱和 batch；attention 层保持适度 batch → 控制内存
- **C (Per-expert 独立)**：最大并发但内存开销过大（百万级 coroutines）

### 调度算法

```
每次 forward pass:
  attention(小batch) → YIELD → COMBINE所有attention输出 → MoE(大batch)

解码阶段:
  每64 tokens (一个KV page)检查:
    Sync → Evict完成sequence → Extend/Evict缺页sequence → Refill注入新sequence
  当全局active batch ≤ 阈值且存在超长sequence:
    O_N_LONG_TAIL callback → YIELD所有 → PARTITION straggler到多GPU
```

### 内存模型

- **Host memory 作为统一存储**：模型参数 + 所有 sequence 的 KV-cache 以 host 为 source of truth
- **GPU 内存分两区**：Resident params（LayerNorm 等小型常驻） + Parameter/KV Buffer（瞬态 staging，模块执行完释放）
- **Prefill**：flash attention 的 O(N) 峰值内存 → 激进异步 offload，GPU 仅保留 2 layers 的 KV
- **Decode**：Lazy 分配（每 sequence 最初仅 2 pages），随输出增长按需扩展；内存不足时 YIELD 最长 sequence

### 静态执行计划优化

通过单 layer profiling → roofline model → DAG critical path analysis，自动搜索最优 (B_attn, B_moe, buffer sizes) 配置。O(V+E) 拓扑排序，layer DAG <100 nodes，几乎零成本。

### 开销分析

| 操作 | 开销 | 频率 |
|------|------|------|
| Hidden state checkpoint (YIELD) | <5 µs | 每 module |
| KV-cache offload (YIELD) | 异步，与 MoE 计算 overlap | 每 layer |
| CUDA event sync (inter-forward YIELD) | <1 µs | 每 forward pass |
| COMBINE（无 offload） | 0（GPU resident） | 每 batch 形成 |
| COMBINE（有 offload） | ~0.2 ms/seq/layer（10K seq） | 仅 refill 时 |
| PARTITION | 5–10s（仅触发少数次） | 仅 straggler 检测时 |
| Cross-node sync | 5–10 ms / 64 tokens | 每 page boundary（0.1-0.2% 计算时间） |

## 证据与评估

### 测试平台
- 8–128×H20 / H200 GPU，NVLink + PCIe 5.0，200Gb/s InfiniBand
- 模型：Mixtral-8×7B/8×22B、DeepSeek-R1 (671B)、Kimi-K2 (1T)
- Baselines：vLLM、SGLang、SGLang-Optimized、TensorRT-LLM、DeepSpeed、FlexGen、MoE-Lightning

### 关键结果

1. **Offline 推理** (Table 3): BatchGen 比 SGLang-Optimized 快 1.25–1.85×，在弱 GPU (H20) 上增益更大（prefill 占比更高 → batch accumulation 收益更大）
2. **Kimi-K2 1T 模型**：BatchGen 是 **唯一** 能在 8×H20 上运行 Kimi-K2 的系统（其余 OOM）
3. **Test-Time Scaling** (Table 4): RSA 工作负载下 30 分钟 SLO 内处理 1.25–1.57× 更多 sequence，60 分钟 SLO 下 1.66–1.75×
4. **RL 训练加速** (§6.3): PARTITION straggler 减少每轮 rollout 时间 5–10%（rollout 占训练 60-80%）
5. **128-GPU 大规模** (Table 5): 比 SGLang-Optimized 快 2.2–2.3×（6.5K-2.8K workload）
6. **单 GPU 极限内存** (Table 7): 比 MoE-Lightning 快 9.6×——BatchGen 通过 coroutine yield 累积大 batch 使 expert 层进入 compute-bound，而 baselines 因 per-expert batch 小 40-1000× 无法利用 GPU
7. **PD Disaggregation 对比** (Table 6): BatchGen 无需手工调 P:D ratio，性能比最优 PD 配置高 2.2×

### 生产部署
已部署在 Tencent 生产集群，通过 Ray 编排独立 BatchGen 实例 + OpenAI 兼容 API + 超额订阅保持高并发。

## 整体评估

### 真正的新意
1. **"序列协程"是推理系统的新抽象层次**：类比线程→事件驱动（Apache→Nginx）的范式转变。现有系统全部是"thread-per-request"模型——sequence 固定绑定 GPU。
2. **Model structure-aware scheduling**：利用 NN module 的天然边界（attention↔MoE）作为调度点，而非无视模型结构做黑盒 batch。
3. **统一的 prefill/decode 调度**：不像 disaggregated 系统需要静态划分 GPU 并手工调 P:D ratio。

### 优点
- 概念简洁：四个原语覆盖所有关键操作
- 无需手工调优：静态 plan（roflline model）+ 动态 adapt（callbacks）
- Drop-in 兼容：OpenAI Batch API 兼容
- 已生产验证
- 冷启动优化（huge pages + memory-mapped checkpoint）

### 局限与假设
- **Decode 通常运行在 best-effort regime**：MoE 饱和需 16384 tokens/decode，实际很难达到（见 §7）。Prefill 阶段不存此问题。
- 当前实现仅针对 Transformer MoE，扩展到 VLM/multi-modal 是 future work
- 128 GPU 后单实例扩展效率递减（MoE all-to-all 通信增长），需 multi-instance 分层扩展
- PARTITION 触发条件（全局 active batch ≤ 阈值）需要 workload-specific tuning

### 适用条件
- 批量推理场景（离线推理、合成数据、评测、RL rollout、test-time scaling）
- MoE 模型（特别是 sparse activation + 超长 decoding）
- 内存受限设备（consumer GPU、spot instance）
- 不适用于对单 sequence 延迟敏感的交互式 serving

### 可复用启发
- **"模块化模型结构 = 天然调度边界"**：attention/MoE/encoder 的接口本身就是理想的 yield point。任何 modular NN 都可以按此思路改造调度。
- **"让小 batch 瓶颈和弱 GPU 的收益反超强 GPU"**：H20 上 speedup > H200——因为 compute 越弱，batching 效率的边际收益越大。在异构集群中，弱 GPU 上的优化更紧迫。
- **"超额订阅 + coroutine pool"模式**：类似 Nginx 的事件驱动——保持 resident pool 大量 sequence，scheduler 自由选择 combine 对象而非按到达顺序 → 最大化 expert batch。
- **"静态模型 + 动态运行时"的分工**：roflline model 决定 yield point 和 batch size 上限，运行时 callback 处理不可预测的长尾。两者解耦使系统既高效又灵活。
- **"不要为每种 GPU-NIC 组合分配 GPU"**的推论：BatchGen 用软件重新定义调度粒度，与 UEP 用 CPU proxy 解耦 GPU-NIC 形成互补——两者都是"用软件层打破硬件刚性绑定"的范例。

### 讨论问题
- Coroutine 抽象能否推广到 non-MoE 推理？（作者认为 VLM 是 natural next step）
- 与 disaggregated 系统是互补还是替代？BatchGen 不需要 manual ratio tuning，但 disaggregation 的物理分离在特定场景仍有价值
- 当模型结构变得更 heterogeneous（如 multi-modal pipeline），yield point 的选择自动化是否仍可行？
