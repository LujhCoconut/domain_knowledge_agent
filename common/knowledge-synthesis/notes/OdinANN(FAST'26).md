# OdinANN(FAST'26)

- **来源**: https://www.usenix.org/system/files/fast26-guo.pdf, FAST '26
- **作者**: Hao Guo, Youyou Lu (Tsinghua)
- **一句话 TL;DR**: 十亿级图-based ANNS 索引的 **direct insert** 方案——通过 GC-free 空间过度分配(overprovision)+近似并发控制(per-record isolation+delta pruning)+缓冲删除，消除 buffered insert 的 merge 干扰，搜索 P50 延迟仅波动 1.07×（vs DiskANN 2.44×），同时节省 ~70% 内存。
- **资料类型**: 论文-系统（ANNS/向量数据库）

---

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| ANNS | Approximate Nearest Neighbor Search，近似最近邻搜索 | 核心问题 |
| Graph-based Index | 将向量组织为有向图，节点=向量，边=近邻关系 | OdinANN/DiskANN 的基础 |
| Buffered Insert | 先写入内存索引→达到阈值→批量 merge 到磁盘 | 现有方案（DiskANN/SPFresh） |
| Direct Insert | 直接将向量插入磁盘索引，无需内存缓存 | 本文提出的替代方案 |
| GC-Free Update Combining | 固定-size record 使 out-of-place 更新可直接复用旧位置→无需 GC | OdinANN 核心创新 |
| Space Overprovision | 每页预留多空 record slot→合并多个 record 更新→降写放大 | 默认 2× 磁盘空间，2× write amplification |
| Per-Record Isolation | 搜索仅保证每条 record 的一致快照，不保证全局图原子性 | 放松隔离度换并发 |
| Approximate Neighbor Snapshot | 插入时使用近邻的近似快照→减少临界区 | 避免搜索-验证循环 |
| Delta Pruning | 仅检查新插入邻接与已有邻接的三角不等式→O(R) vs O(R²) | 降低插入临界区计算开销 |
| Dynamic Candidate Pool | 搜索时动态扩大候选池以补偿删除向量导致的 top-k 不足 | 删除场景的搜索质量保证 |
| Two-Pass Merge (Delete) | Pass 1 扫描加载删除向量邻接→Pass 2 流式替换+裁剪+写回 | 删除合并，低 I/O 干扰 |
| PQ (Product Quantization) | 压缩向量表示（32B/vector） | 内存中图导航加速 |

---

## 背景与动机

### 为什么需要向量更新

- 现实系统持续产生新数据（新图片/文档/商品→新向量）
- 索引重建在十亿级数据集上需数天→搜索结果过时
- 需要在线的索引更新（insert/delete）同时服务于搜索

### Buffered Insert 的三重低效（DiskANN 实验数据）

| 问题 | 表现 | 根因 |
|------|------|------|
| 搜索性能抖动 | 搜索 P50 延迟达 **1.54×**（merge 期间） | Merge 的磁盘读带宽干扰前端搜索 |
| 高内存 | **125GB** for merging 3% vectors into 十亿索引 | 内存索引+缓冲磁盘写入 |
| Merge 本身瓶颈 | 吞吐上限 **~3000 QPS**，不随 batch 增长 | In-memory merge 的搜索步骤无法批处理 |

**核心洞察**：Buffered insert 的 merge 无法高效批处理——因为为每个插入向量搜索磁盘邻居（hundreds of disk reads per vector），这一步是串行的、无法合并。→ Direct insert 不仅可行，而且可以做得和 buffered insert 一样高效。

---

## 方案设计

### 1. GC-Free Update Combining（核心存储创新）

**关键观察**：图索引使用**固定大小 record** → out-of-place 更新可直接复用旧位置，无需 log-structured GC。

**方案**：
- 每页预留额外空 record slot（默认 2× 磁盘空间）
- 插入时合并多个 record 更新到同一页的一次写入
- 旧 record 位置直接标记为可用→下次分配
- 三条分配规则（优先级降序）：
  1. **Empty page**（所有 record 失效）→不需额外读
  2. **On-path partial-empty page**（在搜索路径上，< m 非空 record）→缓存命中
  3. **Overprovision**（分配新页）→空间开销由 rules 1-2 限制

**效果**：写放大 = n/(n-m)（默认 n=6, m=3 → 2×）。但 2× 磁盘空间 + 2× 写放大 vs 节省 128GB+ DRAM → **用便宜的 SSD 换昂贵的内存**（1TB SSD ~$100 < 128GB DRAM >$200）。

### 2. Approximate Concurrency Control

**关键观察**：ANNS 是 approximate 的——不需要严格的 ACID 隔离。

| 冲突类型 | 方案 | 效果 |
|---------|------|------|
| **Search-Insert** | Per-record 锁（仅锁 ID-to-location mapping 条目）+ 允许部分 record 对 search 可见/不可见 | 消除了 DiskANN 的 per-node RW-lock 争用（tail latency spike 来源） |
| **Insert-Insert** | 使用近邻的**近似快照**（不验证结果集不变）→ 三步完成（搜索→锁+验证→更新）vs OCC 的四步（搜索→锁→验证→重试…） | 避免额外全搜索验证 |
| **Delete-Search** | 全局 RW lock（删除开销低→fine-grained 锁不值得） | 简单但有效 |

**两个临界区优化**：
- **优化 1**：磁盘 I/O 移出临界区——write-back page cache（搜索缓存立即释放）+ 后台 I/O 线程提交写入
- **优化 2**：Delta pruning —— O(R) 三角不等式检查（仅检查新插入邻接，fallback 到 O(R²) 仅在无 neighbor 可 prune 时）

### 3. Buffered Delete + Two-Pass Merge

**删除**：仅记录已删除向量 ID（4-8B/vector）到内存集合→搜索后过滤。

**搜索质量**：动态候选池——忽略已删除向量，保证候选池至少包含 l 个非删除向量。

**Merge 时机**：双指标——删除向量比例（默认 10%）或搜索 I/O 放大倍数 > 1.1×（反映索引质量退化）。

**Two-Pass Merge**：
- Pass 1：顺序扫描索引→加载删除向量邻接 ID 到内存（受内存预算限制，每个向量仅加载部分邻接）
- Pass 2：顺序扫描索引→流式替换+裁剪+写回

---

## 评估数据

### 总体性能（SIFT100M，插入 100M → 200M）

| 指标 | OdinANN vs DiskANN | vs SPFresh |
|------|-------------------|------------|
| P50 延迟 | **-13.3%** avg | **-51.7%** avg |
| P50 波动 | **1.07×** (vs 2.44×) | — |
| P90 延迟 | **-34.6%** | -36.5% |
| P99 延迟 | **-19.5%** | -28.4% |
| 吞吐 | **+15%** | **+99%** |
| 峰值内存 | **29.3%** of DiskANN | 86.8% of SPFresh |
| 精度 (Recall@10) | **99.1-100%** of DiskANN | 显著更高 |

### 十亿级 SIFT1B（800M + 200M insert）

- P50 延迟：85.7% of DiskANN, **62.1%** of SPFresh
- 内存 83.8GB vs DiskANN **>200GB**
- 同时达到 **5000 QPS** 搜索 + **1100 QPS** 插入，P50 延迟 ~3ms

### Breakdown（插入性能）

| 优化 | 插入吞吐 | 插入 P50 |
|------|---------|----------|
| Baseline | 1× | 基准 |
| +Async（磁盘 I/O 出临界区） | +37% | - |
| +OP（空间过度分配+out-of-place） | **5.12×** | -72.9% |
| +Prune（Delta pruning） | **+2.59×** | -60.3% |
| 最终 | **2000 QPS** | **11.1ms** |

---

## 整体评估

### 真正的新意

1. **"Fixed-size records → GC-free update combining"**：将图索引的工程约束（定长 record）转化为优势——out-of-place 更新直接复用旧 slot，消除 log-structured GC。这是"利用数据结构本身的特性消除系统开销"的经典案例。

2. **"用便宜的 SSD 过度分配换昂贵的内存节省"**：2× 磁盘空间（~$100/TB SSD）vs 128GB+ DRAM（>$200）。不是纯粹的性能优化——是 TCO-driven 的架构决策。

3. **"ANNS 的近似性 = 并发控制的自由度"**：不需要 atomic operation、不需要 serializable isolation——per-record consistency + approximate neighbor snapshot 就足够。利用问题域的内在松弛换取系统性能。

4. **"Delta pruning = 假设已有邻接满足三角不等式，只检查新增"**：图结构的局部性意味着增量插入时大部分已有边仍然有效→仅验证新边→从 O(R²) 到 O(R)。

### 优点

- 问题分析扎实：buffered insert 的低效通过实验数据清晰展示
- 存储-并发联合设计：overprovision 既降写放大又作为并发控制的基础
- 两条原则清晰："用空间换时间/简单性"（overprovision）+"用近似换并发"（per-record isolation）
- 十亿级数据集验证了 scalability

### 局限

- Direct insert 的 per-insert latency (11.1ms) 高于 buffered insert 的纯内存写入——对延迟极敏感的场景可能不适用
- 空间过度分配的 2× 系数是经验默认值，未提供自适应方案
- 仅测试 SIFT/DEEP 数据集（向量维度 96-128）→对高维向量（768-4096，如 LLM embeddings）的泛化性未验证
- 不支持 concurrent 搜索+插入+删除三负载的完整评估（删除场景仅在 §4.7 简要讨论）

### 适用条件

- 十亿级向量的在线 ANNS（高搜索 QPS，持续向量插入）
- 内存容量是瓶颈（buffered insert 的内存索引不可接受）
- 插入延迟 ~10ms 可接受
- 向量维度 ≤ 几百维（高维场景 PQ 压缩精度下降）

### 可复用启发

1. **"数据结构固有约束 → 系统优化"**：Fixed-size records 常被视为限制→OdinANN 将其变为 GC-free 的基础。适用场景：任何有固定数据结构大小的存储系统——利用 fixed-size 实现 in-place reuse。

2. **"近似 = 并发控制的自由度"**：不要求 atomicity 和 strict isolation → 可以用 per-record consistency + approximate snapshot → 减少锁争用 + 缩短临界区。适用场景：任何 approximate/soft-state 系统（缓存、推荐、流处理）。

3. **"用便宜存储过度分配换取昂贵内存的节省"**：2× 磁盘空间是可接受的代价→但需要论证 SSD/DRAM 价格比。TCO-driven architecture 比纯性能优化更有说服力。

4. **"Delta prune = 利用历史状态的正确性假设"**：假设已有边满足三角不等式→只检查新边→ fallback 仅在无 neighbor 可 prune 时启用。类似数据库的 incrementally maintained views——好的降级路径使"乐观假设"安全。

### 讨论问题

- LLM embedding（768-4096 维）场景下，PQ 压缩的有效性和 overprovision 的空间放大是否会吞噬优势？
- 多磁盘/多节点场景下 GC-free 方案的可扩展性
- 与 SolidAttention/Helmsman 的 SSD-based ANN 方案在 RAG pipeline 中如何组合？
