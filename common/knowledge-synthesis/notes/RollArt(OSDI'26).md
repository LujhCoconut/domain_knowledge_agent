# RollArt(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-gao.pdf
- **全称**: RollArt: Disaggregated Multi-Task Agentic RL Training at Scale
- **作者**: Wei Gao*, Yuheng Zhao*, Tianyuan Wu* (HKUST), Shaopan Xiong*, Weixun Wang* (Alibaba) 等 — HKUST + Alibaba Group (与 Weave 同组)
- **类型**: 论文-系统 (RL training + hardware disaggregation)
- **一句话 TL;DR**: Agentic RL 工作负载混合了计算密集型 prefill、带宽密集型 decode、CPU 密集型环境执行和突发性 reward 评估——单一 GPU 集群或粗粒度解耦都无法匹配硬件特性。RollArt 将三个 pipeline 阶段映射到最佳硬件（prefill→H800、decode→H20、environment→CPU、reward→serverless），并在 trajectory 级别解耦 rollout 使慢/失败环境不阻塞其他。通过 staleness-bounded async weight sync 将 rollout 与 training 重叠。训练时间减少 **1.31-2.05×**，在 3,000 GPU 上验证。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **RollArt** (Rollout + Art) | Disaggregated Multi-Task Agentic RL Training 系统 |
| **Trajectory-level decoupling** | 将生成、环境交互和 reward 评分解耦为独立执行单元——慢 trajectory 不阻塞快 trajectory |
| **Hardware heterogeneity mapping** | 将每个流水线阶段映射到最佳硬件：prefill→H800 (compute-opt)、decode→H20 (BW-opt)、env→CPU、reward→serverless |
| **Staleness-bounded async** | rollout 和 training 之间的异步权重同步，带有 staleness bound——避免 unbounded staleness 威胁收敛 |
| **Serverless reward** | 将无状态 reward 计算卸载到 serverless 基础设施——专用 GPU 利用率仅 7.4%，弹性伸缩更经济 |

## 关键发现

- 同一 rollout 内部已有**硬件异质性**：prefill-heavy 任务在 H800 上花费时间仅 H20 的 **0.53×**；而 decode-heavy 任务反之，H20 花费 H800 的 **0.49-0.79×**
- Reward 阶段在专用 GPU 上利用率低至 **7.4%**——serverless 是更匹配的部署模型
- 环境执行是 CPU 密集型 + heavy-tailed——慢环境不应阻塞整个 pipeline

## 关键结果

| 指标 | 结果 |
|------|------|
| 训练时间减少 | **1.31-2.05×**（对比各种 RL 系统） |
| 验证规模 | **3,000 GPU** |
| 硬件利用 | H800(prefill) + H20(decode) + CPU(env) + serverless(reward) |

## OSDI '26 RL 训练四篇全景

| 论文 | 核心机制 | 优化维度 | 团队 |
|------|---------|---------|------|
| Weave | Co-execution group 消除 dependency bubble | 跨池调度 | HKUST+Alibaba |
| **RollArt** | **硬件异质性映射 + trajectory 级解耦** | **硬件解耦 + 流水线分解** | **HKUST+Alibaba** |
| RLinf | M2Flow 宏→微流变换 | 工作流变换 | Infinigence AI+Tsinghua |
| DynaRL | 动态超图 + 资源迁移 | 运行时资源重分配 | Infinigence AI+PKU |

RollArt 与 Weave 同属 HKUST+Alibaba 组：Weave 聚焦跨集群 scheduling，RollArt 聚焦跨硬件类型 disaggregation——两者互补覆盖 RL 训练的"调度"和"解耦"两个维度。

## 可复用启发
- "将每个流水线阶段映射到最佳硬件"是异构工作负载的根本优化策略——不仅是 RL，任何多阶段异构计算管道都适用
- Trajectory-level decoupling 是处理长尾效应的通用策略：不要等待最慢的完成，让快的先推进
- Serverless reward 的洞察：利用率 7.4% 表明专用 GPU 对突发性低利用率工作是资源浪费——serverless 按需伸缩是更优模型
