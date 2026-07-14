# Concurrent Data Structures

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 无锁自适应基数树 | lock-free ART, freezing-based coordination, hazard keys SMR, range scans, 128-bit CAS | Arctic(OSDI'26) |
| 公平 RDMA 分布式锁 | asymmetric RDMA locking, ticket lock, MCS handover, FCFS fairness, optimistic reader | FARLock(OSDI'26) |

---

## 无锁自适应基数树

### 核心问题
现有索引结构无法同时满足三个属性：高性能（超过锁-based alternatives）、lock-freedom（在有更多线程比物理核心时仍能 progress）、和高效的 range/prefix scans。Hash maps 不支持 range scan；skiplists cache locality 差；B+-trees 的 lock-free 版本（Bw-tree）性能显著差于 optimistic lock coupling；ART 是锁-based 的。

### 关键洞察

1. **Freezing-based coordination** 实现 lock-freedom 同时保持 in-place update：节点更新前先"冻结"目标区域——不需要 RCU 的 extra pointer indirection
2. **Hazard keys**：用 operation key 近似 reachable pointer set——在操作开始时一次性宣布 key，替代传统 hazard pointers 的 per-pointer deref 开销
3. **128-bit CAS** 是 practicality 的边界——Arctic 需要 128-bit atomic CAS（correctness）+ 128-bit atomic load（reasonable performance）
4. 在 80 线程下 YCSB-A 比 lock-based ART 高 **7.7×**（geomean 1.3-7.7× across 7 key distributions）
- 来源：Arctic(OSDI'26)

### 实践启发
- Key-based SMR 适用于任何基于 key 的树索引：key 可以近似 reachable pointer set
- "冻结"协调优于 RCU 或 per-node locks 的一个反直觉结论：freezing protocol 同时实现 lock-freedom 和 in-place update
- 在 RocksDB 和 Turso 中替换默认 skiplist 的实际效果（+40%, +12%）验证了 Arctic 的生产实用价值

---

## 公平 RDMA 分布式锁 (FARLock)

### 核心问题
非对称 RDMA 锁（本地 CPU CAS + 远程 RDMA CAS）性能优秀——利用本地访问的低延迟和 RDMA 的高吞吐。但本地请求可以插队远程请求→FCFS 公平性被完全破坏。数据库、KV store、分布式文件系统等需要公平锁来保证 SLO——不能接受关键查询因锁的不公平授予而被延迟。

### 关键洞察

1. **"Ticket + MCS handover 使非对称锁公平化"**：按到达顺序发 ticket→严格 FCFS；MCS-style token 传递避免轮询→保持高性能。
2. **"Optimistic reader extension"**：只读请求轻量旁路 ticket 队列——大部分工作负载是 read-heavy→较大性能提升。
3. **"First RDMA lock to guarantee fairness"**：之前 RDMA 锁要么公平但慢（对称），要么快但不公平（非对称）。FARLock 首次结合两者。

- 来源：FARLock(OSDI'26)

### 实践启发
- **"Fairness 不应是性能优化后的附加品"**：非对称锁的不公平性在生产系统中会导致不可接受的 tail latency
- **"Ticket-based ordering + local/remote dual-path"**可推广到任何非对称分布式协调原语
