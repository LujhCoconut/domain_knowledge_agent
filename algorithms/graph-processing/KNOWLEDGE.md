# Graph Processing

分布式图处理与图分析系统。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 内存高效分布式图分析 | partial mirroring, mirror heterogeneity, mirror-free, work migration, BSP, communication-computation overlap | Pluto(OSDI'26) |
| GNN 数据准备 ISC 优化 | out-of-order neighbor sampling, DirectGraph format, physical address embedding, multi-level NDP, hop-by-hop barrier elimination | BeaconGNN(HPCA'24) |

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

---

## GNN 数据准备 ISC 优化 (BeaconGNN)

### 核心问题
大规模 GNN 的图数据和 feature table 存储在 SSD 中时，数据准备（多跳邻域采样 + 特征检索）是主要瓶颈。现有 ISC 方案（SmartSage/GList）只卸载部分 GNN 操作到存储，且受限于 hop-by-hop 串行采样顺序（每跳需要 host 做地址翻译）。这导致 flash die 大量空闲（inter-hop barrier）、channel bandwidth 被 page-granular 传输浪费、firmware 处理成为瓶颈。

### 关键洞察

1. **"物理地址嵌入图结构消除 hop-by-hop 串行屏障"**：传统方案中，第 k 跳采样完成后需要 host 做 node_id→LBA→PPA 地址翻译才能开始第 k+1 跳 → 严格的串行依赖。**DirectGraph 将每个 neighbor 直接存为 4 字节物理地址 (28-bit page + 4-bit section offset)** → 采样结果本身就是下一跳的物理地址 → 无需 host 参与 → 允许不同 hop 的采样乱序/重叠执行。

2. **"静态数据 + 可预测访问模式 = 预计算物理地址 > 运行时翻译"**：DirectGraph 利用了 GNN 图数据长期不变的特性——一次性离线构造 DirectGraph → 后续所有访问都直连物理地址。存储膨胀率仅 2.8-4.1%（正常度图），低度图（OGBN 28 平均度）膨胀 32.3%——但因大规模图的 Densification law（平均度随节点数增长），正常大图膨胀很小。

3. **"Die-level 采样 = 将计算推到数据所在的最远端 + 仅传输有用数据"**：Sampler 放在 cache register 和 data register 之间 → 数据读出 flash array 后立即采样 → 输出是采样结果（小）+ feature vectors（中等）+ 新命令（极小），而非整个 4KB page。这直接解决了 "page-granular channel transfer 浪费带宽" 的问题。

4. **"Neighbor sampling 的随机性 → TRNG 比 PRNG 更适合 die-level 实现"**：每个 die 有一个 TRNG → 模运算随机选择邻居 → 不需要存储或同步 PRNG 状态 → 适合分布式、无状态的 die-level 实现。每个采样结果是独立随机的 → 不需要 die 间协调。

- 来源：BeaconGNN(HPCA'24)

### 实践启发
- **"打破串行约束比加速串行操作更有效"**：BeaconGNN 的核心贡献不是让单跳采样更快，而是**允许跨 hop 并行**。DirectGraph 的价值在于"解除约束"而非"加速操作"。**可推广的模式**：当发现一个串行瓶颈时，先问"这个串行依赖是本质的（算法要求）还是人为的（实现约束）？"——GNN hop-by-hop 依赖是实现约束（地址翻译），而非算法要求（图已经固定，所有 neighbor 已知）。
- **"嵌入物理地址的思想可推广到其他 ISC/NPD 场景"**：任何 "数据静态 + 访问模式可预测 + 当前有昂贵的运行时地址翻译" 的组合 → 可以考虑预计算+嵌入物理地址。候选场景：LSM-tree SSTable 的 block index 嵌入物理 offset、向量数据库的 IVF 索引嵌入 flash PPA、KV store 的 hash table bucket 嵌入物理位置。
- **"GNN 数据准备的 I/O 模式是 small random reads over large dataset"**——这与传统 database query (也面临 small random I/O) 有相似之处 → BeaconGNN 的 die-level filtering 与 database 的 "predicate pushdown to storage" 在原理上相通。
