# Graph Processing

分布式图处理与图分析系统。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 内存高效分布式图分析 | partial mirroring, mirror heterogeneity, mirror-free, work migration, BSP, communication-computation overlap | Pluto(OSDI'26) |

---

## 内存高效分布式图分析 (Pluto)

### 核心问题
分布式图分析中 full mirroring（复制所有可能需要的远程数据）内存开销 up to 4×（高连接图上更大），而内存容量增长落后于数据增长——full mirroring 不可持续。

### 关键洞察

1. **"Mirror heterogeneity"——不是所有数据复制都有生产性**：识别并消除非生产性复制 → 减少内存的同时保持或提升性能
2. **"Mirror-free 完全消除复制开销"**：对可无镜像高效运行的算法变体——零复制开销
3. **"Work migration + compute-comm overlap"**：将计算迁移到数据所在节点 + 早启动网络传输与本地计算重叠 → 隐藏通信延迟

- 来源：Pluto(OSDI'26)

### 实践启发
- **"识别并消除非生产性资源消耗"是反复出现的主题**：Pluto（消除非生产性镜像）、DINGO（消除非生产性维护 IO）、SPADE（推迟非瓶颈任务）
- **"Work migration 而非 data replication"是分布式图计算的可扩展范式**：当内存容量成为瓶颈时，将计算迁移到数据比将数据复制到计算更可扩展
- **"Mirror heterogeneity 是可推广的概念"**：任何复制/缓存系统中都存在非生产性副本——按价值区分对待而非全量复制
