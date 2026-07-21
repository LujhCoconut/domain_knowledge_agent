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
| eBPF 页面回收策略委托 | eBPF, user-space delegation, page reclamation, per-page weight, proactive reclamation, LRU vs MIN gap | PageFlex(ATC'25) |
| 多级 flash 近数据处理 (NDP) | die-level sampling, channel-level command routing, in-storage computing, ULL flash, out-of-order processing, page-granular transfer | BeaconGNN(HPCA'24) |
| CXL 内存扩展器通用 NDP | M2func, M2uthr, packet filter, CXL.mem repurposing, FGMT, RISC-V vector ISA, memory-mapped threading, low-overhead offloading | CXL-M2NDP(MICRO'24) |

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

---

## eBPF 页面回收策略委托 (PageFlex)

### 核心问题
超算中心用 TMO/g-swap 做 proactive memory reclamation，但内核中硬编码的 LRU 近似策略与理论最优（MIN）有 14-38% 差距。更优策略已存在但写成内核代码→部署慢、难 upstream。需要一种方式让回收策略能在用户空间快速迭代，同时不牺牲性能和兼容性。

### 关键洞察

1. **"策略决策从内核剥离，但执行机制留在内核"**：内核保留 swap device 实现、page fault 处理、cgroup accounting，只将"哪页该回收"的决策通过 eBPF tracepoint + 4B per-page state 暴露到用户空间。与 userfaultfd 把整个 swap 栈搬出内核截然相反。

2. **"Proactive reclamation = 决策在后台、不在 critical path"**：超算中心的回收是 proactive 的（定时扫描→决策→madvise PAGEOUT），不在 page fault 路径上。这意味着决策的延迟容忍度远高于强制执行路径（userfaultfd 的同步 fault handler 每页多 4µs）。

3. **"LRU 与 MIN 的差距随 refault rate 容忍度上升而放大"**：真实 trace 上，1% refault rate → 14-37% 差距，5% → 22-38% 差距。这说明"允许多一些 refault 以换取更多内存回收"时，LRU 的弱点被放大——LRU 无法区分"偶尔访问但重要的热页"和"偶尔被扫到的冷页"。
   - 来源：PageFlex(ATC'25)

### 实践启发
- **"机制/策略分离的关键是找到'不在 critical path 的决策点'"**：PageFlex 选择 proactive reclamation 和 prefetch 作为委托对象——二者都是后台决策，不在 page fault 关键路径上。类比：Mooncake Store prefetch 也是后台决策（`triggerSsdPrefetch` 异步入队），不在 `get()` 的关键路径上。任何类似的分离设计都应该先画"哪些决策在 critical path、哪些不在"。
- **"Per-page 4B state ≈ per-block 4B lease metadata"**：PageFlex 的 4B 约束（0.1% 内存开销）和 Mooncake 的 lease metadata 设计面临相同约束——"每对象最少需要多少状态才能做出比 LRU 更好的决策？"Mooncake 的 lease_timeout + soft_pin_timeout 也是 ≤ 16B——同样极简。

---

## 多级 flash 近数据处理 (NDP) (BeaconGNN)

### 核心问题
传统 in-storage computing (ISC) 将计算卸载到 SSD 控制器（如嵌入式核或 FPGA），但忽略了 flash 层次内部的两大瓶颈：(1) **page-granular 通道传输**——GNN 等 workload 的 I/O 远小于 flash page 大小，但 channel 必须传输整个 page，浪费大量带宽；(2) **firmware 调度瓶颈**——嵌入式处理器核 poll flash 状态、管理 request queues、配置 DMA——当 flash die 数量多且延迟低（ULL flash 仅 3µs）时，firmware 处理能力跟不上。

### 关键洞察

1. **"每一级解决该级的瓶颈——不是在一处做大 NDP，而是多级分工"**：Die-level (sampler) 在数据源头做筛选，只传输有用数据（采样结果+特征向量）而非整个 page → 消除 page-granular 传输浪费。Channel-level (command router) 接管 flash 控制——硬件自动解析采样结果流、dispatch 新命令、routing between channels → 消除 firmware 调度延迟。Controller-level (spatial accelerator) 做 embeddding aggregation + GEMM 计算 → 消除 PCIe 传输和 accelerator 间数据搬移。

2. **"新技术→新瓶颈→新优化机会"**：ULL flash 将读延迟从 ~100µs 降到 3µs → 传统 NAND 下 die read 是瓶颈（firmware 处理能力足够）→ ULL 下 channel transfer + firmware scheduling 成为新瓶颈 → channel-level router 才有价值。**传统 SSD (20µs) 下 BG-2 与 BG-DGSP 性能相同——证明 router 的价值完全依赖 ULL flash。**

3. **"Die sampler 面积 <0.1% die area, channel router 1.26% controller area"**：用极小的硬件代价（控制逻辑+TRNG+dispatch queues+parser+router crossbar）换取大幅性能提升。关键：定制逻辑的面积远小于通用处理器核。

4. **"优化顺序很重要——先释放物理瓶颈再解除软件约束"**：BG-DG (DirectGraph alone)几乎无提升→ page 传输高延迟压制了 out-of-order 的收益。BG-SP 先消除 page-granular 传输 → 5.47× → 然后 BG-DGSP 的 out-of-order 才带来 20% 额外提升。**如果优化顺序反了（先 DG 后 SP），可能得出"乱序无效"的错误结论**。

- 来源：BeaconGNN(HPCA'24)

### 实践启发
- **"多级 NDP 的设计原则——每级做该级最擅长的事"**：Die-level 有数据局部性（data register 读出的数据就近处理）→ 做数据压缩/过滤。Channel-level 有全局视野（所有 die 的命令流经过）→ 做 routing/调度。Controller-level 有计算资源（SRAM+MAC array）→ 做 heavy compute。这类似于分布式系统中的 map-reduce 分工——不要把所有逻辑堆在一处。
- **"物理地址嵌入数据结构可以打破串行约束"**：DirectGraph 把 PPA 嵌入 neighbor list → 消除 node_id→LBA→PPA 的三级地址翻译 → 允许跨 hop 乱序采样。**可推广的模式**：当数据结构是静态的、访问模式是可预测的 → 预计算并嵌入物理地址 → 消除运行时地址翻译的串行化瓶颈。类似思想可考虑应用于 KV store 的 LSM-tree compaction、预计算文件 offset 的 direct I/O 等。
- **"硬件加速器的价值评估要区分'新技术依赖'和'通用有效'"**：BeaconGNN 的传统 SSD 对比实验是很好的工程习惯——区分哪些优化是 ULL-specific、哪些是通用的。任何 hardware-dependent 优化都应该在评估中包含这个维度。

---

## CXL 内存扩展器通用 NDP (CXL-M2NDP)

### 核心问题
CXL 内存扩展器通过 CXL.mem 协议提供低成本容量扩展（比增加本地 DRAM 便宜得多），但链路带宽远低于内存内部带宽且存在额外延迟（~150ns load-to-use）。在 CXL 控制器中做近数据处理（NDP）可克服这些限制，但现有方案有三重不足：(1) application-specific HW 限制了 target workload 种类；(2) CPU/GPU cores 做 NDP 的面积和能效不匹配 NDP 的成本约束；(3) CXL.io/PCIe 的 NDP 卸载协议延迟达 µs 级（4.5-13.9µs），对细粒度 kernel（如 KV store lookup、DLRM sparse lookup）overhead 超过计算本身。

### 关键洞察

1. **"不修改标准协议,重解释已有语义"**：CXL.mem 已定义标准的 memory read/write → 只需在 CXL 控制器输入口加一个 packet filter → 检查 CXL.mem 请求的目的地址是否落在预分配 M²func region → 是则解释为 NDP 管理命令（kernel launch/status poll/register）而非普通内存访问。**不需要修改 CXL.mem 标准或 host CPU 硬件**——只需 18B per-process 的 packet filter 表（18KB 支持 1024 进程）。

2. **"M²func 用 store 指令做 NDP 卸载"**：Host 执行 uncacheable store 到 M²func region → CXL.mem write packet 到达 CXL 内存 → packet filter 拦截 → NDP controller 解析 write data 作为函数参数 → 执行 kernel launch。返回值通过后续 load 取回。整个 offload 延迟仅 35ns（CXL.mem 协议处理 + 内部路由），vs CXL.io ring buffer 的 13.9µs——**差异 ~400×**。

3. **"Memory-mapped μthread = 数据处理单元的 ID 就是它要处理的数据地址"**：不同于 GPU 用 (threadblockID × blockDim + threadID) 间接计算地址（占动态指令 ~30%），µthread 直接用内存地址创建 → 起始地址通过 (base, offset) pair 直接给 → 消除冗余地址计算。这对于 memory-bound workload 尤为关键——地址计算是指令流中的显著比例。

4. **"Per-kernel 寄存器分配将寄存器文件成本从'ISA 全集'降到'kernel 实际需要'"**：memory-bound workload 算术强度低 → 使用寄存器少 → 只分配 kernel declaration 中声明的寄存器数 → 同样面积的寄存器文件可容纳更多 µthread → 更好的 DRAM 延迟隐藏。与 GPU 的固定寄存器集截然不同。

5. **"细粒度 thread 创建 + 完成后立即释放 = 消除 threadblock 粗粒度资源碎片"**：GPU SM 的 threadblock 在最后一个 warp 完成前不释放资源 → active warp ratio 波动在 0.5-1.0。µthread 完成后立即释放 → 新 µthread 立即填入 → 持续高利用率 → equivalent GPU-NDP 需要 4-16× FLOPS 才能匹配。

- 来源：CXL-M2NDP(MICRO'24)

### 实践启发
- **"CXL.mem 可以是控制通道"**：150ns 往返延迟让 store/load 指令成为可行的细粒度卸载原语。这类似于 RDMA 领域 UEP/UCCL-Tran 用 RDMA imm_data 做控制信号——都是"如果数据信道已经足够快，就可以复用为控制信道"的思路。
- **"Packet filter 是可推广的设备端控制原语"**：按地址范围分流（普通 vs 特殊功能）的模式不仅适用于 CXL 内存——可推广到任何基于地址的互联（SmartNIC 的 on-path processing、PCIe BAR MMIO 的多函数虚拟化）。
- **"Memory-bound workload 的执行模型需要从头设计，不能直接复用 CPU 或 GPU"**：CPU OoO 控制逻辑太重、GPU SIMT 地址计算冗余——两者都不是为 NDP 优化的。M²NDP 的设计体现了"从 workload 特征反推执行模型"的工程方法。类似 BatchGen "从批量推理的特征反推 coroutine 调度"——不是优化现有调度器，而是重新设计抽象。
- **"按需分配资源 + 细粒度回收 = 成本效率"**：Register provisioning + fine-grained thread spawning = 用 1/16 的 FLOPS 做到比 GPU-NDP 更好的 memory-bound 性能。可推广到其他"成本约束 > 峰值性能"的场景（边缘推理、IoT、嵌入式）。
- **"5 类 workload 覆盖了 NDP 的关键场景"**：OLAP + KV + LLM inference + DLRM + graph analytics → 都是 >100GB 内存占用 + 低算术强度 → 证明了 NDP 的通用性而非"为某个 workload 特调"。
