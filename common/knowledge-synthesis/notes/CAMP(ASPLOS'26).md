# CAMP(ASPLOS'26)

- **来源**: ASPLOS '26, DOI: 10.1145/3779212.3790201
- **年份**: 2026
- **全称**: Performance Predictability in Heterogeneous Memory
- **框架名**: CAMP (CXL Analysis and Modeling for Predictability)
- **作者**: Jinshu Liu*, Hanchen Xu* (Virginia Tech), Daniel S. Berger (Microsoft & UW), Marcos K. Aguilera (Microsoft), Huaicheng Li (Virginia Tech)
- **类型**: 论文-系统 (性能建模 + 策略)
- **前身**: SupMario (arXiv:2409.14317) — 最大规模 CXL 性能表征研究
- **一句话 TL;DR**: 提出 CAMP 框架，只需一次 DRAM-only 运行 + 12 个 PMU 计数器，就能将 CXL 引起的 slowdown 解析分解为 demand reads/cache-prefetching/stores 三个正交分量，闭式预测任意 DRAM-CXL 交错比例下的性能，265 个 workload 上 91-97% 预测精度 (≤10% error)；基于此设计了"Best-shot"交错策略和 colocation 策略，分别提升 21% 和 23%。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **CAMP** | CXL Analysis and Modeling for Predictability 框架 | 核心贡献：用少量 PMU 计数器预测 CXL slowdown |
| **Slowdown Decomposition** | 将 CXL 引起的性能下降分解为 3 个正交分量 | 模型的数学基础 |
| **Demand reads** | 按需读取的 stall 分量 | 分量之一，来自 LLC miss 后的直接需求 |
| **Cache/prefetching** | 缓存和预取相关的 stall 分量 | 分量之二，预取效果差异 |
| **Stores** | 写操作相关的 stall 分量 | 分量之三，store buffer/写回的影响 |
| **Weighted Interleaving** | 页面按权重分布在 DRAM 和 CXL 之间（非均匀交错） | CAMP 建模的目标策略 |
| **Best-shot Interleaving** | 基于 CAMP 模型一次性算出最优交错比例的策略 | 实践应用之一 |
| **SupMario** | 前身工作，265 workload 的大规模 CXL 表征 + 线性建模 | CAMP 的基础数据和建模方法来源 |
| **DRAM-only baseline** | 仅在 DRAM 上运行一次的 profiling 数据 | CAMP 预测模型所需的唯一输入 |

## 背景与动机

### 问题
- 异构内存（DRAM + CXL）的性能表现高度可变，取决于 workload 对延迟的敏感度
- 现有指标（miss rate、bandwidth utilization）与真实 slowdown 的关联性弱
- 需要对每个 workload 测试所有可能的 DRAM/CXL 配置 → 组合爆炸、开销过高
- 无法回答："如果我把 X% 的页面放在 CXL、Y% 放在 DRAM，性能会怎样？"

### 核心洞察
> "A DRAM-only run (plus a CXL-only run for bandwidth-bound workloads) reveals the causal microarchitectural pressure points where CXL latency translates into additional processor stall cycles."

换句话说，workload 在纯 DRAM 下运行一次，暴露出的微架构压力点（哪些 CPU stall 事件对延迟敏感）已经足以预测任意 CXL 比例下的性能。

### 与前几篇论文的关系

CAMP 是 PACT(ASPLOS'26) 和 TMO(ASPLOS'22) 的"上游"基础：
- **TMO**: 用 PSI 测 lost work，但 PSI 是结果不是预测
- **PACT**: 用 PAC 量化 per-page criticality，但需要每 20ms 持续采样
- **CAMP**: 一次 DRAM-only profiling 就能**预测**任意配置下的 slowdown，无需在线持续追踪

**三篇来自同一实验室（MoatLab, Virginia Tech）**，构成一个完整的研究栈：
- SupMario (arXiv 2024) → 大规模表征（数据基础）
- CAMP (ASPLOS'26) → 性能预测模型（建模层）
- PACT (ASPLOS'26) → 基于 criticality 的在线管理系统（策略层）

## 方案介绍

### CAMP 预测框架

#### Step 1: Profiling（仅需两次运行）
1. **DRAM-only run**: 全部页面在 DRAM 上运行一次
2. **CXL-only run** (仅带宽密集型): 全部页面在 CXL 上运行一次
- 收集 **12 个 PMU 性能计数器**：涵盖 outstanding misses, stall cycles, prefetch hits/misses, store buffer events 等

#### Step 2: Slowdown 分解
将 CXL 造成的额外 CPU stall 分解为三个正交分量：

```
CXL_Slowdown = f(stall_demand_reads, stall_cache_prefetch, stall_stores)
```

- **Demand reads**: LLC miss 后直接等待数据返回的 stall
- **Cache/prefetching**: 因为慢速 CXL 访问破坏了预取器和缓存的时间窗口
- **Stores**: store buffer full、write-combining buffer 因为 CXL 写延迟而阻塞

这三个分量**正交**——意味着它们独立捕获了 CXL 延迟影响性能的不同微架构通路。

#### Step 3: 闭式加权交错模型
对于任意 DRAM:CXL 的加权交错比例，CAMP 可以闭式计算总 slowdown：

```
Predicted_Slowdown(DRAM_ratio) = g(DRAM_ratio, CAMP_coefficients_from_DRAM_only_run)
```

不需要枚举测试所有比例——直接从一次 DRAM-only run 的 12 个计数器值外推。

### 两个策略应用

#### Best-shot Interleaving
- **场景**: 带宽密集型 workload
- **策略**: 用 CAMP 模型一次性算出最优的 DRAM-CXL 页面交错比例
- **效果**: 接近理想聚合带宽，**最高 21% 性能提升**（vs 现有 tiering 系统）

#### Colocation Placement
- **场景**: 多 workload 共享 CXL 设备
- **策略**: 用 CAMP 预测不同 colocation 组合下的 slowdown，选择干扰最小的组合
- **效果**: **最高 23% 性能提升**（vs 现有 colocation 方案）

## 证据与评估

### 测试环境
- **3 种 CXL 设备**: 真实 CXL-ready 系统，不同延迟配置
- **NUMA**: 140ns 跨 socket 访问
- **265 个 workload**: HPC (LINPACK, HPCG), 图分析 (GAPBS), 内存缓存 (Redis), ML, SPEC CPU 2017 等
- **7 种延迟配置** (在 SupMario 中): 140-410ns

### 关键结果

| 指标 | 结果 | 说明 |
|------|------|------|
| 预测精度 | **91-97%** (≤10% abs error) | 265 workloads × 多种配置 |
| Best-shot interleaving 提升 | **最高 21%** | vs 现有 tiering |
| Colocation 提升 | **最高 23%** | vs 现有 colocation |
| 所需 PMU 计数器 | **12** | 远少于全量 PMU 事件 |
| Profiling 次数 | **1-2 次** | DRAM-only (大部分) + CXL-only (带宽型) |

### 与 PACT 的共享评估基础设施
- CloudLab 双路 Skylake → CXL 模拟（190ns NUMA）
- 真实 CXL 设备（基于 MICRO'23 的 Demystifying CXL Memory）

## 整体评估

### 真正的新意
1. **"一次 DRAM run 预测任意配置"的 closed-form 模型**: 这是本系列工作中最"建模向"的贡献。TMO 是纯反馈控制（不知道未来），PACT 是在线追踪（知道当前），CAMP 是预测模型（知道任意配置下的结果）
2. **3-分量正交分解**: demand reads / cache-prefetch / stores 的分解不是简单线性回归，而是基于对微架构因果链的理解——CXL 延迟如何通过这三条独立通路转化为 stall
3. **Best-shot 策略**: 利用预测模型一次性跳到最优解，无需迭代搜索

### 优点
- **极低的 profiling 成本**: 一次 DRAM-only run 即可，不需要枚举测试所有配置
- **高精度**: 91-97% 预测精度在真实系统上非常实用
- **模型可解释**: 3 分量分解给出 CXL slowdown 的因果解释，不是黑盒
- **策略实用**: Best-shot 和 colocation 都有明确使用场景
- **大规模验证**: 265 workloads 是 CXL 领域最全面的评估

### 局限
1. **模型基于稳态**: 一次 DRAM-only run 假设 workload 的微架构压力特征在执行过程中保持稳定。对于有明显的 phase change 的 workload，可能需要多次 profiling
2. **CXL-only run 对带宽型 workload 是必需的**: 增加了 profiling 成本
3. **仅预测 slowdown，不做迁移**: CAMP 是预测框架，实际迁移决策仍需要 PACT 或 TMO 等系统。二者可互补——CAMP 回答"这个配置的性能会怎样"，PACT 回答"哪些页面应该放哪"
4. **跨平台迁移性**: 模型系数可能需要为不同 CPU 微架构重新校准
5. **SupMario → CAMP 的演进路径**: SupMario 用的是线性回归（99% fit NUMA / 91-94% fit CXL），CAMP 升级为 3-分量正交分解 + 闭式交错模型。但两者核心都是"12 counters + DRAM-only baseline"

### 与本知识库其他论文的关系

| 论文 | 关系 | 层级 |
|------|------|------|
| SupMario (arXiv) | CAMP 的前身和表征基础 | 数据层 |
| CAMP(ASPLOS'26) | 建模层：预测任意 DRAM/CXL 配置下的性能 | 预测层 |
| PACT(ASPLOS'26) | 在线策略层：基于 per-page criticality 做迁移 | 执行层 |
| TMO(ASPLOS'22) | 替代方案：基于 PSI 的反馈控制（不需要预测模型） | 执行层 |
| M5(ASPLOS'25) | 互补：CXL 控制器侧精确观测（可为 CAMP 提供更精确的输入） | 观测层 |

**理想组合**: M5 提供精确的 per-page access 数据 → CAMP 预测最优 DRAM/CXL 分配比例 → PACT 执行 per-page criticality-driven 迁移。

### 可复用启发

1. **"一次 profiling，预测所有配置"的建模范式**: 不仅适用于内存 tiering，任何涉及"改变某个子系统配置后性能会怎样"的场景都可以考虑类似的 closed-form 预测模型（如不同缓存大小、不同网络带宽配比、不同 GPU 显存分配）

2. **3-分量正交分解**: demand/cache-prefetch/store 的三分量分解框架可以推广到其他延迟敏感系统的根因分析——例如 NVMe 延迟对不同 IO pattern 的影响、GPU 显存带宽对不同 kernel 的影响

3. **12 个 PMU 计数器足够了**: 大量工作倾向于收集尽可能多的 PMU 事件然后做 ML，但 CAMP 证明精心挑选的 12 个计数器 + 理解微架构因果链的建模比纯数据驱动方法更有效。这是"理解优于数据量"的好例子

4. **Best-shot 策略**: 用模型一次性跳到最优配置，对于配置空间大但 profiling 成本低的场景（如数据库参数调优、编译优化 level 选择）可借鉴

5. **DRAM-only baseline 作为参考点的思想**: 类似 A/B testing 中的 control group——在纯理想环境运行一次获取 workload 的"本质性能特征"，然后用模型推广到非理想环境。这个方法论对其他系统中的 performance modeling 通用

6. **CAMP 和 PACT 的互补方式**: 预测（CAMP）→ 决策（PACT）→ 执行（migration）。说明在系统设计中，不同时间尺度和不同信息量的问题应该用不同的机制解决——CAMP 做粗粒度的 capacity planning，PACT 做细粒度的 page placement
