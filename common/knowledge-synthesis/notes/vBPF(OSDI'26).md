# vBPF(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-zhang-jing.pdf
- **类型**: 论文-系统/安全
- **一句话 TL;DR**: eBPF 的 static-binding 模型强制多租户争抢共享物理 hook→vBPF 用 late-binding 虚拟化——Sniffer 归因中断事件+Dispatcher O(1) 查找替代线性遍历+编译辅助状态隔离，延迟降 3.9×，PostgreSQL 吞吐 +29%。

## 核心问题

eBPF 是云原生系统中的内核可编程性标准，但其 static-binding 模型隐含单一信任域假设。当多租户都有自己的 eBPF 程序时：struct_ops 只允许一个全局实现（平台 vs 租户二选一）、kprobe 的返回结果被其他租户静默破坏、多程序 attachment 争抢共享执行上下文→性能干扰。现有 filter/container isolation 只是绕过问题而非解决问题。

## 关键洞察

1. **"Late-binding 替代 static-binding"**：不是将程序在部署时固定绑定到物理 hook→物理 hook 作为通用拦截点→事件在运行时按租户属性动态分配。类似 VTC "virtual tensor"——物理 hook 不应与逻辑程序 1:1 绑定。
2. **"Sniffer 精确归因中断驱动事件到租户"**：中断事件不确定属于哪个租户→Sniffer 从硬件状态推断归属→使 late-binding 可行。
3. **"Dispatcher O(1) 查找替代线性遍历"**：多租户→大量程序 attached→线性遍历成为瓶颈→散列表 O(1) dispatch。类似 Ambulance "proposal lane"——消除线性瓶颈。

- 来源：vBPF(OSDI'26)

### 实践启发
- **"Static-binding→late-binding 是可扩展多租户系统中的通用问题"**：不仅是 eBPF——任何 shared resource 的 binding 模式都应设计为运行时解析
