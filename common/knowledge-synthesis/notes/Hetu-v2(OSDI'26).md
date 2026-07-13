# Hetu v2(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-li-haoyang.pdf
- **全称**: Hetu v2: A General and Scalable Deep Learning System with Hierarchical and Heterogeneous Single Program Multiple Data Annotations
- **缩写**: HSPMD (Hierarchical and Heterogeneous SPMD)
- **作者**: Haoyang Li (PKU), Fangcheng Fu (SJTU), Hao Ge, Sheng Lin, Xuanyu Wang, Jiawen Niu, Yuming Zhou (PKU), Xupeng Miao (Purdue), Bin Cui (PKU & PKU Qingdao)
- **开源**: https://github.com/PKU-DAIR/Hetu
- **类型**: 论文-系统 (distributed ML training system)
- **一句话 TL;DR**: 现有 SPMD 假设"所有设备同构且所有输入等量"——但在混合 GPU 代际、频繁故障（Llama 3: 54 天 419 次中断）、变长序列（packing/straggler）的现实中不成立。HSPMD 扩展 SPMD 的声明式注解以支持**非对称分片 + 层级通信**，通过 progressive graph specialization（设备特定执行逻辑）和 dynamic graph switching（运行时适应性）统一处理空间和时间异质性，在各场景下匹配或超越专用系统。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **SPMD** (Single-Program Multiple-Data) | 同组设备运行同一程序，仅输入数据不同（GSPMD, Alpa, Megatron 的核心 paradigm） | HSPMD 要扩展的基础 |
| **HSPMD** | 层级化+异质的 SPMD——允许 per-device 不同分片策略和通信模式 | 核心贡献 |
| **Spatial heterogeneity** | 来自设备差异（混合 GPU 代际、故障后降级）的不对称性 | 通过 progressive graph specialization 解决 |
| **Temporal heterogeneity** | 来自数据差异（变长序列、dynamic batching）的时变不对称性 | 通过 dynamic graph switching 解决 |
| **Progressive graph specialization** | 从统一的 SPMD graph 逐步特化为 per-device 执行图 | 空间异质的核心机制 |
| **Dynamic graph switching** | 在运行时根据当前数据特征切换执行图 | 时间异质的核心机制 |
| **Asymmetric sharding** | 非均匀切分：大 GPU 承担更多参数/计算，小 GPU 承担更少 | HSPMD 注解的核心扩展 |
| **Hierarchical communication** | 利用标准通信原语组合出的层级化通信模式（先 intra-group 后 inter-group） | 适配混合硬件的通信优化 |

## 背景与动机

### 问题
- SPMD 的核心前提是 **"workload should be uniformly partitioned"** — 所有设备同构且所有输入等量
- 但现实中这个假设已不成立：

| 异质性来源 | 示例 | 影响 |
|-----------|------|------|
| 混合 GPU 代际 | H100 + A100 混部 | FLOPS/显存不对称 → 对称分片浪费快设备 |
| 设备不稳定 | Llama 3: 54 天 419 次意外中断（148 次 GPU 故障） | 故障后设备数变化 → 需动态重新分片 |
| 变长序列 | sequence packing, straggler | 各设备处理量不同 → 同步 barrier 等最慢设备 |

### 现有三种应对方案的局限

| 方案 | 代表 | 局限 |
|------|------|------|
| MPMD (Multiple-Program) | 手动为每种设备写不同程序 | 开发负担重、不可扩展 |
| SPMD + Scheduler | 对称 SPMD + 外部负载均衡 | 调度器和 ML 框架分离 → coarse-grained |
| Per-scenario 专用系统 | Oobleck (故障), 变长序列专用方案 | 不通用，每个场景需要单独系统 |

### HSPMD 的定位
**将可扩展性下沉到原语层**：扩展 SPMD 的注解（支持非对称 sharding）+ 组合标准通信原语实现层级通信，统一处理三种异质性来源而不需要 per-scenario 的专用系统。

### 我的分析
这是 OSDI '26 中第二篇大规模训练论文（第一篇是 Tessera）。Tessera 解决**模型架构异质性**（不同层类型的 compute-comm 比例不同）在 PP 中的挑战；Hetu v2 解决**设备和数据异质性**在 SPMD 中的挑战。两者互补：Tessera 在 PP 维度，Hetu v2 在 DP/TP 和 sharding 维度。

## 方案介绍

### 两大机制

**1. 原语层扩展 — 非对称 Sharding + 层级通信 (§4-5)**
- 扩展现有 SPMD 注解（Split, Duplicate）→ 支持 **Asymmetric Split**（大小 GPU 承担不同分片比例）
- 组合标准 collective 通信原语（all-reduce, all-gather, reduce-scatter）→ 实现层级通信
- 例: 先 intra-H100-group all-reduce → 再 inter-group reduce（小 GPU 仅参与部分通信）

**2. 执行层 — Progressive Graph Specialization + Dynamic Switching (§6-7)**

- **Progressive graph specialization** (空间异质): 从统一的 SPMD compute graph 开始 → profiling 阶段识别设备差异 → 逐步特化为 per-device 执行图（大 GPU 的图有更多计算/更少通信等待）
- **Dynamic graph switching** (时间异质): 运行时监控当前 batch 的数据特征（序列长度分布、straggler）→ 从预编译的图库中选择最优执行图 → 避免"等最慢设备"的 bubble

### 统一三种场景

| 场景 | 机制 | 效果 |
|------|------|------|
| 混合 GPU (H100+A100) | Asymmetric sharding + 层级通信 | 匹配或超过专用异构训练系统 |
| 设备故障 (GPU 丢失) | Progressive specialization → 快速重新生成执行图 | 匹配 Oobleck（专用容错系统） |
| 变长序列 | Dynamic switching 按 batch 选图 | 匹配专用变长序列系统 |

## 证据与评估

### 三种场景评估

| 场景 | 对比基线 | 结果 |
|------|---------|------|
| 异构设备 (mixed GPU gen) | 专用异构训练系统 | HSPMD **匹配或超越** |
| 不稳定设备 (failures) | Oobleck (专用容错) | HSPMD 匹配 |
| 变长序列 (mixed-length) | 专用变长系统 | HSPMD 匹配 |

在所有场景中，HSPMD 作为统一框架匹配或超越了需要 per-scenario 专用系统才能达到的性能。

## 整体评估

### 真正的新意
1. **将 SPMD 从对称扩展到非对称**：保留"单设备视角编程"的简洁性，通过原语层扩展（而非上层调度器或 per-scenario hack）实现异质性支持
2. **Progressive specialization + Dynamic switching 的双图机制**：前者解决"设备是什么"的静态差异，后者解决"这一 batch 数据是什么"的动态差异——分工清晰
3. **统一三种异质性来源**：之前需要三个不同系统（混合 GPU 调度器 + Oobleck + 变长序列专用），现在一个框架解决

### 优点
- **通用性**: 一个框架覆盖三种场景，不需要 per-scenario 定制
- **保留 SPMD 简洁性**: 用户仍写单设备代码，异质性处理由系统自动完成
- **开源**: 在 Hetu v2 中完整实现
- **系统性评估**: 覆盖全部三种异质性来源

### 局限
- **仅 SPMD/数据并行**: 不涉及 pipeline parallelism、tensor parallelism 的异质处理
- **图切换开销**: Dynamic switching 需要预编译多张图并支付切换成本——对极短 batch 可能不划算
- **与 Tessera 互补但独立**: Hetu v2 的 PP 支持有限

### 可复用启发

1. **"原语层扩展"优于"上层 patch"**：要解决"对称性假设不成立"的问题，最根本的做法是在注解/原语层引入不对称性，而非在调度层打补丁
2. **空间 vs 时间异质性的分离处理**：设备差异是 quasi-static 的（graph specialization），数据差异是 per-batch 的（graph switching）
3. **HSPMD 可与 Tessera 组合**：前者处理 DP/TP sharding 的异质性，后者处理 PP 的异质性 → 完整的大规模异质训练方案
