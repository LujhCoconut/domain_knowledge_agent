# Concurrent Data Structures

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 无锁自适应基数树 | lock-free ART, freezing-based coordination, hazard keys SMR, range scans, 128-bit CAS | Arctic(OSDI'26) |

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
