# DynaRL(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-wang-yuanqing.pdf
- **全称**: DynaRL: Flexible and Dynamic Scheduling of Large-Scale Reinforcement Learning Training
- **作者**: Yuanqing Wang, Hao Lin, Junhao Hu 等 (PKU + Infinigence AI + Tsinghua + CAS + BUAA + SJTU — 与 RLinf 同组)
- **类型**: 论文-系统 (RL training scheduling)
- **一句话 TL;DR**: 现代 RL 工作负载展现极端动态性——重尾 rollout 分布、不规则多轮工具交互、时变瓶颈，静态资源分配浪费 **60% 计算**。DynaRL 是首个动态重分配计算/内存/通信资源的 RL 系统：用**动态超图**建模整个 RL 管线，统一资源迁移接口 + context-aware 数据路由 + 多层次调度算法实现运行时重分配。提升吞吐高达 **1.98×**，在线调度开销可忽略。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **Dynamic hypergraph** | DynaRL 的核心抽象——将 RL 管线的所有组件（推理/training/reward/simulator）和资源表示为动态超图的节点和边，随训练进展持续演化 |
| **Heavy-tailed rollouts** | 某些 rollout 路径生成极长的响应序列（尾部效应），导致静态 batch 中的 GPU 利用率低 |
| **Unified resource migration** | 在 RL 组件间动态迁移计算/内存/通信资源的统一接口 |
| **Context-aware data routing** | 根据当前超图状态智能路由数据流——确保资源重分配后数据到达正确的目标 |
| **Multi-level scheduling** | 多层次调度算法——粗粒度组件间 rebalancing + 细粒度资源迁移——协同消除瓶颈 |

## 与 RLinf / Weave 的关系

三篇 RL 论文均出现于 OSDI '26，互为补充：

| 论文 | 核心机制 | 加速 |
|------|---------|------|
| Weave | Co-execution group 交错调度消除跨池 dependency bubble | 1.84× 成本效率 |
| RLinf | M2Flow 宏→微流变换，context switching + elastic pipelining | 1.07-2.43× |
| **DynaRL** | **动态超图 + 资源迁移，首次运行时动态重分配 RL 资源** | **1.98×** |

DynaRL 与 RLinf 来自同一团队（Infinigence AI）。RLinf 聚焦工作流变换，DynaRL 聚焦运行时动态调度——前者是"设计时优化"，后者是"运行时适应"。

## 关键结果

| 指标 | 结果 |
|------|------|
| 吞吐提升 | 最高 **1.98×** |
| 静态浪费的算力 | **60%** |
| 在线调度开销 | 可忽略 |
| 工作负载 | 数学推理 + agentic RL |

## 可复用启发
- 动态超图是"高度动态的多组件管线"的强大建模工具——不仅适用于 RL
- "静态分配→动态重分配"是处理时变瓶颈的根本范式转变
- 资源迁移 + 上下文感知路由是动态系统中的两个互补机制——一个动"资源"，一个动"数据"
