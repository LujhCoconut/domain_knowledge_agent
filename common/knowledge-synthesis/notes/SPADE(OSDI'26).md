# SPADE(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-lechowicz.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: SPADE 是信号感知的 DAG 调度和动态资源供给系统——通过 "相对重要性" 指标联合优化调度和供给，在保持吞吐的前提下减少碳排放/能源成本等次要目标 **32.9%**。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| Signal-aware scheduling | 根据外部时变信号（碳强度、电价、可用功率）动态决定何时调度任务、分配多少资源 | 本文的核心概念——将外部环境约束纳入集群调度决策 |
| DAG (Directed Acyclic Graph) | 数据批处理作业的前驱约束任务图 | Spark 等框架的作业表示——stages 有依赖关系 |
| Relative Importance (rv,t) | rv,t = pv,t / maxu pu,t ∈ [0,1]，某个任务在就绪集合中的相对重要性 | SPADE 的核心指标——瓶颈任务总是 r=1，自然获得优先调度 |
| Threshold function φγ(r) | 指数型阈值函数，决定给定相对重要性的任务在多高的信号下仍被调度 | 融合在线搜索理论——低重要性任务宽松阈值、高重要性任务收紧 |
| Signal-awareness parameter γ | γ ∈ [0,1]，0 = 信号无感（恢复原调度器），1 = 最大信号感知 | 用户唯一需要调节的 knobs |
| SAP (Signal-Aware Provisioning) | SPADE 的 ablation：仅根据信号调整可用 executor 数量的配额，调度委托给信号无感策略 | 用于证明"供给和调度必须联合优化"的对照实验 |
| Stretch factor | 由于信号感知行为导致的 makespan 增加比例 | 主要性能代价指标 |
| Online search / One-way trading | 在线决策理论：玩家需在时变价格下完成 N 次购买，最优策略是指数型保留价格曲线 | SPADE 阈值函数形状的理论依据 |
| Score/probability distribution D(t) | 就绪任务的分数或概率分布（如 Decima 的 RL policy 输出, Graphene 的启发式分数） | SPADE 的输入——将任何 DAG 调度器视为黑盒 scorer |

## 背景与动机

数据中心扩张正撞上物理和环境天花板——碳强度、电价、可用功率、水资源等外部约束正变得与内部硬件容量同等重要。但现有系统是割裂的：
- **传统 DAG 调度器**（Spark FIFO/Fair、Decima、Graphene）：假设稳定资源供给，优化 makespan/throughput，完全信号无感
- **信号感知供给方案**（如 carbon-aware scaling）：仅调整资源数量，不关心作业的 DAG 结构

**关键挑战**：这两个决策是紧耦合的。在信号高时缩小资源规模——如果恰好推迟了瓶颈任务，整个下游 stages 都被阻塞。反之，不了解信号何时改善就盲目扩展——资源闲置。必须联合优化。

## 问题定义

**如何在共享集群中调度 DAG 结构的批处理作业，使其响应外部时变信号（碳强度、电价、可用功率），在保持吞吐的同时最小化信号相关的成本？**

信号值在未来不可知（online setting），仅知道历史范围 [smin, smax]。

## 方案介绍

### SPADE 核心设计

输入：任何 DAG 调度器的 score/probability distribution D(t)（如 Decima RL policy、Graphene 启发式分数）

SPADE 在其上叠加一层信号感知 filter，不需要改变底层调度器：

```
1. 从 D(t) 采样一个就绪任务 v
2. 计算相对重要性 rv,t = pv,t / max_u pu,t
3. 如果 φγ(rv,t) ≥ s(t)，调度 v；否则推迟，等待下次调度事件
4. 如果所有 executor 都空闲 → 无论如何调度（保证最小吞吐）
```

### 关键设计决策

**1. 相对重要性指标**

```
rv,t = pv,t / max_u pu,t
```

- 瓶颈任务（最高分）= 总是 r=1 → φγ(1) = smax → 任何信号下都调度
- 低分任务 = r 接近 0 → 仅低信号时调度
- 归一化方式保证继承底层 scorer 的任务排序

**2. 指数型阈值函数 φγ(r)**

```
φγ(r) = (γ·smin + (1-γ)·smax) + [γ·smax - γ·smin] · (exp(γr) - 1) / (exp(γ) - 1)
```

- 在线搜索理论（one-way trading）证明指数型是最优保留价格曲线
- 直观：低重要性任务（"第一个 unit"）在信号极差时才推迟；高重要性任务（"最后一个 unit"）几乎任何信号下都执行
- γ=0：φ0(r) = smax → 所有任务都调度 → 恢复底层信号无感调度器
- γ=1：最大信号感知

**3. 采样而非 argmax**

如果总是取最高分任务（argmax），其 r=1 永远被调度 → 无法推迟任何任务。采样让低分任务有机会被选中，然后被阈值 filter 推迟——在低信号时它们会通过 filter，在高信号时被 defer。

**4. 理论保证**

SPADE 的 stretch factor 上界为 1 + (exp.defs. × K) / (2 - 1/K)，其中 exp.defs. ∈ [0,1] 是在信号 s 下被推迟任务的期望比例。保证 stretch factor 有限。

### SAP Ablation（证明联合优化的必要性）

仅根据信号设置 executor 配额 {B, ..., K}：
- s(t) 高于阈值 → 可用 executor 数减少
- s(t) 低于阈值 → 可用 executor 数增加
- 最低保证 B 个 executor（避免完全停滞）

**SPADE 为什么优于 SAP**：SAP 不知道哪个任务更重要——可能在信号高时减少 executor，恰好阻塞了瓶颈任务。SPADE 精准地让瓶颈任务继续执行、推迟非瓶颈任务 → 更好的 makespan-cost trade-off。

### 补充操作者 knobs

- **最小吞吐保证**：强制至少 η 比例 executor 始终活跃
- **目标截止时间**：超过 deadline 的 job 进入 priority 模式，忽略信号执行

## 证据与评估

### 测试设置
- 100 节点 Kubernetes 集群上的 Spark 原型
- 高保真 Spark 模拟器（大规模实验）
- 工作负载：Alibaba traces + TPC-H（有真实 DAG 结构的查询）
- 信号：6 个区域的碳强度 traces + Google 可用功率 traces
- Baselines: FIFO, Fair, Decima (RL-based), Graphene (heuristic-based), SAP

### 关键结果

1. **碳排放减少**：SPADE 比信号无感调度器减少 **32.9%** 碳排放，同时保持相同 throughput
2. **可用功率对齐**：SPADE 比 baselines 好 **51%** 对齐可用功率信号
3. **SAP 严格劣于 SPADE**：在相同的 throughput 下，SAP 的次要目标改善始终比 SPADE 差——证明了调度和供给必须联合优化
4. **γ 参数平滑可控**：γ=0.3-0.5 在大多数场景下提供了最佳 makespan-cost trade-off
5. **对底层 scorer 不敏感**：SPADE 在 Decima 和 Graphene 两种底层调度器上都表现出一致的改善

## 整体评估

### 真正的新意
1. **首次将 DAG 结构感知和外部信号感知联合考虑**：之前的工作要么优化 DAG 调度忽略信号（Decima/Graphene），要么做信号感知供给忽略 DAG（carbon-aware scaling）
2. **"相对重要性"指标的优雅性**：不需要修改底层调度器——只需其输出一个 score/probability distribution。归一化后瓶颈任务自然获得"免疫"信号的能力
3. **在线搜索理论到系统调度的迁移**：指数型阈值的理论最优性来自金融领域的 one-way trading 问题，SPADE 将其首次应用到 DAG 调度

### 优点
- 概念极其简洁：一个参数 γ，一个公式 rv,t，一个阈值函数 φγ
- 与现有调度器兼容：黑盒 scorer 输入，drop-in 增强
- 有理论保证（stretch factor 上界）
- 实现轻量（不需要修改 Spark 核心，仅需 K8s 调度钩子）

### 局限与假设
- **假设底层 scorer 能识别瓶颈任务**：如果 scorer 质量差，SPADE 可能错误地推迟瓶颈任务
- **信号仅使用当前值和历史范围**：不使用预测，在某些可预测信号（如日前电价）上可能不如 forecast-based 方法
- **DAG 结构在提交时已知**：不支持动态 DAG（运行时 stages 变化）
- **无抢占**：已执行的任务不会被中断——降低了信号响应的粒度

### 适用条件
- 批处理 DAG 工作负载（Spark、Hive、Presto DAG）
- 外部信号有时变性（碳强度日周期、电价峰谷）
- 工作负载延迟可容忍（非交互式）
- 有 DAG 结构信息（stages + 依赖关系）

### 可复用启发
- **"相对重要性归一化"是优雅的调度原语**：不需要理解底层 scorer 的具体逻辑，只需信任其排序，归一化后瓶颈任务自然获得优先级。可推广到任何"在多个候选对象中做取舍"的 filter 设计。
- **"在线搜索理论 → 系统调度"是一个有生产力的迁移路径**：one-way trading 的最优策略（指数型阈值）在资源调度场景有自然对应——"任务"对应"购买 unit"，"信号"对应"价格"，"截止时间"对应...集群队列不为空的约束。
- **"Ablation 作为论证手段"**：SAP 不是随便做的 ablation——它是精心设计的"仅有供给无调度"对照，目的就是证明耦合的必要性。写系统论文时应该学习这种 ablation 设计。
- **"采样而非 argmax"是让 filter 有作用的前提**：如果总是取最高分任务，filter 永远无法推迟任何任务。这个设计细节看似小但极为关键——没有它 SPADE 就退化回原调度器。
- 来源：SPADE(OSDI'26)

### 讨论问题
- 如果信号是可预测的（如日前电力市场），SPADE 能否结合 model-predictive control 获得更大收益？
- 相对重要性指标在多租户混合工作负载（批处理 + 在线服务）场景下如何扩展？
- 与 PowerSight 结合：PowerSight 预测功率限额，SPADE 根据预测的限额调度 DAG 作业——两个 OSDI '26 系统是否可以组合？
