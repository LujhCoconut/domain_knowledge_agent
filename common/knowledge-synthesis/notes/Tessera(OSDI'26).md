# Tessera(OSDI'26)

- **来源**: OSDI '26 (Operational Systems Track), https://www.usenix.org/system/files/osdi26-hu-weifang.pdf
- **全称**: Tessera: A Holistic Pipeline Parallelism Framework for Trillion-Parameter Heterogeneous MoE Training
- **作者**: Weifang Hu (HUST & Alibaba Cloud), Langshi Chen*, Man Yuan*, Youyang Yao, Xiulong Yuan, Li Tian, Yong Li, Wei Lin (Alibaba Cloud), Xuanhua Shi† (HUST), Zhengping Qian†, Jingren Zhou (Alibaba Cloud)
- **类型**: 论文-系统 (Operational Systems — massive-scale ML training)
- **一句话 TL;DR**: 千亿参数 Qwen3/Qwen3-Next 在生产集群 10,000+ GPU 上训练时，模型架构的异质性（混合 DeltaNet + softmax attention + sparse MoE）打破了现有 pipeline parallelism 的均匀性假设。Tessera 通过 overlap-aware partitioner + fine-grained overlap scheduler + dynamic bubble optimizer 三组件协同优化，在 4,096-12,288 GPU 规模上比生产 baseline 提升 **20-33% throughput**，万亿参数模型达到 **39% MFU**，vs Megatron-Core 提升 **1.24×**。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **PP** (Pipeline Parallelism) | 将模型按层切分为多个 stage，每个 GPU/microbatch 以流水线方式执行 | Tessera 优化的核心目标 |
| **MoE** (Mixture-of-Experts) | 稀疏激活的前馈网络，仅部分 expert 对每个 token 激活 | 引入 All-to-All 通信和 routing skew 的来源 |
| **A2A** (All-to-All) | MoE 的 token dispatch/combine 通信原语 | 需要被 overlap 的主要通信开销 |
| **1F1B** (1-Forward-1-Backward) | 经典的 PP 调度策略：交错执行 forward 和 backward | 现有 baseline |
| **Heterogeneous architecture** | Qwen3-Next 中 Gated DeltaNet + softmax attention + dense FFN + MoE 的混合层结构 | 打破均匀性假设的根本原因 |
| **Overlap-aware partitioner** | 基于 profiled post-overlap cost（而非 serial cost）的 stage 切分策略 | Tessera 核心创新 #1 |
| **Fine-grained overlap scheduler** | 为每对层组合单独合成最优的 compute-communication 交错方案 | Tessera 核心创新 #2 |
| **Dynamic bubble optimizer** | 监控 MoE routing metadata，在 routing 引起的 idle slot 中插入可移动任务 | Tessera 核心创新 #3 |
| **MFU** (Model FLOPs Utilization) | 实际 FLOPS / 理论峰值 FLOPS | 大规模训练的核心效率指标 |
| **Bubble** | PP 中因 stage 间等待而产生的 GPU 空闲时间 | 传统 PP 的主要效率损失 |
| **Virtual stages** | 每个物理 rank 分配多个"虚拟"stage，允许同一 rank 上不同 micro-batch 的 chunk 交错执行 | 实现细粒度 overlap 的机制 |

## 背景与动机

### 问题
- Qwen3/Qwen3-Next 架构不再是一致 Transformer blocks — 混合了 DeltaNet (linear attention) + softmax attention + dense FFN + sparse MoE
- **三个异质性来源**:
  1. **Layer heterogeneity**: 不同层类型 compute-communication 比例不同 → 统一的 overlap 策略只适合部分组合
  2. **MoE routing skew**: 不同 expert 被激活的频率不均匀 → 各 stage 之间的负载不一样 → 产生 transient idle slot
  3. **Scale-induced communication**: 10K+ GPU 上，通信时间占比巨大，overlap quality 直接影响吞吐

### 为什么现有方案不够

现有 PP 系统（Megatron-Core, DeepSpeed）采用 uniform 策略:
- **Uniform partitioning**: 按 serial layer cost 平均切分 → 忽略 overlap 后各 partition 的实际 cost 差异
- **Uniform overlap**: 所有 stage 用相同 1F1B 交错 → 不同的层组合 overlap 效果差异巨大（14% vs 有效隐藏）
- **Static only**: 无法处理 MoE routing 引起的 runtime skew

### 核心数据
- 相同 model 的不同层组合: 一些层对 overlap 后通信被充分隐藏，另一些仅 14% — 差异 6×
- 10K+ GPU 上: pipeline bubble + routing skew → 显著低于理论 MFU

### 我的分析
这是 OSDI '26 第一篇大规模训练（non-inference）论文。前面的 5 篇 LLM 论文都是推理优化，Tessera 是训练优化，而且是"超大规模"级别的——10K+ GPU、万亿参数。和前面 GPU 论文相比，Tessera 的独特之处在于它将"pipeline parallelism 的均匀性假设"作为核心攻击点，通过为每种层组合单独定制 overlap 策略来消除异质性带来的效率损失。

## 方案介绍

### 三组件架构

**1. Overlap-Aware Partitioner**
- 传统: 按 serial computation cost 均分 stage
- Tessera: 对每种层组合做 **离线 profile**，测量 overlap 后的实际剩余通信暴露量
- 用 post-overlap cost（非 serial cost）驱动 partition 选择 → 同一条 pipeline 中所有 stage 的 post-overlap cost 平衡

**2. Fine-Grained Overlap Scheduler**
- 传统 unified 1F1B: 所有层用相同交错模式
- Tessera: 为每种 (layer_type_A, layer_type_B) 对**单独合成**最优 compute-communication 交错调度
- 利用 virtual stages: 同一物理 rank 分配多个虚拟 stage，不同 chunk/microbatch 的通信与计算在同一个 rank 上并行
- 效果: 全部层组合的通信都被充分隐藏（而非仅部分）

**3. Dynamic Bubble Optimizer**
- MoE routing 在运行时产生 skew → 某些 stage 提前 idle
- Optimizer 监控 routing metadata，识别即将出现的 idle slot
- 在 idle slot 中插入**可移动任务**（movable tasks，如 gradient sync 或可推迟的 compute）
- 将不可预测的 routing bubble 转化为有效利用时间

### Plan-Agnostic Execution Engine (§5)
- 独立于具体 partitioning/overlap strategy
- 用户只需指定 model architecture → Tessera 自动 profile → 生成 partition + schedule
- 无缝兼容现有的 P-D 分离、TP/EP 配置

## 证据与评估

### 测试环境
- **规模**: 4,096 至 12,288 NVIDIA Hopper GPUs
- **模型**: Qwen3, Qwen3-Next（万亿参数规模）
- **Baseline**: 生产内部 baseline（uniform PP）、Megatron-Core with public recipes
- **5 个工作负载** varying model sizes and cluster configurations

### 关键结果

| 实验 | 结果 | 要点 |
|------|------|------|
| vs 生产 baseline (5 workloads) | **+20-33% throughput** | 跨 4,096-12,288 GPUs |
| 万亿参数模型 | **39% MFU** | 在此规模下非常 competitive |
| vs Megatron-Core MoE | **1.24× MFU** | 使用相同 public recipes |
| Overlap quality | 所有层组合都被充分隐藏 | vs unified 1F1B 中部分仅 14% |

### 生产部署
- 阿里巴巴云生产集群，10,000+ GPU
- 用于 Qwen3 和 Qwen3-Next 的 pre-training
- 用户无需手动调整 partition 或 overlap 策略

## 整体评估

### 真正的新意
1. **Overlap-aware partitioner**: 首次将 "overlap 后的有效 cost" 作为 partition 决策的目标函数 → 打破了 "切分只看 serial cost" 的惯例
2. **Per-layer-combination synthesized overlap**: 不是每个 stage 统一策略，而是根据具体的层类型对单独生成最优交错方案
3. **Dynamic bubble filling for MoE routing skew**: 将 MoE 特有的 runtime 不确定性纳入 PP 优化 → 填补了 "static PP plan + dynamic routing" 之间的空白

### 优点
- **生产验证**: 10K+ GPU 上训练 Qwen3-Next，39% MFU
- **自动化**: Plan-Agnostic Engine → 用户无需 manual tuning
- **兼容性**: 与现有 Megatron-Core 接口兼容
- **完整优化链路**: partition + overlap + dynamic → 三个组件覆盖 pipeline 的全生命周期

### 局限
- **仅 MoE 模型**: overlap scheduler 的收益主要来自 MoE 的 A2A 通信 — dense 模型可能收益较小
- **需要离线 profile**: 每种 layer combination 都需要预先 profile → 新增模型架构时需要重新 profile
- **仅 pipeline parallelism**: 不涉及 TP、DP、EP 的优化 — 聚焦 PP 维度

### 可复用启发

1. **"Overlap-aware" 优于 "Compute-aware"**: 在通信密集型并行中，仅考虑 serial computation cost 不够 — 必须 profile overlap 后的有效 cost 作为决策依据
2. **Per-component customization beat uniform strategy**: 异质性架构需要异质性优化 — 统一的策略必然在某些组合上是次优的
3. **Dynamic bubble filling 的思想可推广**: 任何"static plan + dynamic load skew"系统（MoE routing、elastic scaling、straggler mitigation）都可以通过监控 + 插入可移动任务来填补 idle slot
