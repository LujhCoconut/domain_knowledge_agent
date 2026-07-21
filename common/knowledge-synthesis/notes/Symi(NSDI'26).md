# Symi(NSDI'26)

- **来源**: 23rd USENIX Symposium on Networked Systems Design and Implementation (NSDI '26)
- **作者**: Athinagoras Skiadopoulos (Stanford), Mark Zhao (CU Boulder), Swapnil Gandhi (Stanford & NVIDIA), Thomas Norrie (OpenAI, work done at Enfabrica), Shrijeet Mukherjee (NVIDIA, work done at Enfabrica), Christos Kozyrakis (Stanford & NVIDIA)
- **URL**: https://www.usenix.org/system/files/nsdi26-skiadopoulos.pdf
- **一句话 TL;DR**: 将 MoE expert 参数与 optimizer state 解耦——optimizer 静态均匀分片，expert 权重动态按 popularity 复制——利用现有的权重更新通信"免费"实现 per-iteration adaptive replication，不增加任何数据传输，相比 DeepSpeed 收敛加速 30.5%。
- **资料类型**: 论文-系统（NSDI'26）

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| MoE (Mixture-of-Experts) | 每层多个 FFN "expert"，router 动态将 token 路由到 top-k experts | 训练对象——大规模稀疏模型架构 |
| Expert Parallelism (EP) | 将不同 expert classes 分布在不同 GPU 上 | 当前 MoE 训练的标准并行策略 |
| Expert Data Parallelism (EDP) | 同一 expert class 跨多个 rank 复制多份实例 | 增加 expert capacity 的方法 |
| Expert Capacity | 每个 expert class 能处理的最大 token 数，超出则 drop | 控制 latency 但牺牲收敛 |
| Adaptive Expert Replication | 根据 popularity 动态调整各 expert 的副本数 | 理想方案——但现有系统受限于 optimizer state 迁移开销 |
| Optimizer State | Adam optimizer 的 momentum + variance（16B/expert parameter，fp32） | 最大瓶颈——expert weight 的 8×，迁移开销 2.46-4.10× 迭代延迟 |
| ZeRO-1 | 将 optimizer state offload 到 CPU + 均匀分片 | Symi 的基础——但 ZeRO 绑定 optimizer 到 expert instance |
| Auxiliary Load-Balancing Loss | 惩罚不均衡 expert 利用率的损失项 | 现有缓解负载不均的手段——大系数伤害收敛 |
| All-reduce / All-to-all | MoE forward/backward 需要的集合通信操作 | Symi 修改了 all-reduce 实现以支持 intra-rank replication |

## 背景与动机

### MoE 训练的 Expert 负载不均

MoE 模型的 router 动态分配 token 到 experts，但 popularity 分布**高度偏斜且快速变化**（single layer 内 3 个 iteration 可波动 16×）。现有方案有两个极端：

- **Low expert capacity** → latency 低但 drop tokens 多 → 收敛慢
- **High expert capacity** → 收敛好但 latency 高（popular expert 成瓶颈）

**根本原因**: expert replication 是均匀且静态的，而 expert popularity 是偏斜且动态的。

### Adaptive Replication 为什么不可行

理想的方案是让 popular experts 有更多 replicas → 需要动态迁移 expert state。但 optimizer state 是 **expert weights 的 8×**（fp16 weights + fp32 Adam = 2B + 16B/expert parameter）。对于 GPT3-175B 规模的 hidden dim = 12288：

- Expert weights: 3.375GB
- Expert optimizer state: **27GB**
- 在 400Gbps IB 上迁移 = **0.54s**（per expert per layer）≈ 整个 iteration 时间

现有 adaptive replication 系统（FlexMoE）只能每 50-100 iterations 迁移一次 → 无法跟上 per-iteration 的 popularity 变化。

## 问题定义

**要解决什么**: 实现 **per-iteration granularity** 的 MoE expert adaptive replication，将 expert 副本数动态匹配 popularity 分布，最小化 token drops + latency，且不引入额外数据迁移开销。

**现有工作为什么不够**:
- Static replication (DeepSpeed): token drop 多，收敛慢
- Infrequent adaptive replication (FlexMoE): 无法跟上快速变化的 popularity；rebalancing 时延迟 spike 2.46-4.10×
- Auxiliary loss tuning: 大系数伤害 expert specialization；小系数不能解决负载不均

## 方案介绍

### 方案概述

**核心 insight: Decouple model weights from optimizer state**

```
Current systems:                    Symi:
┌─────────────────┐                ┌─────────────────┐
│ Expert Instance  │                │ Expert Instance  │ (Dynamic, GPU)
│ ┌─────────────┐ │                │ (weights only)   │
│ │ Weights (2B)│ │                └────────┬────────┘
│ │ Optimizer   │ │                         │
│ │ State (16B) │ │  ← Bound together       │ weight update
│ └─────────────┘ │    Must move 18B/param  │ (same volume
└─────────────────┘    during rebalancing    │ either way!)
                         │
                ┌────────┴────────┐
                │ Optimizer State  │ (Static, CPU DRAM)
                │ 1/N per node    │  Uniformly partitioned
                └─────────────────┘  across ALL nodes
```

**关键观察**: 每次 optimizer step 后，optimizer 总是需要把 updated weights 传回 GPU slots。无论传到"同 expert 的旧位置"还是"新 expert 的新位置"，**数据传输量完全一样**。→ 借助这个已有的通信"免费"改变 expert placement。

### 关键模块

#### 1. Optimizer State 的静态均匀分区

- 每个 expert 的 optimizer state 均匀分片到**所有 N 个节点**（不是像 ZeRO 那样只分片到托管该 expert 的 r 个节点）
- 数学上证明这是 latency-optimal 的（Appendix A.1）
- 总内存占用: `M = EO`（与 static baseline 相同，但更均匀分布）

#### 2. Per-Iteration 零开销 Rebalancing

**通信量不变性证明**:

| Phase | Static Baseline | Symi |
|-------|----------------|------|
| Gradient Comm | `rEG = sNG` | `∑ri × G/N = sNG` |
| Weight Comm | `rEW = sNW` | `∑ri × W/N = sNW` |

Total data moved 完全相同 → 额外 overhead 仅来自 locality 变化: `(E-s)/(sN - E(1-BWnet/BWpci))` → 实际仅 **1.52%** 额外通信。

**步骤**:
1. Forward: router 分配 token + aggregate expert popularity（all-reduce，每 class 1 element → negligible）
2. Backward: all-reduce synchronize gradients across replicas of same expert class
3. Optimizer: gather gradient partitions → produce updated weights → **distribute to new placement**
4. Scheduler: calculate next iteration's placement from popularity metadata

#### 3. Expert Placement Scheduler

- **策略**: mimic previous iteration's popularity（简单有效）
- 按 popularity 比例分配 replicas，至少 1 instance per expert
- **Intra-rank locality**: 同一 expert class 的实例优先放在同一 rank → 减少跨 rank all-reduce 通信
- Placement 算法是 deterministic 的 → 每个 rank 独立计算，无需协调

#### 4. 新 Collective 实现

**Intra+Inter Rank All-Reduce**:
- 允许同一 expert class 的多个实例在同一 rank 上（传统 NCCL 不支持）
- 1) 每个 rank 选举 slot representative
- 2) Intra-rank: 其他同 class slots → add to representative
- 3) Inter-rank: all-reduce across representatives
- 4) Representative → normalize + copy back to other slots
- **效果**: 跨 rank 通信量减少 + 消除了 NCCL 的 "每个 expert class 只能 replicas ≤ N" 限制

**Communication Group 预注册**:
- Expert placement 变化 → all-reduce 的参与 rank 集合变化
- NCCL group 创建代价: 在 2048-rank 集群 > 1000s
- Symi: 预注册所有需要的 consecutive-rank groups（O(N²)）→ 零运行时 group 创建

**Gradient Collection Load-Balance**:
- 每个 expert class 选一个 instance 作为 gradient shard source
- 优先 local transfer → remote 时 round-robin 避免热点

## 实现

- 基于 DeepSpeed 实现
- 新增组件: Symi Optimizer + Expert Placement Scheduler + Layer Metadata Store
- 修改: Router（aggregate popularity）+ Runtime Engine（dynamic groups）+ All-Reduce（intra+inter rank）
- 支持 ZeRO-1/2/3，compatible with TP/PP

## 证据与评估

### 测试环境

- Azure NC24ads-v4 × 16: A100 80GB, PCIe 4.0 32GB/s, 100Gbps ConnectX-5
- GPT-Small/Medium/Large (125M/350M/760M) × 32 experts
- MMLU dataset, sequence length 512, batch size 64
- capacity_factor = 1.0, Top-k=1 routing, 16 expert classes, 4 slots/GPU, 64 total instances

### 主要实验结果

#### Time-to-Convergence

| System | Time to target loss (min) | vs Symi |
|--------|--------------------------|---------|
| DeepSpeed | 147.84 | **+30.5%** |
| FlexMoE-100 | 145.42 | +29.4% |
| FlexMoE-50 | 141.60 | +25.9% |
| FlexMoE-10 | 138.61 | +25.9% |
| **Symi** | **102.68** | — |

**数据解读**: FlexMoE-10 在收敛性上接近 Symi（same #iterations to target loss），但系统性能差（~35% higher per-iteration latency）→ Symi 端到端胜出。

#### Token Drops

| System | % tokens dropped (vs Symi) |
|--------|---------------------------|
| DeepSpeed | **+69%** |
| FlexMoE-100 | +64% |
| FlexMoE-50 | +62% |
| FlexMoE-10 | +43% |

**关键**: Drop 越少 → 收敛越快。Symi 的 per-iteration rebalancing 最小化 drops。

#### Iteration Latency

| Model | Symi vs DeepSpeed | Symi vs FlexMoE-10 |
|-------|-------------------|---------------------|
| GPT-Small (125M) | **-2.8%** | ~-35% avg |
| GPT-Medium (350M) | **-3.2%** | — |
| GPT-Large (760M) | **-9.3%** | FlexMoE OOM |

**Symi 比 static DeepSpeed 还略快**: 归因于 enhanced all-reduce collectives 减少跨 rank 通信。

#### New Components Overhead

| Component | % of iteration time |
|-----------|---------------------|
| Popularity all-reduce | < 1.06% |
| Expert scheduler | — |
| Metadata update | — |
| **Total** | **0.70-1.06%** |

#### Auxiliary Loss Sensitivity

DeepSpeed 依赖高 auxiliary loss coefficient 降低 drops → 但损伤 expert specialization 和 model quality。Symi 在所有 coefficient 下保持低 drop rate (~10%) → auxiliary loss 变成 quality knob 而非 system necessity。

## 整体评估

### 真正的新意

1. **Decoupling 的巧妙**: optimizer 不需要知道 expert 在哪——不管 weight 更新发给"老 expert slot"还是"新 expert slot"，数据量相同 → **借助已有通信做 rebalancing**。这是一个漂亮的 "不变性利用" 设计。
2. **Per-iteration placement 的数学证明**: 不是 heuristic，而是证明了通信量不变 + overhead 公式 → 实际 <2%。这是 rigorous systems design 的典范。
3. **Intra+inter rank all-reduce**: 打破 NCCL 的 "每个 expert class 只能 N 份 replica" 限制 → 允许任意 placement schedule。这是一个简单但有效的 NCCL 扩展。

### 优点

- 设计原则清晰: decouple → 零额外通信 → per-iteration rebalancing → minimize drops → faster convergence
- 数学分析扎实: 通信量不变性、optimizer partition latency-optimality、overhead 公式
- 消融实验完整: convergence / drops / latency / breakdown / auxiliary loss sensitivity / scalability
- 工程实用: 基于 DeepSpeed，兼容 ZeRO/TP/PP，11K 行实现
- 与 FlexMoE 的对比凸显了 decoupling 的价值

### 缺点

- 测试规模较小: 16 GPUs, 760M max model → 未验证千卡/千亿参数规模
- 基于 CPU offload → PCIe BW 可能成为瓶颈（讨论中坦承）
- GPT-only: 未测试非 Transformer MoE
- 仅 Top-k=1: 多 expert per token (k>1) 可能改变 token distribution
- Previous-iteration proxy 的可靠性未在更 chaotic 的 popularity 分布上验证

### 局限与假设

- Expert popularity 在连续 iteration 间足够 smooth → 如果分布极 chaotic（e.g., 交替频繁），proxy 可能不准
- Optimizer offload 依赖 PCIe BW → 在大模型下 PCIe 可能成为瓶颈
- 假设 optimizer state 均匀分片的 overhead（在 CPU-GPU 传输中）可忽略 → 证明成立但不含更复杂的 memory hierarchy

### 适用条件

- MoE 模型训练（8-512 experts, top-k routing）
- Optimizer state 已 offload/sharded 的场景（ZeRO-1+）
- 大规模集群（N 几百到几千）
- Expert popularity 有 per-iteration continuity（真实训练中常见）

### 可复用启发

1. **"通信量不变 → 免费改变目的地"**: Symi 证明了当通信 volume 不变时，可以零成本改变 placement。**可推广模式**: 任何有 "周期性 group communication → 下一周期可以改变 receiver" 的场景——parameter server 的梯度聚合、federated learning 的 model aggregation、streaming systems 的 state redistribution
2. **"Decouple fast-changing from slow-changing state"**: Optimizer state 需要在所有可能的 hosts 间共享 → static partitioning；Expert weights 需要快速适应 popularity → dynamic placement。**可推广**: 任何有 "随时间演化 + 跨节点重新分配" 需求的 stateful system
3. **"Previous iteration as proxy for next": 最简单的预测往往是够好的**: 不需要 ML 预测 popularity → 直接用上一轮的 distribution。类似 FastServe 的 "profile prefill time 替代 ML 预测 output length"——确定性/历史信息常被低估
4. **"Auxiliary loss = quality knob, not system necessity": 系统设计消除了对 hyperparameter tuning 的依赖**: 类似 FastServe 消除 MLFQ quantum 的 workload-sensitive tuning → 好的系统设计应该让 hyperparameters 从 "必须调" 变为 "可选优化"
5. **"Intra+inter rank all-reduce 打破 replication ceiling": NCCL 的不支持 intra-rank all-reduce 是历史设计限制 → Symi 的 3-step solution 简单而高效 —— 候选 election + representative all-reduce + copy back

### 与 DeepSeek 方案的关系

DeepSeek-V3 [26] 使用 auxiliary-loss-free load balancing → 通过注入 bias 到 router score 而非修改 loss。Symi 的 adaptive replication 是 **正交补充**——auxiliary-loss-free 改变 token routing 让 experts 更平衡，Symi 改变 expert replication 让系统能处理剩余的不平衡。两者可以同时使用。
