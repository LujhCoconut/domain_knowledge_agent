# Memory Hierarchy

CXL/分离式内存与缓存一致性体系结构。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 泛化缓存一致性 (GCP) | disaggregated shared memory, lock synchronization, wait queues, variable-size cache lines, coherence protocol extension | Soul/GCP(OSDI'26) |
| 共享分离式内存对象存储 (Duhu) | CXL, pass-by-reference, immutable objects, non-temporal writes, cache coherence avoidance | Duhu(OSDI'26) |
| VM 弹性内存超卖 (Blowfish) | disaggregated memory, paravirtualization, THP-aware tracking, far memory swapping, hypervisor bypass | Blowfish(OSDI'26) |
| 虚拟化无压缩内存碎片整理 | infinite GPA space, compaction-free, GPA-HPA remap, memory trade, huge page defragmentation | InfiniDefrag(OSDI'26) |
| CXL 部分一致性数据共享 | split metadata, SCR-LNR tiering, CXL shared log, hardware-coherent region, cross-host sharing, HCMeta | Megalon(OSDI'26) |
| DM 树索引计算侧协同设计 | disaggregated memory, range index, compute-side collaborative cache, fingerprint offloading, collaborative locking, RDMA resource rebalancing | DMTree(FAST'26) |
| CXL-SSD 全系统仿真 | CXL.mem emulation, Dynamic EPT Remapping, hybrid fast/slow path, cache policy exploration, FEMU-based, hardware-software co-design | Cylon(FAST'26) |
| CXL 3.1 全特性仿真框架 | port-based routing, device-managed coherence, PCIe 6.0, non-tree topology, snoop filter, architectural simulation | Xerxes(FAST'26) |

---

## 泛化缓存一致性 (GCP)

### 核心问题
机架级计算-内存解耦中，inter-compute 链路延迟是 NUMA 的 50-500×（5-10µs vs 20-100ns）。在此延迟下，layered approach（锁算法叠加在缓存一致性之上）产生**冗余 inter-cache 通信**——每个锁操作需要多次 coherence 消息往返。即使是性能最好的锁算法，在解耦共享内存上性能退化高达 **1000×**。

### 关键洞察

1. **"同步是缓存一致性在时间和空间上的泛化"**：时间泛化 = 等待队列替代 spin-retry；空间泛化 = 可变大小缓存行适配锁结构
2. **等待队列 at coherence layer**：锁不可获取时 core 直接注册到 coherence 协议队列 → 锁释放时 coherence 通知下一个等待者——消除 spin-retry 的重复往返
3. **Model checking 验证 GCP 正确性**：在 protocol 级提供形式化保证
4. **1-2 个数量级更快的应用性能，< 8% 存储开销**：无需修改应用代码
- 来源：Soul/GCP(OSDI'26)

### 实践启发
- "不要在上层打补丁，在下层改协议"：锁瓶颈转移到 coherence protocol 层——与其优化锁算法，不如改 coherence 协议
- 等待队列替代轮询适用于任何 distributed coordination 中的重复重试场景
- 最低限度的 protocol 扩展 > 全新的 lock 算法——GCP 是对现有 coherence 协议的 minimally invasive 扩展

---

## 共享分离式内存对象存储 (Duhu)

### 核心问题
分布式数据处理框架（Ray/Spark）使用 pass-by-value：每个节点在访问前将中间对象**复制**到本地内存——造成内存、网络和 CPU 的多重浪费。CXL SDM 使 pass-by-reference（多节点直接访问共享内存中的同一份对象）成为可能——但 SDM 不提供全局缓存一致性，而 CXL 3.0 的一致性支持带有 coherence tax（按比例增加，限制可扩展性）。

### 关键洞察

1. **"不可变性 + non-temporal writes" 绕开缓存一致性**：中间对象是不可变的（只写一次）→ 创建时用 non-temporal writes → 读取前 flush cache lines → 无需硬件一致性
2. **元数据/数据分离处理**：元数据需要节点间协调（易变、低频访问）→ 分区所有权；对象数据不需要一致性（不可变、高频访问）→ 直接 load-store
3. **Duhu-Channel**：基于 SDM + 网络信号的 low-latency RPC——元数据操作的通信延迟比传统网络 RPC 更低
4. **Pass-by-reference 不仅优化现有操作，还能**fundamentally**改变操作实现**：FlexShuffle 将数据传输变为元数据重组，shuffle stage 最高 13.81× 加速
- 来源：Duhu(OSDI'26)

### 实践启发
- "不可变性 + non-temporal writes + flush-before-read" 是绕开缓存一致性的通用模式——适用于任何共享不可变数据的场景
- 元数据（需协调）+ 数据（无需协调）的分离是共享系统的核心架构模式
- Pass-by-reference 的价值远超"减少复制"：它可能**改变操作的基础实现方式**（数据搬移→指针重定向）

---

## VM 弹性内存超卖 (Blowfish)

### 核心问题
超过 50% 的数据中心内存闲置（VM bin-packing 低效），但现有内存超卖机制（balloon+swap）在 THP 场景下失效：2MB 大页掩盖 4KB 访问信号→无法追踪冷页；swap to disk 的毫秒级延迟破坏 SLO。新兴高速互联（RDMA/CXL）使 µs 级远端内存成为可能→但现有软件栈 overhead 达 3.4-6.8×，成为新瓶颈。

### 关键洞察

1. **"语义在 guest，控制在 hypervisor"的半虚拟化分工**：guest 拥有程序语义（识别冷页）但缺乏全局视角，hypervisor 拥有跨 VM 视角但缺乏语义→半虚拟化结合两者
2. **THP-aware 热度追踪**：在不打破 2MB 大页的前提下追踪 4KB 页面访问——这是 THP + 内存超卖的核心难题
3. **Hypervisor 直通跨 VM 路径**：绕过 guest 页表修改和 IO 页表修改——消除传统方案的 3.4-6.8× 软件 overhead
4. **"硬件速度已来，软件栈没跟上"**：disaggregated memory 的 µs 延迟使冷内存交换可行→但需要重新设计整个软件路径
- 来源：Blowfish(OSDI'26)

### 实践启发
- THP 在内存管理优化中常被忽视——2MB 粒度掩盖了 fine-grained access pattern
- 半虚拟化分工模式（语义在 guest，控制在 hypervisor）适用于任何 VM 资源管理场景
- "硬件就绪→软件瓶颈暴露→软件栈重新设计"是 disaggregated memory 方向的普遍模式

---

## 虚拟化无压缩内存碎片整理 (InfiniDefrag)

### 核心问题
虚拟化环境中大页（huge page）对两态地址翻译性能至关重要，但内存碎片导致大页分配失败。现有方案：防碎片策略（静态、不适应多 workload）和 compaction（页迁移昂贵——YCSB-Redis 吞吐 -51%、延迟 +102%）。根本原因：guest OS 假设 GPA 空间固定有限→被迫用 compaction 在有限空间内拼出连续区域。

### 关键洞察

1. **"GPA 已经是虚拟地址——不需要 compaction，只需要 remap"**：Guest OS 以为自己管理物理内存，实际 GPA 已被 hypervisor 再次映射。获取连续 GPA 只需扩展 GPA 空间+更新 GPA-HPA 映射——guest 端完全不需要做页迁移。
2. **"GPA 空间几乎无穷"**（57-bit address width = PB 级）→永不耗尽→可以无限制地分配新的连续 GPA 区域→"用空间换连续性"。
3. **"Memory trade 替代 compaction"**：用碎片化页面换取连续内存——扩展新 GPA 区域→回收碎片→无需数据移动。Host Memory Guard 通过 self-hosted remap + batch unmapping 强制 HPA 使用在 VM quota 内。

- 来源：InfiniDefrag(OSDI'26)

### 实践启发
- **"多一层虚拟化 = 多一个解决碎片的机会"**：GPA 已经是虚拟层→guest 端 compaction 完全多余。类似 Blowfish "硬件速度已来，软件栈没跟上"——当底层是虚拟化的，上层的某些优化可能根本不需要
- **"穷举空间换简单性"**：PB 级 GPA 空间远超实际需求→可以用空间换取避免昂贵操作的简单性

---

## CXL 部分一致性数据共享 (Megalon)

### 核心问题
CXL 允许多主机共享内存，但硬件一致性（cache coherence）仅覆盖 CXL 的一个小区域（SCR，几百 MB），而 CXL 总容量可达数 TB——这是**部分一致性 CXL 模型**。现有 HCMeta 方案（如 Tigon）在 SCR 中存储 per-object coherence 元数据——数据集增大时元数据超出 SCR→反复 unshare/reshare (churn)→吞吐降 **10×**。

### 关键洞察

1. **"Split 元数据——大-低频 vs 小-高频——策略化分离"**：大的 index 条目复制到 LNR（低频更新），仅 coherence record 关键字段 + shared-log tail pointer 在 SCR（小、高频）。类似 Megalon "Cache-level vs object-level"——不是简单的缓存分层，是不同性质的元数据的策略化分离。
2. **"CXL shared log 保持 index replica 一致"**：所有对 index 的更新通过 shared log 序列化（increment tail→append update→check tail to sync）→消除单独的一致性协议开销。利用 CXL 低延迟 load-store 实现高效 shared log。
3. **"'利用 CXL 特性改变软件设计'——与 Duhu/Blowfish/InfiniDefrag 共享哲学"**：不是把现有设计移植到 CXL，而是重新设计以利用 CXL 独特特性（部分一致性模型、低延迟 load-store、shared memory 语义）。

- 来源：Megalon(OSDI'26)

### 实践启发
- **"分层策略不是大小分层——是按更新频率分层"**：large-seldom-updated vs small-heavily-updated 才是合理的分离维度。类似 LAH/S4-FIFO "cache-level learning vs object-level prediction"——分离维度的选择比分离本身更重要
- **"Shared log over shared memory 是高效的跨主机协调原语"**：当共享内存有低延迟时，shared log 可以替代传统的 message passing。类似 LogDrive "shared log over cloud storage"——shared log 是跨架构的通用协调模式

---

## DM 树索引计算侧协同设计 (DMTree)

### 核心问题
分离式内存(DM)将计算和内存分离为独立资源池，范围索引是 DM 上数据库/KV store 的关键组件。但现有范围索引全遵循 private compute-side caching 范式，面临两种互斥瓶颈：连续范围存储(B+ -tree/learned index)→读放大→带宽瓶颈(仅 16-18% of expected)；精确定位(ART)→多次小 RDMA→IOPS 瓶颈(扫描仅 35.5% of B+ -tree)。FP-B+ -tree 混合方案仍因额外 fingerprint read+lock RDMA 导致性能仅 expected 的 23-62%。核心机会：memory server 的网络是瓶颈，但 compute server 之间的 RDMA 资源始终不饱和。

### 关键洞察

1. **"瓶颈在哪里 → 把工作搬到不饱和的资源上"**：将 fingerprint table 的精确定位和 leaf node 的 lock/unlock 从 memory server 卸载到 compute server 之间——利用不饱和的 CS-CS RDMA 处理 IOPS 密集操作。传统 FP-B+ -tree 的 update 需要 5 次 RDMA 到 MS→DMTree 将其中 3 次（lock→CS, read FP→local cache, unlock→embedded in FP write to CS）重新路由到 CS 间。

2. **"Lock placement ≠ data placement"**：传统思维是锁应放在数据所在位置(MS)。DMTree 的洞察是 lock 只需在 write 访问路径上→当 primary fingerprint table 是写入必经之路时，lock 放在那里(CS)不仅省 RDMA 到 MS，还能和 FP write-back 合并为一个 RDMA_WRITE(embedded unlock)。

3. **"Primary-write-sync + cache-read-async + version validation = 读多写少的最优缓存一致性"**：仅同步更新 primary fingerprint table(写比例低→同步开销小)，缓存副本异步更新(读 local cache 快)，version ID 验证 catch inconsistency→fallback to primary。利用 DM 场景写比例低的特征→异步缓存的短暂不一致被乐观验证优雅处理。

4. **"Fingerprint(1B/entry) 承担三重角色"**：精确定位(替代整 leaf read→降带宽)、空条目过滤(scan 跳未写入 entry→降带宽)、协同缓存一致性单元(1B 的极小粒度→CS 间传输高效)。

- 来源：DMTree(FAST'26)

### 实践启发
- **"全局资源利用率热图→架构重构"**：识别哪个资源是瓶颈(MS IOPS/带宽)、哪个资源闲置(CS-CS RDMA)→将工作从瓶颈资源搬到闲置资源。这是通用性能优化方法论——适用场景：任何多节点非对称架构(边缘-云、client-server、CPU-GPU)
- **"Lock can live separately from data"**：锁不需要和数据在同一节点——只要锁在 write 访问路径的必经节点上。适用场景：分布式文件系统 metadata server、分布式数据库 transaction coordinator
- **"Primary-write-sync + cache-read-async = 写入瓶颈 vs 读取性能的最优折中"**：不要求所有副本同步→仅在写入时同步 primary→读取从最近副本读→版本号提供 safety net。适用场景：任何"读写比 >> 1"的分布式缓存/DNS/配置分发

