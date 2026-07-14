# PowerSight(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-li-ruihao.pdf
- **类型**: 论文-系统（Operational Systems）
- **一句话 TL;DR**: Meta 十年数据中心电源规划实践经验——硬件生命周期感知的机架功率超额订阅方法论（~20% oversubscription）+ PowerSight ML 模型在无功率传感器时预测系统功耗（MAPE 3.81-7.89%）。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| Hardware Lifecycle | 服务器从 pre-silicon 到 decommission 的完整阶段序列（Pre-EVT→EVT→DVT→PVT→MP→MP+1yr） | 核心框架——不同阶段可用数据不同，电源规划策略需相应调整 |
| Design Power (D) | 最恶劣工作负载下服务器的峰值功耗 + TOR 交换机等开销 | 保守的电源规划基准——所有服务器同时峰值的理论上限 |
| Rack Power Budget (RPB) | 峰值流量 + 最坏故障场景下机架的期望功耗 | 替代 Design Power 的实际规划值，本文核心优化目标 |
| Rack Density (n) | 不超过 Design Power 能部署的最大服务器数 | 电源规划的关键输出——决定每个机架放多少台机器 |
| CR (Inter-workload Max Correlation Score) | 各工作负载峰值之和 / 任意时刻总功耗最大值 | 量化"时间多样性"带来的 power buffer——CR > 1 即可超额订阅 |
| Power Oversubscription | RPB < Design Power，利用工作负载的时间和空间多样性 | Fleet-wide 平均约 20%，相当于多部署 ~20% 机架 |
| Forecast RPB / Initial RPB / Refined RPB | Pre-EVT→DVT / PVT→MP / MP+1yr 的 RPB 版本 | 三阶段递进：电气规格估算→负载测试校准→fleet-wide 数据精化 |
| PowerSight | 基于 MLP 的功耗预测模型，输入 perf counters + machine configs，输出 system power | 在无功率传感器的早期阶段（Pre-EVT→DVT 18 个月窗口）预测功耗 |
| MAPE (Mean Absolute Percentage Error) | 预测误差的百分比均值 | PowerSight 跨架构预测新平台的误差：7.89%（MLP）vs 9.39-11.26%（DT/GBDT） |
| SPEC CPU2017 vs Hyperscale workloads | 标准 benchmark 平均达 75.5% Design Power vs hyperscale 85.6% | SPEC 低估系统功耗 11.8%，因其 memory/uncore 压力不足 |

## 背景与动机

Meta 数据中心同时运行数代硬件（最老和最新可差 5+ 年），服务数千种工作负载。传统电源规划基于 Design Power（最坏情况峰值），但实际中：
- 不同工作负载的功耗差异巨大（20-90% Design Power）
- 不同服务的峰值功耗出现在不同时间
- CPU 功耗效率代际提升 ~2×，但内存功耗仅 ~1.2× → 内存占系统功耗比例持续增长

**核心矛盾**：新硬件引入时（Pre-EVT，量产前 2-3 年），必须做出电源规划决策（是否需要建新数据中心？），但功率传感器数据要到 DVT/PVT（量产前 6 个月）才有。

## 问题定义

**如何在硬件生命周期的各个阶段（从 pre-silicon 到 mass production+1 年）制定准确的机架电源预算（RPB），实现安全的功率超额订阅，并在缺乏功率传感器数据的早期阶段预测系统功耗？**

## 方案介绍

### 1. 功耗特征化研究（§3）

以 Meta 数百万服务器、数千服务、8 代 CPU + 2 代 GPU 的 live production 数据为基础，关键发现：

| 发现 | 数据 | 含义 |
|------|------|------|
| SPEC 低估系统功耗 | SPEC 75.5% vs 生产 85.6% Design Power | 仅靠 benchmark 做电源规划会低估 11.8% |
| Core power <50% 系统功耗 | 生产 web service 中 core 不到一半 | 不能只看 CPU/GPU——memory、NIC、fan 都很重要 |
| 服务间功耗方差大 | 20-90% Design Power | 所有服务器同时峰值的概率极低 |
| 内存功耗占比持续增长 | DDR5 vs DDR4 仅 ~1.2× 改善，CPU ~2× | 内存感知的电源管理越来越重要 |
| 无单一指标可决定系统功耗 | CPU util 与系统功耗的 R² 随代际变化大 | 需要多指标（CPU+mem+IO+GPU）综合模型 |

### 2. 硬件生命周期感知的 RPB 方法论（§4）

```
RPB = (Σ fw × pw) × n + PTOR          (Initial RPB, 基于负载测试)
RPB = (Σ fw × pw) / CR × n + PTOR     (Refined RPB, 基于fleet-wide数据)
```

三阶段递进：
- **Forecast RPB**（Pre-EVT/EVT/DVT）：仅有电气规格 → 用历史经验 derating factors → 实现 ~13% oversubscription vs Design Power
- **Initial RPB**（PVT/MP）：有硬件 + 可负载测试 → 服务 owner 确定目标利用率 + 功耗-利用率曲线 → 得到 pw
- **Refined RPB**（MP+1yr）：有 fleet-wide 功率传感器数据 → CR 量化时间多样性 → 额外 ~11% oversubscription → 总计 ~20% vs Design Power

### 3. PowerSight：早期阶段的 ML 功耗预测（§5）

**输入**：Performance counters（IPC, cache misses, DRAM/NIC accesses, GPU SM util...）+ Machine configs（core count, cache sizes, DIMM channels, HBM size...）

**输出**：System power（连续值）

**模型选择**：评估 6 种模型 → MLP 最优（跨架构泛化 MAPE 7.89%，DT 9.39%，GBDT 11.26%）

**关键设计决策**：
- 排除 kernel-level GPU counters（profiling overhead 太高，不适合 fleet-wide 部署）
- PCA 聚类选特征 → 全量特征 vs 精简特征的精度差 <0.1%
- 需要至少 millions 级数据点才能达到可用精度（<10% MAPE）

**三个用例**：
1. **Rack Density 预测**：MLP 预测 Design Power MAPE 1.7% → 机架密度估算误差 8.7%
2. **RPB 预测**：在 PVT 早期无功率传感器时预测，误差 2.5%
3. **最优 Perf/W 频率搜索**：预测最节能频率范围（Video workload 实际最优 2.6GHz，PowerSight 预测 2.4-2.8GHz）

## 证据与评估

- **数据规模**：数百万服务器、数千服务、42 种机器配置、8 代 CPU + 2 代 GPU、live production traffic
- **RPB 方法论**：在 Meta 全球数据中心部署超过十年
- **Oversubscription 效果**：Fleet-wide 平均 ~20% → 同等电力基础设施多部署约 20% 机架
- **PowerSight 精度**：
  - 同架构预测：MLP MAPE ~4%（96%+ accuracy）
  - 跨架构预测（新 CPU+新 GPU 未见训练集）：MLP MAPE 7.89%
  - Rack density 预测误差：1.7%
  - RPB 预测误差：2.5%
- **训练数据量影响**：<10 万数据点 MAPE >10%，百万级才收敛到 <5%

## 整体评估

### 真正的新意
1. **首次提出硬件生命周期概念并给出各阶段的电源规划策略**：之前的研究都假设有生产数据可用
2. **将 ML 功耗模型用于实际数据中心电源规划**：之前 ML power modeling 停留在学术研究，本文展示了三个实际用例
3. **CR 指标量化时间多样性**：比"峰值之和 / 同时峰值"的直觉更严谨，可直接用于 RPB 公式

### 优点
- **真实生产数据**（数百万服务器、十年经验）→ 结论可信度极高
- **完整的端到端方案**：从早期 forecast 到 refined RPB，覆盖整个硬件生命周期
- **PowerSight 仅需 perf counters + config**——这些都是现有基础设施可提供的（dynolog），不需要新硬件
- **方法论对 AI 工作负载也适用**：训练/推理 rack 的 power profile 不同（GPU rack 时间方差更小），但 RPB 公式框架通用

### 局限与假设
- PowerSight 跨架构预测误差 7.89% 对容量规划可接受，但对实时 power capping 不够精确
- 未考虑温度、冷却效率等环境因素（作者承认这是 future work）
- GPU 功率建模排除了 kernel-level counters，对 AI 训练功耗预测的精度可能低于 CPU 侧
- RPB 方法依赖服务 owner 配合负载测试——这在非 Meta 环境中可能不现实

### 适用条件
- 大规模异构数据中心（有多代硬件共存）
- 有 fleet-wide telemetry 基础设施（perf counters + power sensors）
- 新硬件采购和部署的 lead time 很长（18+ months）
- 电力基础设施是数据中心扩容的瓶颈

### 可复用启发
- **"Design Power 是虚假的上限"**：所有服务器同时峰值的概率几乎为零。任何多租户资源规划场景（不仅是电源，也包括网络带宽、存储 IOPS）都可以借鉴 CR 指标量化时间多样性。
- **"Benchmark 不可信"在电源领域同样成立**：SPEC CPU 低估系统功耗 11.8%——因为 hyperscale 工作负载的 memory/uncore 压力远超 benchmark。做电源规划必须用生产数据。
- **"功耗模型的精度-可部署性 trade-off"**：PowerSight 刻意排除 kernel-level GPU counters（profiling overhead 太高），牺牲少量精度换取 fleet-wide 可部署性。这是"scale over precision"的务实选择。
- **硬件生命周期的阶段化思维**：不同阶段可获取的数据不同 → 不同阶段应有不同的规划方法。这个框架可推广到任何"新硬件引入"场景（如新 GPU 型号的性能预测、新存储介质的容量规划）。
- **内存功耗占比持续增长是跨代趋势**：不仅是 Meta 的数据，也符合行业趋势（HBM 功耗、CXL 内存功耗）。未来数据中心电源管理必须从"以 CPU 为中心"转向"系统全组件视角"。

### 讨论问题
- CR 指标假设各工作负载峰值独立，如果未来 AI 训练作业被集中调度（同步峰值），CR 是否会趋近 1？
- PowerSight 的跨架构泛化是否依赖于同一厂商的 ISA 连续性（都是 x86）？跨 ARM/x86 预测还能保持精度吗？
- 20% oversubscription 在当前是安全边界，但随着服务器功耗密度增长（单机架 >100kW），这个安全边际是否会被压缩？
