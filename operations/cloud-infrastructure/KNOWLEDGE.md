# Cloud Infrastructure & Virtualization

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| vCPU 调度与超卖 | mwait-passthrough, oversubscription, steal time, VM exit, idle visibility | mwait-sched(OSDI'26) |
| 内核性能常量在线调优 | perf-const, Scoped Indirect Execution (SIE), critical span, side-effect safety | Xkernel(OSDI'26) |
| 嵌套虚拟化安全容器 | nested virtualization, Kata Containers, VMFUNC, EPTP switching, shadow-root, page-table decoupling | Janus(OSDI'26) |
| 嵌套 SEV 机密VM | AMD SEV, nested virtualization, emulation-less multiplexing, SEV context decoupling, two trust models | Nested SEV(OSDI'26) |
| 数据中心电源生命周期规划 | hardware lifecycle, RPB oversubscription, power characterization, ML power prediction, PowerSight | PowerSight(OSDI'26) |

---

## vCPU Idle 管理与超卖

### 核心问题
`mwait-passthrough` 将 guest 硬件 idle 直接透传——在 1:1 场景下完美（零 VM exit），但在超卖场景下 hypervisor 失明：idle vCPU 霸占 pCPU 不放，导致同核心其他 vCPU 被饿死。

### 关键洞察

1. **Passthrough 优化的双面性**：消除 VM exit 的同时也消除了 hypervisor 的可见性——在 1:1 下是净收益，在超卖下是灾难
2. **Steal time 不只来自"被活跃 VM 抢占"**：idle VM 占着 pCPU 不放是另一个被忽视的来源
3. **Timer 仿真 + idle 分类 + 多地址代理**的组合：恢复可见性而不引入频繁 VM exits
4. **生产数据揭示隐藏瓶颈**：CPU 利用率仅 5-10%，超卖却被限制在 1% — 不是因为用不完，而是 mwait-passthrough 在更高超卖比下触发大量 SLO 告警
- 来源：mwait-sched(OSDI'26)

### 实践启发
- 在超卖环境中，"passthrough" 优化需要特别小心——核心风险是可见性的丧失
- Steal time 作为性能退化信号需要精细解读：高 steal 可能来自竞争，也可能来自 idle 占用
- 3.2M pCPU 生产规模的数据驱动方法：先观测生产症状，再做受控实验复现

---

## 内核性能常量在线调优

### 核心问题
Linux 内核中大量性能关键常量（perf-consts）是"magic numbers"——基于过时硬件假设，在运行系统上完全不可调。现有机制（sysctl 仅覆盖预设常量；live patching 需分钟级延迟）。

### 关键洞察

1. **常量有结构，代码没有**：perf-const 进入机器状态的精确点可被静态分析识别，受影响的指令范围很短（critical span ~3-5 条指令）
2. **Scoped Indirect Execution (SIE)**：捕获 critical span 边界 → 生成合成指令以新值更新状态 → 保证 side-effect safety
3. **Side-effect safety 是新正确性准则**：live patching 仅保证 version atomicity（原子更新所有引用），但忽略了"新值与旧运行时状态是否冲突"
4. **50× 吞吐改善**：仅 tuning 一个 NIC interrupt batch size（以前不可调的常量）
- 来源：Xkernel(OSDI'26)

### 实践启发
- "magic number 不应是 magic"——内核常量值反映了开发时的硬件/负载假设，在部署场景中快速过时
- Side-effect safety（不仅是 version atomicity）应作为任何在线更新机制的必备属性
- 将任意内核常量转化为运行时可调 knob，是比"把每个常量逐一变成 sysctl"更 scalable 的解决方案

---

## 嵌套虚拟化安全容器 (Janus)

### 核心问题
安全容器（Kata Containers）在云VM上部署产生**不可避免的嵌套虚拟化**——CPU虚拟化和三级页表管理在两层hypervisor之间纠缠。传统设计导致频繁的跨world同步和中间页表管理开销，混合内存访问负载性能下降严重。

### 关键洞察

1. **"分离CPU和内存虚拟化职责"**：Guest hypervisor负责CPU调度（最了解guest behavior），Host hypervisor负责内存翻译（最了解物理内存布局）
2. **VMFUNC-based EPTP switching** 实现无trap的guest↔nested-guest地址空间过渡——Host从CPU事件关键路径移除
3. **Shadow-root机制**：保护world-switch集成的同时允许直接更新nested-guest页表——消除中间shadow/nested page tables
4. **In-guest VE handling**：二级fault在guest hypervisor内解决，仅需一次轻量级host交互
- 来源：Janus(OSDI'26)

### 实践启发
- "分离关注点"是嵌套系统最强大的设计原则——不仅是虚拟化，嵌套容器、嵌套沙箱都适用
- 硬件特性可以被重新用于非原始设计意图——VMFUNC的页表切换能力超越其原始用途
- "将Host从关键路径移除"是嵌套虚拟化性能优化的核心原则

---

## 嵌套 SEV 机密VM (Nested SEV)

### 核心问题
AMD SEV 被广泛采用（AWS/GCP/Azure 的机密VM），但嵌套虚拟化支持严重不足：Microsoft 补丁仅加密 L2 无法保护 L1、Hecate/OpenHCL 仅支持单个 L2 VM。当嵌套虚拟化用于虚拟云/测试环境/VM-in-VM 部署时，安全边界被打破。

### 关键洞察

1. **Emulation-less multiplexing**：不在不可信 hypervisor 中仿真AMD-SP，而是将多个 SEV context **超安全复用**到物理 AMD-SP——避免性能惩罚
2. **SEV context decoupling**：每个 L2 VM 拥有独立的加密上下文——与 L1 VM 的密钥分离
3. **两种信任模型覆盖实际部署**：L0+L1 untrusted（virtualization）和仅 L0 untrusted（passthrough）
- 来源：Nested SEV(OSDI'26)

### 实践启发
- "复用物理硬件而非仿真"是嵌套安全虚拟化的核心性能优化
- Context decoupling 是嵌套系统安全的关键原则：每层独立加密上下文
- 嵌套 SEV 填补了机密计算 + 嵌套虚拟化的交叉空白

---

## 数据中心电源生命周期规划 (PowerSight)

### 核心问题
超大规模数据中心同时运行数代硬件（新旧差 5+ 年）、数千种工作负载。传统电源规划基于 Design Power（所有服务器同时最坏情况峰值），但实际功耗变异巨大（20-90% Design Power），各服务峰值时间不重叠——Design Power 导致大量电力容量闲置。更关键的是，新硬件引入时（量产前 2-3 年）就必须做出电力规划决策（是否需要建新数据中心？），但功率传感器数据要到量产前 6 个月才可用——存在 12-18 个月的"数据真空期"。

### 关键洞察

1. **"Design Power 在所有服务器同时峰值的前提下成立，但现实中从不会发生"**：不同工作负载的峰值功耗出现在不同时间。利用这个时间多样性（通过 CR 指标量化），可以安全地将 RPB 设为低于 Design Power → Fleet-wide 平均 ~20% oversubscription，等于多部署 ~20% 机架。

2. **"不同阶段的电源规划需要不同的方法学"**——硬件生命周期框架：Pre-EVT（电气规格 + 历史 derating factors）→ PVT/MP（负载测试 + 功耗-利用率曲线）→ MP+1yr（fleet-wide 数据 + CR 指标）。不存在"一种方法适用所有阶段"的银弹。

3. **"SPEC 等标准 benchmark 系统性低估了 hyperscale 系统功耗"**：SPEC CPU2017 平均达 75.5% Design Power，而生产负载达 85.6%——差距 11.8%。原因是 SPEC 对 memory subsystem、uncore、NIC 的压力远低于真实 web service。做电源规划不能依赖 benchmark。

4. **"内存功耗占比持续增长是跨代趋势"**：CPU 能效代际提升 ~2×，但内存仅 ~1.2×。新平台 memory power 占比已 >20%。未来电源管理必须从"CPU 中心"转向"全系统组件视角"。

5. **"功耗模型的可部署性比绝对精度更重要"**：PowerSight 刻意排除 kernel-level GPU counters（profiling overhead 太高），用 perf counters + config 做预测。跨架构误差 7.89% 对容量规划够用，但 fleet-wide 可部署。

- 来源：PowerSight(OSDI'26)

### 实践启发
- **CR 指标可推广到任何"多用户共享有限资源"的容量规划场景**：不仅是电力，也包括网络带宽峰值、存储 IOPS 峰值。核心思想——"峰值之和 / 同时峰值"的比值 > 1 → 可超额分配。
- **"不要相信 benchmark 的功耗评估"**：SPEC 等 benchmark 的 memory/IO 压力远低于真实生产负载。做电源规划必须有生产数据——至少在 PVT 阶段用真实负载测试校准。
- **硬件生命周期的阶段化思维可以移植**：任何"新硬件引入但数据在后期才可用"的场景（新 GPU 型号性能预测、新存储介质寿命预测）都可借鉴 Forecast→Initial→Refined 的递进框架。
- **MLP 比树模型更适合跨架构泛化**：DT/GBDT 在同架构上表现好，但跨架构（新 CPU/GPU 未见训练集）时 MLP 明显更优（7.89% vs 11.26%）。选择模型不仅要看同分布精度，更要看 OOD 泛化能力。
