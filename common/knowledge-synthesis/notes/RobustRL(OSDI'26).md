# RobustRL(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-chen-zhenqian.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 首个 RL 后训练的角色化容错系统——Detect-Restart-Reconnect，故障时仅恢复失败角色（trainer/rollout）而非重启整个任务，256 GPU 下 10% 故障率时 ETTR >80%（vs ByteRobust 60%）。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| ETTR (Effective Training Time Ratio) | 有效训练时间比例 = 实际训练时间 / 总 wall-clock 时间 | 核心指标——机器故障越多，ETTR 越低 |
| Role-based fault isolation | 将 trainer、rollout 等角色视为独立分布式子任务 | 核心洞察——一个角色故障不应影响其他角色 |
| Detect-Restart-Reconnect | 三阶段容错：角色感知检测→角色隔离恢复→动态重连 | RobustRL 的架构 |
| Semi-sync / Async RL | Semi-sync: rollout+trainer 混部+独立 rollout；Async: 纯分离 | RobustRL 同时支持三种 RL 架构 |
| UCX (Unified Communication X) | 动态点对点通信框架 | 替代静态 NCCL communicator——支持故障后动态重连 |
| Warm standby | Rollout 在 trainer 故障时作为热备快速接管 | 避免 gang-scheduling 延迟 |
| Gang-scheduling | 所有 worker 必须同时启动才能建通信组的调度约束 | 传统容错的最大瓶颈——重开任务需等所有 GPU 就绪 |

## 背景与动机

RL 后训练同时包含 rollout（推理+工具交互）和 training 两个阶段——继承了**两边**的故障模式。现有容错方案仅针对纯训练（ByteRobust）或纯推理——RL 缺乏专门的容错。

**致命问题**：在 RL 系统中，一个关键 worker 的故障会触发**整个 RL 任务重启**——丢弃训练进度、浪费计算资源、rollout 需要重新生成轨迹。

## 核心方案：角色化容错

### Detect（角色+阶段感知故障检测）

- 区分 trainer 故障 vs rollout 故障（两者行为特征不同）
- 避免 rank-level 检测的误判（rollout 的 generation 阶段看起来像 hang）和 cluster-level 检测的延迟

### Restart（角色隔离恢复）

| 故障角色 | 恢复策略 |
|----------|----------|
| **Trainer** | Rollout 作为 warm standby 快速接管——绕过 gang-scheduling，不丢弃 rollout 进度 |
| **Rollout** | 隔离替换故障机器——其他 rollout 继续生成，新 rollout 从 peer pull 最新权重 |

### Reconnect（动态通信重连）

- 用 UCX 点对点替代 NCCL 的静态通信组
- 恢复的角色可以动态加入已有通信→立即开始权重同步

## 评估

- Qwen3-8B-Math，256 GPU
- 10% 故障注入频率下 **ETTR >80%**（vs ByteRobust 60%）
- 端到端训练快 **8.4-17.4%**

## 可复用启发
- **"角色隔离"是混合工作负载容错的通用原则**：trainer 和 rollout 是不同角色→故障应分别处理。类似地，任何"离线+在线"混合系统（训练+推理、batch+streaming）都可以按角色隔离故障
- **"Warm standby 绕过 gang-scheduling"**：用已有资源（rollout）做热备，而非等待全新资源
- 来源：RobustRL(OSDI'26)
