# Weave(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-wu-tianyuan.pdf
- **全称**: Weave: Efficient Co-Scheduling for Disaggregated RL Post-Training
- **作者**: Tianyuan Wu, Lunxi Cao (HKUST), Yining Wei (UIUC), Wei Gao, Yuheng Zhao, Dakai An (HKUST), Shaopan Xiong, Zhiqiang Lv, Ju Huang, Siran Yang, Yinghao Yu, Jiamang Wang, Lin Qu (Alibaba), Wei Wang (HKUST)
- **类型**: 论文-系统 (RL training + cluster scheduling)
- **一句话 TL;DR**: RL 后训练的 rollout-training 解耦架构产生**依赖气泡**——一个集群在另一个集群 roll/train 时空闲。Weave 通过 **co-execution group** 抽象（将多作业的 rollout 和 training 阶段交叉编排 + 双层调度）回收这些气泡。在 328 H20 + 328 H800 GPU 的生产测试床上，比标准解耦提高成本效率 **1.84×**，比 co-located SOTA **1.38×**，100% SLO 达成。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **RL post-training** | 用强化学习对 LLM 进行最终微调——释放推理能力（数学、编程、工具使用） |
| **Rollout-training disaggregation** | 将 rollout（推理器，受内存带宽限制）和 training（受计算限制）物理隔离到不同的 GPU 集群 |
| **Dependency bubble** | 由于严格同步要求，一个集群必须在另一个集群完成当前阶段之前空闲 |
| **Co-execution group** | Weave 的核心抽象——将被隔离到独立局部域中的多作业分区，交错它们的 roll/train 阶段 |
| **Two-tier scheduling** | 组间调度器（保守随机规划优化作业放置）+组内调度器（可证明最优的轮询编排） |
| **Residency constraint** | 组内大规模模型状态保留在主机内存中——使"热启动"上下文切换无需重新加载权重 |
| **Conservative stochastic planning** | 组间调度器处理随机 RL 序列长度——对不可预测的 token 生成制定保守估计预算 |
| **On-policy** | 要求 rollout 和 training 保持同步的 RL 算法——现有系统通过切换到非策略（样本陈旧）来消除 bubble，以模型精度为代价 |

## 背景与动机

### 问题
- RL 后训练已成为 LLM 开发的关键阶段（用于数学/编程/工具使用等推理能力）
- 生产部署已汇聚到**rollout-training 解耦**：推理优化 GPU（H20）用于 rollout，计算优化 GPU（H800）用于训练
- 但解耦引入了<b>依赖气泡</b>：rollout 阶段强制训练集群空闲，反之亦然——**两个池都被浪费**
- 现有系统通过切换到异步 off-policy 算法来消除 bubbles → 牺牲了模型准确率和收敛稳定性

### 为什么现有方法不够
- Monolithic provisioning：资源错配（训练 GPU 做 rollout 浪费计算）
- 仅解耦（不做额外优化）：依赖气泡使两个池的利用率都低
- Async/off-policy 替代同步 on-policy：放弃严格性能要求以获得效率——在关键任务中不可接受

## 方案介绍

### Weave：三层设计

**1. Co-execution group abstraction**
- 将集群划分为**隔离的局部域**——一个 group 是多作业的集合单元
- 在 group 内，作业 A 的 rollout 与作业 B 的 training **交错执行**——填充对方的依赖 bubble
- Group 的大小由**residency constraint**决定：所有成员作业的模型状态必须适合每个 worker 的主机内存

**2. Inter-group scheduler（组间）**
- 使用**保守随机规划**优化作业跨组的放置
- 考虑随机的 rollout 序列长度——为每阶段做保守预算以确保 SLO

**3. Intra-group scheduler（组内）**
- 编排**可证明最优的轮询调度**——保证 SLO 的同时最大化利用
- 每个 group 内的交错模式是确定性的（可提前知道）

### 关键设计决策

- **状态化 Workers**：每个 worker 持有数百 GB 的驻留模型状态——在同一个 group 中的作业间"热启动"上下文切换
- **模型拷贝乘数器**：将一个模型副本通过跨作业的慢速通信通道传输，避免重复加载
- **SLO 优先**：保守规划确保即使在随机序列长度变化下也能达成 SLO

## 证据与评估

| 指标 | 结果 |
|------|------|
| 对比标准解耦（仅 disagg，无 co-sched） | 成本效率 +**1.84×** |
| 对比 SOTA co-located baseline | 成本效率 +**1.38×** |
| SLO 达成率 | **100%** |
| 测试床 | 生产规模：**328 H20 + 328 H800** GPU |
| 工作负载 | 数学模型、编程、工具使用 RL 后训练 |

## 整体评估

### 真正的新意
1. **首次将 dependency bubble 概念化并作为一等系统问题**：RL 后训练中解耦架构内的结构空闲不是边缘情况——它是设计固有的
2. **Co-execution group 作为正确的中层抽象**：在单个作业（过于细粒度）和整个集群（过于粗粒度）之间——隔离的局部域使状态管理变得可行
3. **通过 conservative planning + res constraint 处理随机性**：RL 序列长度不可预测，但 SLO 仍然可保证

### 可复用启发
- "Dependency bubble"是一个通用概念，适用于任何有两个交替阶段跨不同资源池的管道（不仅是 RL——生成式 AI 的预取-生成、ML 训练中的前向-反向、MapReduce 中的 map-reduce）
- "Co-scheduling across pools"是解耦系统的正确调度抽象——不仅优化单个池，而是优化交叉池的依赖链
- 对于状态化热启动，residency constraint 是关键设计约束：必须决定一个 worker 能"记住"多少个作业
