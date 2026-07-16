# DMTree(FAST'26)

- **来源**: https://www.usenix.org/system/files/fast26-wei.pdf, FAST '26
- **作者**: Guoli Wei, Yongkun Li (USTC), Haoze Song (HKU), Tao Li, Lulu Yao, Yinlong Xu (USTC), Heming Cui (HKU)
- **一句话 TL;DR**: 面向分离式内存(DM)的树索引 **计算侧协同设计**——将 fingerprint table 的精确定位和锁操作从内存服务器卸载到计算服务器之间的不饱和 RDMA 资源上，使用协同缓存(shared fingerprint storage) + 协同并发控制(compute-side locking + embedded unlock)，搜索/插入/扫描吞吐最高 **5.7×** 于 SOTA。
- **资料类型**: 论文-系统（分离式内存+索引）

---

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| DM | Disaggregated Memory，分离式内存（计算池+内存池） | 目标架构 |
| One-sided RDMA | 绕过远端 CPU 直接读写远端内存 | DM 索引的首选访问方式 |
| Read Amplification | B+ -tree 读取单个 entry 需读整个 leaf node(含 32 entries) | 带宽瓶颈根因 |
| IOPS Bottleneck | ART 多次小 RDMA 读分散 leaf entries + 频繁更新 internal tree | IOPS 瓶颈根因 |
| FP-B+ -tree | 在 leaf node 前加 1B/entry fingerprint table | 基础数据结构 |
| Private Compute-side Caching | 每个计算服务器私有缓存（不共享） | 现有方案范式 |
| Compute-side Collaborative Cache | 多计算服务器共享 fingerprint table 副本（一台 primary，其余 cache） | DMTree 核心创新 |
| Primary Fingerprint Table | 每 leaf node 的 fingerprint table 由一致哈希指定 primary server | 协同缓存的一致性基础 |
| Version ID | 8B 版本号（leaf node 范围变化时递增） | 缓存一致性验证 |
| Collaborative Locking | Lock fields 存储在计算服务器的 primary fingerprint table 中 | 将锁操作从内存服务器移到计算侧 |
| Embedded Unlock | Unlock 与 fingerprint table write-back 合并到一个 RDMA_WRITE | 减少 RDMA 次数 |
| CRC Check | 每读写单元 8B CRC→读-写冲突通过 CRC mismatch 检测 | 乐观并发控制（读-写冲突） |

---

## 背景与动机

### DM 架构中范围索引的两种瓶颈

DM 架构下，所有现有范围索引遵循 **private compute-side caching** 范式（每个计算服务器私有缓存内部节点/模型），面临两种互斥的瓶颈：

| 索引类型 | 代表 | 瓶颈 | 根因 | 性能损失 |
|---------|------|------|------|---------|
| 连续范围存储 (B+ -tree/Learned Index) | Sherman, ROLEX | **带宽瓶颈** | Read amplification（读 1 entry 需读整 leaf node=32×） | 仅达期望搜索性能的 16.3-18.8% |
| 精确定位 (ART) | SMART | **IOPS 瓶颈** | 多次 RDMA 读分散 leaf + 频繁更新 internal tree | 扫描仅 35.5% of Sherman; 插入仅 35.8% of expected |
| LSM-tree | dLSM | **CPU 瓶颈** | Compaction 任务在 memory server 单核上堆积 | 插入性能随线程增长→下降 |

### 混合方案（CHIME/FP-B+ -tree）仍然不足

连续存储 + 精确定位（hashing/fingerprint）结合了二者的优势，但仍有两个问题：
1. **Fingerprint table 的额外 RDMA**：读/写 fingerprint table 消耗额外 IOPS→FP-B+ -tree 搜索仅 half of expected
2. **锁操作的 IOPS 消耗**：RDMA_CAS + RDMA_WRITE for lock/unlock → update 仅 48.1-61.8% of expected

### 被忽视的机会：计算服务器间的不饱和 RDMA 资源

Memory server 是 IOPS/带宽瓶颈，但 **compute server 之间的 RDMA 资源始终不饱和**——因为多 CS→单 MS 的聚合请求使 MS 网络先达瓶颈。

---

## 方案设计

### 核心理念：Compute-side Collaborative Design

将精确数据定位和锁操作从 memory server 卸载到 compute server 之间，利用不饱和的 CS-CS RDMA 资源。

### 1. Compute-side Collaborative Cache（协同缓存）

**Private Internal Cache**：每个 CS 缓存 internal tree（底部内部节点），上层节点本地构建。内部节点极少更新→缓存 thrashing 最小。

**Collaborative Fingerprint Storage**：
- 每 leaf node 的 fingerprint table 存储在多个 CS 上（一台 primary + 若干 cache）
- Primary ownership 通过一致哈希决定（`consistent_hash(fp_offset)`）
- 搜索时：从 peer CS 读 fingerprint table → 本地缓存 → match → 读 remote K-V → 若非命中/不一致 → fallback 到 primary table
- 写入时：仅同步更新 primary table → 缓存副本异步更新

**一致性（版本号验证）**：
- 每 leaf node/entry/fingerprint table 含 8B version ID
- 缓存命中后比对 version ID → 不匹配则 invalidate cache → 远程遍历+更新
- Entry 级 CRC（8B）：读-写冲突检测

### 2. Compute-side Collaborative Concurrency Control

**核心创新**：将锁字段从 memory server 移到 compute server，存在 fingerprint table 末尾。

| 操作 | 传统 FP-B+ -tree (5 RDMA to MS) | DMTree |
|------|-------------------------------|--------|
| Lock | RDMA_CAS to MS | RDMA_CAS to primary CS |
| Read FP | RDMA_READ from MS | 本地 CS 缓存命中 |
| Read K-V | RDMA_READ from MS | RDMA_READ from MS |
| Write K-V | RDMA_WRITE to MS | RDMA_WRITE to MS |
| Unlock | RDMA_WRITE to MS | **Embedded**: RDMA_WRITE FP+unlock→primary CS |

**5 次 MS RDMA → 3 次卸载到 CS 间，仅剩 2 次**（read/write K-V entry to MS）。

**Optimistic Read-Write**：CRC 检测不一致→重读。

### 3. RDMA 优化

- Fingerprint 过滤空条目→扫描时仅读有效 entry→节省带宽
- 合并同 CS 的并发请求→减少 RDMA 次数

---

## 评估数据

### Micro-benchmarks (Uniform, 1B entries, 6 CS + 1 MS)

| 操作 | DMTree vs 最佳 baseline |
|------|------------------------|
| Search | 超越所有 baseline，接近 Expected |
| Insert | 显著高于 CHIME/FP-B+ -tree（跨线程 scaling 更稳定） |
| Update | 显著高于 CHIME/FP-B+ -tree（协同锁的好处） |
| Scan | 显著高于 SMART（fingerprint 过滤+连续存储） |
| **最高** | **5.7×** vs SOTA |

### 关键消融

- 协同缓存（fingerprint 从 CS 读 vs 从 MS 读）+ 协同锁（lock 在 CS vs MS）→ IOPS 消耗大幅降低
- Memory overhead: 每 entry 1B fingerprint + 每 CS 的内部树缓存 → 在 25GB/compute server 内存预算内

---

## 整体评估

### 真正的新意

1. **"利用不饱和的 CS-CS RDMA 资源卸载 MS 瓶颈"**：这不是新优化技巧——是架构级重构。将原本全部流向 MS 的 IOPS（fingerprint read/write + lock/unlock）重新路由到 CS 间。前提是发现 CS-CS RDMA 始终不饱和，而 MS 网络是瓶颈。

2. **"Collaborative caching ≠ shared caching——primary + replica 的一致性模型"**：不同于简单的 shared cache（所有副本同时更新→同步开销大），DMTree 采用 primary-write-synchronous + cache-read-async + version-based validation。结合 DM 场景中写比例低的特点，异步缓存的"短暂不一致"被乐观验证优雅处理。

3. **"Lock fields 从 memory server 搬到 compute server——where you lock matters"**：传统思维是 lock 应该在数据所在位置（memory server）。DMTree 的洞察是：lock 的目的是 serializing write access，不一定需要和数据在同一物理位置——只要 primary FP table 是 write 的必经之路。

### 优点

- 问题分析非常扎实：从 B+ -tree → ART → LSM-tree → CHIME/FP-B+ -tree 的瓶颈演进链完整
- IOPS/带宽消耗的量化热图（图 5）直观展示了"MS 是瓶颈，CS 间资源闲置"的核心机会
- 协同缓存+协同锁是一个联合设计——锁的位置取决于缓存的位置——两个组件互相依赖
- 正确性处理周全（version ID + CRC + fallback path）

### 局限

- 仅测试固定 32B K-V 对→实际应用中 K-V 大小差异大→更大的 K-V 会减小 IOPS 瓶颈的相对重要性
- FP-B+ -tree 基础的 1B fingerprint 对长 key 的哈希冲突率可能上升→需评估
- CS 内存预算 25GB 是否在所有部署场景中可行
- CXL 场景下 CS-CS 延迟更低的 RDMA 仍有优势但幅度可能减小

### 适用条件

- DM 架构（RDMA 互联的计算-内存分离池）
- 范围索引需要同时服务 point 和 range 操作
- Memory server 网络是瓶颈但 CS 间有剩余 RDMA 资源
- 写比例不太高（否则 CS 间同步开销上升）

### 可复用启发

1. **"瓶颈在哪里 → 把工作搬到不饱和的资源上"**：CS-CS RDMA 不饱和 + MS 网络饱和 → 把 fingerprint read + lock 搬到 CS 间。这是"全局资源利用率图→架构重构"的方法论。

2. **"Primary-write-sync + cache-read-async + version validation = 读多写少场景的最优缓存一致性"**：写同步保证正确性、读异步利用局部性、版本号提供 safety net。适用场景：任何"读写比 >> 1"的分布式缓存。

3. **"Lock placement ≠ data placement——where you lock 是独立的设计维度"**：锁的位置不一定需要和数据在同一物理节点。当访问路径必经某个中间层（primary FP table），锁放在那里更高效——不仅省 RDMA，还能和 write-back 合并（embedded unlock）。

4. **"Fingerprint 不仅是索引加速——也是带宽节省（空条目过滤）和一致性验证的载体"**：1B/entry 的 fingerprint 承担了三个角色：精确 locating（替代整 leaf read）、空条目过滤（scan 时跳未写入 entry）、协同缓存的一致性单元。

### 讨论问题

- 极高写入比例（YCSB A: 50% write）下协同缓存的异步更新延迟是否会导致频繁的 primary fallback → 退化为传统方案？
- Fingerprint table 的 1B 哈希在高维 key 场景下的冲突率需要更多分析
- CXL 3.0 shared memory 场景下，DMTree 的 CS-CS 卸载还能保持多少相对优势？
