# Kareus(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-wu-ruofan.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: Kareus 联合优化大模型训练的静态和动态能耗——通过精细控制 SM 分配、通信 kernel 启动时机和 GPU 频率，比 Perseus 最高再节省 28.3% 能耗或减少 27.5% 训练时间。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| Dynamic energy / Static energy | 动态能耗 = 芯片实际工作消耗（与频率、电压平方相关）；静态能耗 = 芯片上电即消耗（与时间成正比） | 本文的关键分析框架——动态能耗主要受频率影响，静态能耗主要受执行时间影响 |
| Execution schedule | 三要素的组合：(1) 通信 kernel 启动时机 (2) 通信 kernel 的 SM 分配数 (3) GPU 频率 | 核心发现：三者联合且互为依赖地决定时间和能耗 |
| Partitioned overlap | 将 microbatch 的前向/反向 pass 划分为重复的通信+计算分区 | 把全局搜索空间（85K configs）分解为 local subproblem 的 key idea |
| SM allocation | 分配给通信 kernel 的 SM 数量 | 过多→争抢计算 SM、延长总时间；过少→通信暴露、静态功耗浪费 |
| Exposed communication time | 通信 kernel 完成前计算 kernel 已全部执行完毕的时间窗口 | 此时大量 SM 空闲但仍在耗电——静态功耗浪费 |
| Nanobatching | 将 pipeline microbatch 拆分为两个无依赖的 nanobatch，stagger 执行以 overlap 通信和计算 | Kareus 的前身之一，但没有 SM 分配控制和频率联调 |
| Multi-objective Bayesian Optimization (MBO) | 多目标贝叶斯优化，同时搜索时间和能耗的 Pareto 前沿 | Kareus 的核心优化器——四轮 pass 从不同方向扩展前沿 |
| Hypervolume Improvement (HVI) | 候选配置能将当前 Pareto 前沿向外扩展的体积 | MBO 的 exploitation metric——total/dynamic/static 三种 HVI 覆盖不同方向 |
| Thermally stable profiler | 5s 重复执行 + 5s cooldown，确保 GPU 温度 <32°C | 防止前一配置的 GPU 发热影响后一配置的能耗测量 |
| GPU frequency throttling | GPU 硬件在功耗过高时自动降频 | Nanobatching 提高 GPU 利用率 → 瞬时功耗触发热 throttling → 平均频率反而降低 → Kareus 通过固定频率避免此问题 |

## 背景与动机

大模型训练的能耗增长远超电力供给增长——预计 2035 年美国近 10% 电力将用于数据中心，而能源采购周期极长（天然气 3 年、核电 5-10 年）。现有优化工作各自为战：
- **Perseus**：降低 off-critical-path 的 GPU 频率 → 减少动态能耗，但忽略静态能耗和 kernel 调度
- **Nanobatching**：重叠通信和计算 → 减少静态能耗（缩短时间），但忽略动态能耗和频率影响

**简单的 Perseus + Nanobatching 组合不能达到最优**——因为 SM 分配、频率、启动时机三者互为依赖。

## 问题定义

**如何联合优化 SM 分配、kernel 启动时机和 GPU 频率，找到大模型训练的时间和能耗 Pareto 最优执行 schedule？**

搜索空间极大（85K candidates），每个需 ~13s 稳定测量（thermally stable），穷举需 4,912 GPU-hours。

## 方案介绍

### 核心洞察

**Execution schedule 的三要素互为依赖，改变一个会改变其他要素的最优配置。**关键发现：

1. **SM 分配存在"中间最优点"**：太少→通信暴露时间浪费静态功耗；太多→抢走计算 SM、自身几乎空闲→更糟
2. **重叠的对象比重叠本身更重要**：通信 kernel 和 memory-bound kernel（Norm）一起跑会争抢内存带宽，和 compute-bound kernel 一起跑抢 SM——影响完全不同的选择
3. **低频改变最优 schedule**：低频率使所有 kernel 变得相对更 compute-bound（频率只影响计算速度、不影响内存/通信带宽）→ 改变了哪些 kernel 应该与通信重叠
4. **恒定频率比频率波动更节能**：GPU 功耗控制器的频率波动导致高功耗期的能耗浪费 > 低功耗期的节省（动态功耗 ∝ f³）

### 架构

```
Workload → 自动分区 → Per-partition MBO → 组合 Frontier → 运行时选择 Schedule → 执行引擎
```

### Partitioned Overlap Execution Model

将 Transformer block 的 forward/backward 划分为重复的通信+计算分区。每种分区类型（如 Attention-AllReduce、MLP-AllReduce）独立优化，**但强制同类型分区共享相同配置**（避免指数级搜索空间膨胀）→ 将全局 search 分解为 local subproblems。

### MBO 算法

决策变量：(1) SM 数 (2) 启动时机 (3) GPU 频率

**两个 Surrogate Models**：T̂(x) 预测时间 + Ê(x) 预测动态能耗。用 XGBoost（因处理离散/类别变量好、训练快）。

**四轮 Multi-pass Candidate Selection**：
| Pass | Acquisition | 方向 |
|------|-------------|------|
| Total energy | HVI(总能耗) | 向原点 (更快 + 更省电) |
| Dynamic energy | HVI(动态能耗) | 更低能耗（低频方向） |
| Static energy | HVI(静态能耗) | 更低时间（更少静态浪费） |
| Uncertainty | Bootstrap ensemble std | 探索未覆盖区域 |

### Thermally Stable Profiling

- 5 秒重复执行（NVML 采样 ~100ms，millisecond-scale 误差大）
- 配置间 5 秒 cooldown（功耗测量对温度敏感）
- 单 candidate ~13s

### 几个巧妙设计

- **频率在 microbatch 内统一**：频率切换需数 ms，与 partition latency 可比 → 所有 partition 同频
- **自动回退到 sequential execution**：当 nanobatch 太小导致 GPU 欠利用时，Kareus 自动选择不拆分的执行模式
- **连续 memory-bound kernel 合并**：如 BiasDropoutAdd + Norm → 视为一个逻辑操作，避免启动时机搜索空间膨胀
- **多通信 kernel 融合**：如 context parallelism 下多个 AllGather → 合并为一个共享 SM 分配的 kernel

## 证据与评估

### 测试设置
- 16×A100 40GB，2 节点
- 真实训练：Llama 3.2 3B、Qwen 3 1.7B
- 大规模模拟：Llama 3.3 70B
- 14 种 workload 配置（TP8/CP2TP4 × various microbatch/seqlen）
- Baselines: Megatron-LM / M+Perseus / Nanobatching+Perseus

### 关键结果

1. **Max-throughput 对比** (Table 3)：Kareus 比 Megatron-LM 减少 **up to 14.9%** 时间 + **22.1%** 能耗，在所有配置上严格优于 baselines
2. **Frontier 改进** (Table 4)：比 M+Perseus 的 iso-time 能耗减少 **up to 28.3%**，iso-energy 时间减少 **up to 27.5%**
3. **Kareus 自动发现一个反直觉配置**：Qwen 1.7B TP8 上，Kareus 发现在 1,350 MHz（非最高频 1,410 MHz）反而最快——因为 1,410 MHz 下 overlap 导致瞬时功耗触发 GPU throttling，平均频率反而接近 1,350 MHz，但平均功耗仍是 1,410 MHz 的水平
4. **Nanobatching 可能比 sequential 更差**：Qwen 1.7B CP2TP4 mb=8 seq=4K 上，Nanobatching+Perseus 时间增加 20.4%、能耗仅降 3.1%——因为 GPU 欠利用时拆分 microbatch 进一步降低了算术强度。Kareus 自动回退到 sequential 模式避免了此问题
5. **MBO 收敛**：每个 partition 的 MBO 在 ~200 evaluations 后收敛，开销 ~2.3 GPU-hours/partition

## 整体评估

### 真正的新意
1. **"Execution schedule 三要素应联合优化"是此前被忽视的 fundamental insight**：Perseus 只看频率、Nanobatching 只看 schedule——两者 naive 组合是次优的
2. **Partitioned overlap 模型**：用 "同类型分区共享配置" 的约束把全局搜索变成多个局部搜索，在 expressiveness 和 tractability 之间找到平衡
3. **Multi-pass MBO**：四个 pass 从不同方向扩展 Pareto 前沿（total/dynamic/static/uncertainty），是系统领域首次系统化使用多目标 BO 同时搜索时间和能耗

### 优点
- 理论与实现的一致性：从 case study (§3) 到 MBO (§4) 到实现 (§5) 到评估 (§6) 形成完整闭环
- 自动回退 sequential 执行是务实的——不是所有场景 overlap 都更好
- 发现了 "恒定低频 > 高频波动" 的实践洞察——对理解 GPU power management 有超出本文的意义
- 开源 + 与 Megatron-LM/Perseus 兼容

### 局限与假设
- **GPU 功耗模型简化**：假设静态功耗恒定（实际有 temperature/voltage 依赖），需要未来扩展到更精细的模型
- **MBO 的 profiling 开销**（~2.3 GPU-hours/partition）对每次部署都重新 profile 可能不现实——需要研究跨模型/跨硬件迁移
- **当前仅在单 partition type 内优化**，跨 partition type 的联合优化空间仍有未探索部分
- A100 特定——频率 throttle 行为在 H100/B200 上可能有不同表现

### 适用条件
- 大模型训练（GB 级以上通信开销显著的场景——partitioned overlap 的收益与通信量成正比）
- 有能量预算或时间预算约束的训练作业
- 多种 parallelism 的组合（TP+CP+PP）——越复杂的通信模式，Kareus 的相对收益越大

### 可复用启发
- **"恒定频率 > 频率波动"的能耗优势**：动态功耗 ∝ f³，频率波动的不对称成本意味着恒定频率策略优于响应式频率调整。这不仅适用于 GPU 训练，也适用于任何有 DVFS 的计算场景。
- **"重叠什么"比"重叠多少"更重要**：通信 kernel 与 memory-bound kernel 重叠（争内存带宽）vs 与 compute-bound kernel 重叠（争 SM）——资源竞争维度不同，效果完全不同。做 compute-communication overlap 优化时必须关心两者的资源需求类型。
- **"大搜索空间可以通过结构约束分解"**：Partitioned overlap 的核心智慧——识别重复结构并强制同类 partition 共享配置，使指数级空间变为可管理。适用于任何有重复模式的调度问题。
- **BO 做多目标时需要多方向的 acquisition**：单方向 HVI 只会扩展前沿的一个方向；四轮 pass（total/dynamic/static/uncertainty）的设计可推广到任何多目标 BO 系统问题。
- **"能耗测量的温度敏感性"不可忽视**：GPU 功耗随温度漂移很小但足够影响 Pareto 前沿的准确性——需要 cooldown 和重复测量。
- 来源：Kareus(OSDI'26)

### 讨论问题
- Kareus 的 MBO 发现的 schedule 能否迁移到不同 GPU 型号（A100→H100）而无需重新 profile？
- Partitioned overlap 能否推广到 non-Transformer 架构（如 SSM/Mamba）——这些模型的通信模式不同？
- 是否可能与 BatchGen 或 UEP 集成——BatchGen 优化批量推理的调度、UEP 优化 EP 通信可移植性、Kareus 优化训练能耗？
