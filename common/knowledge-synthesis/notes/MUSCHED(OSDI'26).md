# MUSCHED(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-xiao.pdf
- **类型**: 论文-运维系统 (Operational Systems)
- **一句话 TL;DR**: Honor 手机语义感知调度——识别跨进程 IPC 依赖链将交互关键线程提升到 VIP 调度类（RT 和 CFS 之间），eBPF 用户态可插拔策略无需内核重编译。20M+ 设备部署，冷启动异常 -30.7%。

## 核心问题

移动 CPU 调度的 "不可能三角"：稀缺的 prime core + 跨进程 IPC 依赖链 + tight 延迟截止。内核调度器缺乏用户交互上下文→将 UI render 线程和后台线程同等对待→交互卡顿。单次触摸触发跨越 app→system server→kernel 的 IPC 链，高优先级 UI 线程可能在等低优先级后台服务（优先级反转）。

## 关键洞察

1. **"语义感知调度——跟踪交互路径上的跨进程依赖链"**：不是给单个线程提权，而是提升整个交互依赖链的执行紧迫度。类似 GOODKIT "lock-aware consistency"——理解系统语义而非仅看线程状态。
2. **"VIP 调度类：介于 RT 和 CFS 之间"**：避免 RT 的完全抢占（可能饿死后台），但给予高于 CFS 的优先权→交互关键任务可抢占普通后台而不威胁系统稳定性。
3. **"eBPF 用户态可插拔策略"**：不需要内核重编译→适应 COTS 移动设备。类似 vBPF "late-binding eBPF"——用户态可编程性打破内核策略的 one-size-fits-all。

- 来源：MUSCHED(OSDI'26)
