# Cloud Infrastructure & Virtualization

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| vCPU 调度与超卖 | mwait-passthrough, oversubscription, steal time, VM exit, idle visibility | mwait-sched(OSDI'26) |
| 内核性能常量在线调优 | perf-const, Scoped Indirect Execution (SIE), critical span, side-effect safety | Xkernel(OSDI'26) |

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
