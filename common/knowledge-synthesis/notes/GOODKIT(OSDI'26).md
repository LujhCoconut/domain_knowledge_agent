# GOODKIT(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-teguia.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: VM 自省的新范式——观察器作为轻量 VM 与目标共享 VMM 进程，native-speed 访问目标内存，比 LibVMI 快 up to 110×，目标端 overhead 最多 1.06×（LibVMI 5.15-37.6×）。

## 核心问题

VM 自省 (VMI) 是云安全的基础——检测 rootkit/勒索软件/性能异常。现有三种部署位置各有致命缺陷：超visor 内（扩大 TCB）、单独 VM（LibVMI——需要 pause VM + 多次 kernel-userspace crossing→慢 5-37×）、guest 内（guest 被攻破后无效）。**没有任何方案同时满足快速、强隔离、不修改 hypervisor。**

## 关键洞察

1. **"Observer VM 与 target VM 共享同一 VMM 进程"**：VMM（如 QEMU）已经是用户态进程，持有 target VM 的完整内存映射。将 observer 也作为轻量 VM 跑在同一 VMM 下→直接 mmap target 内存→native-speed 访问。无需修改 hypervisor（KVM 不改）。
2. **"Lock-aware 内存一致性"**：不像 LibVMI pause 整个 VM→GOODKIT 理解内核锁状态→在安全时刻捕获一致性快照→不暂停 target。
3. **"Mutualization layer"**：多 observer 共享公共自省工作→减少对内核数据结构的竞争。

## 可复用启发
- **"Insider observer VM"**：共享 VMM + mmap target memory = 零拷贝 VM 自省。类似 CoPilotIO 的 "split SQ/CQ"——找到两个域之间的高效共享点
- 来源：GOODKIT(OSDI'26)
