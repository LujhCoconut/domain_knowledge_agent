# FARLock(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-hu-yuehao.pdf
- **类型**: 论文-协议/算法
- **一句话 TL;DR**: 首个保证公平性的 RDMA 非对称锁——ticket + MCS handover + 读写优化扩展，保持高性能同时严格 FCFS 排序。

## 核心问题

RDMA 原子操作在本地访问时需绕道 RNIC（避免 CPU 直接竞争）→ 开销大。非对称锁（本地用 CPU CAS、远程用 RDMA CAS）性能好但**破坏公平性**——本地请求插队远程请求。

## 方案

- **Ticket lock style**：按到达顺序发 ticket → 严格 FCFS
- **MCS-style handover**：token 传递避免轮询
- **Optimistic reader lock extension**：只读请求轻量旁路
- 保持非对称的性能优势 + 首次同时保证公平性

## 可复用启发
- **"Ticket + handover"模式使非对称锁公平化**——与 Arctic 的并发数据结构形成互补（Arctic 做无锁结构，FARLock 做带公平性的锁）
- 来源：FARLock(OSDI'26)
