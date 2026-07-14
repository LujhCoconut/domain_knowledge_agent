# RLinf(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-yu-chao.pdf
- **全称**: RLinf: Flexible and Efficient Large-Scale Reinforcement Learning via Macro-to-Micro Flow Transformation
- **作者**: Chao Yu (Tsinghua), Yuanqing Wang (Infinigence AI & PKU), 等 — Tsinghua + Infinigence AI + PKU + UC Berkeley + BUAA + SJTU 联合团队
- **开源**: https://github.com/RLinf/RLinf
- **类型**: 论文-系统 (RL training system)
- **一句话 TL;DR**: RL 训练工作流高度异质（LLM 推理/training/reward model/simulator），每种组件的资源需求和动态性不同。现有系统的单一执行模式（colocated 或 pipelined）无法适应这种多样性。RLinf 提出 **M2Flow**（macro-to-micro flow transformation）——将高层、易组合的 RL 工作流在时空两个维度上自动分解并重组为优化的微执行流，用 context switching + elastic pipelining + profiling-guided scheduling 实现。对比 SOTA 系统加速 **1.07-2.43×**。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **M2Flow** (Macro-to-Micro Flow Transformation) | 宏观逻辑流（开发者编写）→ 微观执行流（系统自动优化） |
| **Context switching** | RLinf worker 在不同 RL 组件间自适应切换——利用组件的"空闲间隙" |
| **Elastic pipelining** | 在组件间灵活调整 pipeline 深度和资源的弹性流水线 |
| **Profiling-guided scheduling** | 离线 profile 各组件的资源需求 → 在线生成最优执行计划 |
| **Macro-to-micro** | 将开发者的高层 RL 工作流（policy, rollout, training）与物理执行规划解耦 |

## 核心洞察

RL 工作流的异质性来自多组件混合：LLM 推理 + training（含梯度/优化器状态，内存需求更高）+ reward models + agent tooling + embodied simulators（需 CPU 物理模拟 + GPU 图形管线）。单一执行模式（colocated: sequential → 长尾问题; pipelined: concurrent → 资源碎片化）无法适应这种多样性。M2Flow 的关键洞察是**将高层工作流描述与物理执行解耦**——系统可以自由地在时空维度上重组执行。

## 关键结果

| 指标 | 结果 |
|------|------|
| 对比 SOTA | **1.07-2.43×** end-to-end 加速 |
| 测试场景 | reasoning RL + embodied RL |

## 可复用启发

- "宏观逻辑流→微观执行流"的解耦设计是任何多组件异构工作流系统的通用范式
- Context switching 作为填充 accelerator idle gap 的第三种策略（与 colocated 和 pipelined 并列）
- RL 系统的核心瓶颈不是训练本身的吞吐，而是异构组件的调度效率
