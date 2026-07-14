# Spice(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-holmes.pdf
- **类型**: 论文-OS/系统
- **一句话 TL;DR**: SHELF 格式 + spliceVMA 内核原语解耦快照的物理存储布局与进程虚拟内存布局，冷启动恢复仅比热启动慢 0.6-18ms（vs 现有系统 3.6-1197ms），端到端延迟平均降 7.5×（vs process snapshot）和 9.5×（vs VM snapshot）。

## 核心问题

Serverless 冷启动延迟是弹性的根本限制——81% 应用每分钟最多调用一次，60% 函数冷启动多于热启动。最有效方案是快照恢复（函数初始化后 snapshot→下次从磁盘恢复），但**现有 OS 缺乏快照恢复支持**：内存原语（mmap/madvise）为增量进程启动设计→强制在高效磁盘布局和廉价虚拟地址重建之间做 trade-off；内核缺少 bulk-restore 机制→用户态用大量细粒度 syscall 逐个重建→慢。

## 关键洞察

1. **"SHELF 格式 + spliceVMA 解耦物理布局和虚拟布局"**：磁盘上的 snapshot 可以稀疏且乱序→无需复制到物理内存完美契合虚拟布局→spliceVMA 在内核中一次性 bulk 重建 VMA。类似 VTC 的 "virtual tensor index mapping"——物理层级和逻辑层级解耦。
2. **"snapshot + working set 分离 = 避免不必要的 I/O"**：只恢复 working set pages→其余 lazy fault→类比 SSD 的冷热分层。
3. **"Bulk metadata restore 替代逐个 syscall"**：现有 CRIU 等用大量 mkdir/setrlimit/prctl 等 syscall 重建进程状态→Spice 一次内核调用完成。

- 来源：Spice(OSDI'26)

### 实践启发
- **"物理-逻辑解耦是最强大的优化之一"**：类似 VTC 的 virtual tensor、InfiniDefrag 的 GPA-HPA remap——出现于存储/虚拟化/编译器等多领域
- **"OS 为 serverless 重新设计内存原语"**：现有 mmap/madvise 为传统进程设计→serverless 需要自己的 snapshot restore 原语
