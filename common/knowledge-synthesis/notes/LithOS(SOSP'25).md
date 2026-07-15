# LithOS(SOSP'25)

- **来源**: SOSP '25, doi:10.1145/3731569.3764818 (arXiv:2504.15465)
- **作者**: Patrick H. Coppock, Brian Zhang, Eliot H. Solomon, Vasilis Kypriotis (CMU), Leon Yang, Bikash Sharma, Dan Schatzberg (Meta), Todd C. Mowry, Dimitrios Skarlatos (CMU)
- **类型**: 论文-系统/GPU OS
- **一句话 TL;DR**: 首个 GPU OS——将 CPU OS 抽象（time-sharing、空间调度、隔离、DVFS）移植到 GPU。TPC 级调度 + 透明 kernel 原子化(Prelude kernel) + 两点 Amdahl 插值 right-sizing + 频敏度引导 DVFS。SLO 100% + throughput 1.0× vs MPS throughput 1.08× but SLO 42%。Quarter GPU capacity 节省(<4% hit), quarter GPU energy 节省(7% hit)。

## 核心问题

Meta 生产 Ads 推理集群 GPU 利用率仅 27%（SM 利用率更只 14%），Microsoft 52%，Alibaba 10%。根因不是硬件慢，而是 GPU 缺乏 OS 级资源管理——现有方案：(1) NVIDIA MPS 空间共享但无 isolation、SLO 仅 42%；(2) MIG 强隔离但静态粗粒度分区（GPC 级，>5s 重配）；(3) 学术方案(Orion/REEF/TGS)需框架修改或 offline profiling——在快速演化的 ML 生态中不可行。核心矛盾：**spatial sharing 提升利用率但损伤 LC SLO，static partitioning 保护 SLO 但浪费资源**。

## 关键洞察

1. **"TPC 级调度 = GPU 的 core-level scheduling"**：H100 有 8 GPC × 9 TPC × 2 SM = 72 TPCs，每个 TPC = 2 SM。以 TPC 为调度粒度→类似 CPU OS 以 core 为调度粒度→可实现 per-app TPC quota（guaranteed）+ TPC Stealing（idle TPCs 被 steal→work conservation）。比 MIG 的 GPC 级粒度细化 9×。

2. **"Prelude kernel = 透明 kernel 原子化"**：无编译器/PTX/源码修改，通过注入 Prelude kernel（Algorithm 1: 检查 `block_idx` 是否在 atom 的 block range 内→是则调用原 kernel，否则 early exit）将 64-thread-block kernel 拆为 2-64 个 atoms。每个 atom 是 kernel 的 thread block 子集→在 atom 边界可重分配 TPC→实现 GPU "伪抢占"。Atom duration 由 tunable `atom_duration` 参数控制。

3. **"两点 Amdahl 插值 = 轻量 right-sizing"**：仅测 1 TPC 和 all TPCs 两次 latency→拟合 `l = m/t + b`（m=并行部分, b=串行部分）→计算 saturating TPC 数。关键发现：**per-kernel right-sizing >> whole-model right-sizing**，因为不同 kernel scaling 行为差异极大（部分线性、部分快速饱和）。k-slack 参数控制性能损失上限。

4. **"频敏度引导 DVFS = 差异化能耗管理"**：内存密集 kernel（低频敏度）降频→计算密集 kernel（高频敏度）保高频。GPU 频率切换延迟 ~50ms→LithOS 采用保守策略（高 learning period + 从 max freq 渐进降）。类似 right-sizing 使用 k-slack 控制性能上限。

5. **"Launch queue + Sync queue 解耦 = OS 级调度控制"**：应用提交 kernel 到 launch queue→LithOS 不在提交时立即 dispatch→延迟到 scheduler 决策后再 dispatch→类似 CPU OS 的 runqueue。Sync queue 跟踪 outstanding work→当 backlog 超阈值时 throttle 提交→防止 GPU starvation。

- 来源：LithOS(SOSP'25)

## 实践启发

- **"OS 抽象移植到 GPU 是 paradigm shift"**：CPU OS 的 core scheduling、work stealing、quota、DVFS 在 GPU 上同样有效。LithOS 是证明这件事的 first system
- **"Kernel atomization = GPU 的 time-sharing primitive"**：GPU 无硬件 timer interrupt→Prelude kernel 以软件方式实现 "伪抢占"→在 atom 边界重新分配 TPC
- **"Spatial isolation + temporal flexibility = 两者兼得"**：MPS 有 throughput 无 SLO，MIG 有 SLO 无 utilization，LithOS 的 TPC quota + stealing 同时满足：SLO 100% + throughput 1.0（接近 MPS 的 1.08）
- **"Transparency = no ML stack modifications"**：LibLithOS 替换 CUDA library→对 PyTorch/TensorRT/JAX 全透明。ML 框架每几个月大版本迭代→非透明方案必然 lock-in outdated stack
