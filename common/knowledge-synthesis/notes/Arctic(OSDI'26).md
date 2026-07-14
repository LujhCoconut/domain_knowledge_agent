# Arctic(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-ni.pdf
- **全称**: Arctic: a practical lock-free adaptive radix tree
- **作者**: Newton Ni, Nicolas Garza, Jenny Stinehour, Michael Goppert (UT Austin), Michal Friedman (ETH Zürich), Emmett Witchel (UT Austin)
- **类型**: 论文-系统 (concurrent data structures)
- **一句话 TL;DR**: 现有索引结构无法同时满足**高性能、lock-free 和无锁 range scans**。Arctic 是首个同时实现三者的 lock-free 自适应基数树：基于 ART 但用新的元数据布局 + freezing-based 协调协议实现 lock-freedom，在 80 线程下吞吐比 ART 高 **1.3× 到 7.7×**；贡献了 novel 的 **hazard keys** SMR 方案——用操作 key 近似可达指针，消除 per-pointer dereference 开销。集成进 RocksDB 写吞吐提升 **40%**，Turso **12%**。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **ART** (Adaptive Radix Tree) | 基于前缀的自适应基数树——根据 key 分布自适应节点大小 | Arctic 基于的基础结构 |
| **Lock-freedom** | 至少一个线程始终能取得 progress——即使某个线程被挂起或崩溃 | Arctic 的三个核心属性之一 |
| **Freezing-based coordination** | Arctic 的"冻结"协调协议——节点更新前先"冻结"目标区域，防止竞争冲突 |
| **Hazard keys** | 用 operation key 近似 reachable pointers，up front 一次性宣布——消除 per-pointer dereference 开销 | Arctic 的 novel SMR 方案 |
| **Hazard pointers (HP)** | 传统 SMR：每次指针解引用时宣布要保护的指针——开销高 | Arctic 的对比 baseline |
| **SMR** (Safe Memory Reclamation) | 确保在并发访问下安全释放内存的机制 | Arctic 的 hazard keys 属于 SMR |
| **Range scan** | 批处理读取一段连续的 key range——LSM compaction 和 DB index-only plans 的必需操作 | Arctic 支持 wait-free non-linearizable range scan |

## 核心贡献

| 贡献 | 说明 |
|------|------|
| **性能** | 80 线程 YCSB-A 比 ART 高 7.7×（geomean across 7 key distributions: 1.3× 到 7.7×） |
| **Lock-freedom** | 新 metadata 布局 + freezing protocol——no additional pointer indirection vs ART, in-place update |
| **Range scans** | Wait-free non-linearizable range/prefix scans |
| **Hazard keys** | 用 operation key 一次性宣布所有受保护指针——消除 per-deref SMR 开销 |
| **系统集成** | RocksDB write-heavy +40%, Turso +12%（替换默认 skiplist） |

## 可复用启发

- **Key-based SMR**：hazard keys 的核心洞察——"operation key 可以近似 reachable pointer set"——避免了传统 hazard pointers 的 per-pointer 开销。适用于任何基于 key 的树索引
- **"冻结"协调**优于 RCU 或 per-node locks：freezing-based protocol 同时实现 lock-freedom 和 in-place update——两者之间通常被认为是矛盾
- 128-bit CAS/load 是 practicality 的边界——论文指出 Arctic 需要它作为 correctness 和 reasonable performance 的前提
