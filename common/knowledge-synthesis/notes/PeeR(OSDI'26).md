# PeeR(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-carin.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: eBPF 程序可抢占可调度——利用 verifier helper call 作为自然抢占点，budget check→超出则 yield 到 per-CPU kthread，两级调度（sched_ext 外环 + 微调度内环）。p99 latency 降 3-19.8×。

## 核心问题

eBPF 从微小包过滤器演变为复杂内核应用（KV store、负载均衡器、存储引擎→数十万条指令、数百微秒执行时间）。但执行模型未变：softirq 上下文中运行，**不可抢占**。三个根因：(1) eBPF 执行时间被计入被中断的 userspace 进程而非 eBPF 自己→不公平的 CPU 分配，colocated 工作负载被饥饿 (2) 长运行 eBPF 程序阻塞后续 invocation→尾延迟飙升（短请求等长 handler 完成→7.4× p99 升高）(3) 调度器对 eBPF 执行完全不可见→无资源控制。

## 关键洞察

1. **"Verifier helper call boundaries = natural preemption points"**：eBPF verifier 确保 helper 调用边界处程序状态干净→这些就是天然的协作抢占点。非平凡 eBPF 程序频繁调 helper→细粒度抢占机会。不需要修改内核调度器或重新设计 eBPF verifier。
2. **"Hybrid softirq-worker thread model"**：正常情况=softirq 路径（低开销）；超出预算→yield 到 per-CPU kthread 恢复执行→内核可见+可调度。类似 Ambulance "protocol-rigged racing"——leader 正常路径更快但 fallback 时无空等。
3. **"两级调度：sched_ext 外环 + 微调度内环"**：sched_ext 控制 eBPF workload 的总 CPU 时间（跨所有 eBPF 和其他应用），微调度器在 eBPF 内实现 operator-defined 排序策略。类似 vBOIDs "全局粗粒度+局部细粒度" 和 MUSCHED "VIP 类介于 RT 和 CFS"。

- 来源：PeeR(OSDI'26)
