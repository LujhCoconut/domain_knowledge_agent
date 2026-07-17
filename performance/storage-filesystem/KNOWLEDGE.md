# Storage & File Systems

存储系统与文件系统的性能优化和架构设计。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| LLM 预训练数据管线 | cross-DC checkpoint replication, proactive hot-file replication, storage-tier CPU offloading, HDFS | ByteDance DataPipeline(OSDI'26) |
| 多核可扩展文件系统 (LFS) | decentralized locking, per-core domain, log-structured, critical/deferrable path disentanglement | DeLFS(OSDI'26) |
| CXL 跨 SSD 计算资源共享 (Espresso) | JBOF, inter-SSD resource sharing, decentralized compute pooling, CXL interconnection, storage disaggregation | Espresso(OSDI'26) |
| DM 缓存同步放大缓解 (FORGE) | synchronization amplification, group-level sync, lazy hotness tracking, FIFO eviction, RDMA NIC offload | FORGE(OSDI'26) |
| 多组件协调式文件系统 | semi-kernel-bypass, shared-ownership metadata, split journaling, CSD offload, coordinated architecture | Oxbow(OSDI'26) |
| 声明式 IO 与维护任务复用 | declarative IO, IO wall, maintenance task coordination, inter-task IO reuse, HDD capacity scaling | DINGO(OSDI'26) |
| mmap-IO DFS 矩阵访问优化 | file-backed matrix, abstraction mismatch, page-granularity network I/O, DFS-agnostic runtime, lazy-expansion cache | Umap(OSDI'26) |
| 聚类型 SSD ANNS 生产系统 | clustering-based ANNS, userspace storage stack, learned pruning, GPU-accelerated index, SSD bandwidth | Helmsman(OSDI'26) |
| 宽条带矢量纠删码 | template-unfold structure, sub-packetization, vector codes, wide-stripe erasure coding, repair throughput | WiseCode(OSDI'26) |
| EBS 镜像预加载与 I/O 预测 | lazy loading, slow I/O, preloading, genetic algorithm, score-based block selection, zero-shot prediction, Jaccard Index, Alibaba EBS | ThinkAhead(FAST'26) |
| 容器镜像快速启动文件系统 | MPHF, FUSE, on-demand pulling, container cold start, metadata lookup, kernel-space caching, sparse files | CoFS(FAST'26) |
| 云本地存储三代演进与混合架构 | SPDK user-space, ASIC DPU offloading, ASIC+SoC co-design, SR-IOV, context switch elimination, ML I/O dispatch, local-cloud hybrid, S3-FIFO caching | Latte(FAST'26) |
| 磁带归档存储系统 | tape library, drive thrashing, asynchronous tape pool, batched erasure coding, dedicated drives, lifetime-based placement, bulk scheduling, wrap-aware read reordering | TapeOBS(FAST'26) |
| 排序增强压缩只读文件系统 | sort-enhanced compression, data mixture, similarity graph, subgraph partitioning, METIS, hotness grouping, read-only FS compression, chunk deduplication | RubikFS(FAST'26) |
| EB 级跨地域对象存储 | geo-distributed object store, two-layer encoding, XOR parity, LRC, replication factor optimization, sealed container immutability, metadata prefetch, EB-scale production | ACOS(FAST'26) |
| SSD-based LLM 推理 KV cache 卸载 | KV cache offloading, attention sparsity-SSD co-design, KV interleaving, speculative prefetch, temporal locality, DAG microtask scheduling, memory-constrained inference | SolidAttention(FAST'26) |
| 十亿级图-based 在线 ANNS | direct insert, GC-free update combining, space overprovision, approximate concurrency control, delta pruning, buffered delete, billion-scale vector search | OdinANN(FAST'26) |
| 云块存储 Range-as-a-Key 树索引 | range indexing, log-structured leaf, ablation-based search, two-stage GC, range-conscious split, consecutive write pattern, memory-efficient EBS index | RASK(FAST'26) |
| FDP SSD 仿真与表征 | Flexible Data Placement, write amplification, RUH isolation, II vs PI, Noisy RUH, Save Sequential, firmware design space, SSD emulation | WARP(FAST'26) |
| I/O Completion 自适应方法 | hybrid polling, per-I/O adaptive sleep, UNDER/OVER binary feedback, dynamic mode switching, SSD latency tracking, CPU contention | DPAS(FAST'26) |

---

## LLM 预训练数据管线

### 核心问题
训练作业需要持续供给 EB 级数据，但三个被忽视的瓶颈在分析 30K 作业的 90 天 trace 后才被发现：跨 DC 评估延迟使 GPU 空闲、启动时并发 checkpoint 加载导致 I/O 竞争、多模态数据转换饱和训练节点 CPU。

### 关键洞察

1. **跨 DC 评估作为被忽视的 GPU 浪费源**：伴随评估每 N 步加载远程 checkpoint → 网络传输主导延迟 → GPU 空闲
2. **全局命名空间 + 访问模式分析 → 预测性复制**：利用 checkpoint 访问的可预测性，在评估作业开始前就将数据推送到远程 DC
3. **主动热文件复制**：在作业启动前，根据历史模式预先复制热点 checkpoint 文件，避免数千 GPU 同时读取导致的 I/O 瓶颈
4. **存储层 CPU 卸载**：将数据预处理（解码/调整大小/增强）推送到 HDFS DataNode 的 CPU，而非训练节点的 CPU
- 来源：ByteDance DataPipeline(OSDI'26)

### 实践启发
- "数据供给"应与 MFU 和通信重叠并列作为训练效率的第一等瓶颈
- 30K 作业 × 90 天 trace 的分析方式为基础设施优化提供了量化基础
- "将计算带到数据"（storage-tier offload）在 AI 训练管线中同样适用

---

## 多核可扩展文件系统 (DeLFS)

### 核心问题
现有日志结构文件系统（F2FS、MAX、ScaleLFS、F2FSJ）在 128 核上扩展性极差——多个全局锁串行化所有文件操作，NVMe 原生 5.24 GB/s 但 LFS 仅 1.06 GB/s。即使添加可扩展页缓存也几乎无改善。

### 关键洞察

1. **"One-core-to-one-resource" 消除共享而非优化锁**：per-core metadata/data domain——每个 core 主要操作本地资源
2. **LFS-aware decentralized locking**：锁所有权分布到 core，死锁安全获取，解耦 critical/deferrable updates
3. **路径解耦（critical vs deferrable）**：inode 更新必须原子，但 block 分配可以推迟——提高并发度
- 来源：DeLFS(OSDI'26)

### 实践启发
- "不优化锁，而是消除共享"是解决锁竞争的根本方案——per-core 分区策略不仅适用于文件系统
- 关键路径/延迟路径的分解是提高并发度的通用策略——不是所有操作都需要原子同步
- 128 核上的真实瓶颈测量为后续多核文件系统设计提供了基准

---

## CXL 跨 SSD 计算资源共享 (Espresso)

### 核心问题
企业级 SSD 为处理 I/O 突发集成了大量计算资源（ARM CPU + 板载 DRAM），但 JBOF 部署中这些资源因 I/O burst 偶发性而严重低利用——同时大幅增加了 SSD 的单位成本。现有方案（传统 JBOF black-box、hypervisor 虚拟化）要么无法跨 SSD 共享资源，要么需要昂贵的数据复制并丢失 computation-near-data 优势。

### 关键洞察

1. **CXL 不仅是"存互联"——也是"计算互联"**：Espresso 将 CXL 从 memory pooling（容量扩展）重新定位为 **compute resource pooling**（跨 SSD 共享 CPU/DRAM）
2. **"Data stays, compute moves"**：忙碌 SSD 通过 CXL 将其元数据计算任务卸载到空闲 SSD——数据保留在原 flash 上，不复制
3. **去中心化资源管理匹配 JBOF 的 scale-out 本质**：各 SSD 自主决策何时请求远端计算资源——类似 P2P 负载均衡
4. **SSD 架构解耦**为功能独立组件是跨 SSD 资源共享的前提：compute/DRAM/flash 分离 → 精细化分配
- 来源：Espresso(OSDI'26)

### 实践启发
- "Compute resource pooling over CXL"不仅适用于 SSD——任何嵌入式计算资源池（SmartNIC、DPU、storage controller）都可以共享
- 去中心化资源管理在分布式存储中以特定方式适用——集中式管理器无法匹配分布式 I/O 模式
- "不需要数据移动的计算卸载"是 CXL shared memory 语义的独特优势

---

## DM 缓存同步放大缓解 (FORGE)

### 核心问题
分离式内存（DM）使缓存系统可以独立弹性扩展 CN（CPU）和 MN（内存），但关键的缓存管理任务（热度追踪、淘汰协调、内存碎片整理）被迫跨越 CXL/RDMA 高延迟链路进行同步——即**同步放大**。传统 monolithic 缓存方案对此完全无感。

### 关键洞察

1. **组级同步摊销跨节点通信**：将相似对象分组，按组进行同步而非 per-object——将 N 次同步减少为 1 次
2. **FIFO 可预测性→懒同步**：FIFO 淘汰顺序可预测→仅在淘汰时 (just-in-time) 更新热度指标，而非每次访问都更新（传统方案）
3. **RDMA NIC 片上内存用作加速载体**：将热度更新卸载到 RDMA NIC 的片上内存——消除 CPU 参与和额外网络往返
4. **无竞争 FIFO 队列**：多 CN 环境下无锁淘汰——在跨节点延迟下锁竞争是灾难性的
- 来源：FORGE(OSDI'26)

### 实践启发
- "同步放大"是任何将共享数据结构跨高延迟链路扩展的系统中共通问题——不仅仅是缓存
- "懒同步利用可预测性"是一个通用策略：当操作的顺序或时间可预测时，可将工作推迟到最后一刻
- RDMA NIC 片上内存是 under-explored 的计算卸载目标——不仅用于数据传输

---

## 多组件协调式文件系统 (Oxbow)

### 核心问题
存储硬件超过 14GB/s，传统 kernel-centric 架构成为瓶颈。但现有三个方向各有利弊：user-level FS 快但丢失 page cache/sendfile 等内核服务；kernel FS 功能全但 CPU-bound；CSD FS 省 CPU 但 PCIe 延迟 + 弱 device CPU。没有一个架构能同时满足高性能、内核互操作、低 CPU 开销、快速开发四个目标。

### 关键洞察

1. **"不对称 bypass"比"全 bypass"或"全 kernel"更优**：读和写的 kernel 价值不对称——读走 kernel page-fault path（复用 page cache + readahead + sendfile），写 bypass kernel 直接从 user→device
2. **"按写者分区共享状态"消除同步**（shared-ownership metadata）：每个 inode 属性只有一个 writer（oxLib 管 size/mtime，kernel 管 uid/gid）→ 消除同步瓶颈
3. **Split Journaling**：Host-device journaling——fsync 与后台 commit 解耦，利用 staging areas + DMA snapshot→CSD 卸载 crash-consistency 工作
- 来源：Oxbow(OSDI'26)

### 实践启发
- **"不等同 bypass，也不等同 kernel"——寻找不对称价值**：不是 kernel vs user-level 的二选一，而是识别每个路径上 kernel 的相对价值
- **"按写者分区"消除共享状态同步**：适用于任何多组件共享状态的设计——每个属性只有一个 writer
- **"将 crash-consistency 卸载到 CSD"**：journal/checkpoint 不是延迟关键路径——天然适合设备端后台执行

---

## 声明式 IO 与维护任务复用 (DINGO)

### 核心问题
HDD 容量快速增长（40TB→100TB）但带宽不按比例增长→**IO wall**：IO/TB 持续下降，到临界点后无法部署更大 HDD。6 个 hyperscaler trace 分析惊人发现：**45-70% 的 HDD IO 来自维护任务**（scrubbing、GC、capacity balancing）。这些任务访问大量数据、无单任务内复用→缓存无效，但**跨任务有显著数据重叠**——只是执行时间不对齐导致浪费。

### 关键洞察

1. **"维护任务本质上灵活但 imperative 接口不暴露灵活性"**：维护任务可以调整顺序、时间、甚至数据选择——但 read/write 接口把一切都锁死了。
2. **"声明式接口暴露窗口"**：Declare "scrub device D, deadline 7 days"→存储系统自行调度→跨任务制造数据复用窗口。
3. **"维护 IO 是隐藏的主要成本"**：45-70% 的 IO 用于维护——这在存储系统设计中被系统性忽视了。

- 来源：DINGO(OSDI'26)

### 实践启发
- **"声明式接口暴露灵活性"是通用模式**：后台 compaction、数据迁移、备份——任何"不需要精确控制每次 I/O 何时发生"的任务都可以受益
- **"跨任务协调代替单任务优化"**：系统级优化 > 单任务优化——与 SPADE（跨 job DAG 调度）和 Quota Marketplace（跨 BU 芯片分配）共享哲学

---

## mmap-IO DFS 矩阵访问优化 (Umap)

### 核心问题
File-Backed Matrix (FBM) 通过 mmap-IO 提供开箱即用的 out-of-core 访问——是 ML 推理加载模型权重、金融回测的矩阵访问的核心机制。但迁移到 disaggregated DFS 后（尽管 DFS 提供 25GB/s 远程带宽 >> 本地 SSD），反而出现 **3-10× 性能下降**、livelock（写密集阶段）、OOM kill（容器化环境）。

### 关键洞察

1. **"抽象层 mismatch 是迁移到 disaggregated 系统时的常见陷阱"**：mmap 为本地低延迟存储设计（page-granularity VM），DFS 是 block 语义+分布式元数据。每个 page fault → 碎片化远程 I/O + 大量元数据流量 + 跨节点同步。
2. **"Page fault 不是好的远程 I/O 原语"**：per-page 网络往返在高带宽网络下严重低效——需要 batch。
3. **"不修改 DFS 或内核的修复更可部署"**：DFS-agnostic runtime 在用户态修复三个问题——batch 网络请求、并发感知缓存、lazy-expansion 缓存管理。

- 来源：Umap(OSDI'26)

### 实践启发
- **"抽象 mismatch 诊断"是问题定位的通用方法**：当迁移到新技术栈时，先检查底层假设是否仍然成立——类似 Blowfish 发现的"硬件就绪→软件栈没跟上"
- **"Batch 化网络请求"是解决 page-granularity 低效的通用策略**：不仅是 mmap——任何细粒度远程访问模式都应考虑 batching

---

## 聚类型 SSD ANNS 生产系统 (Helmsman)

### 核心问题
小红书的 graph-based ANNS (HNSW) 在线服务必须全 DRAM 部署——随着用户和内容增长，内存和 CapEx/OpEx 爆炸。Hybrid SSD+DRAM (DiskANN) 的贪婪图遍历产生大量串行 I/O→延迟无法满足在线 SLA。但 SSD 硬件进步已改变旧 trade-off。

### 关键洞察

1. **"SSD 高带宽 > IOPS——batch 友好型算法重新获得优势"**：Clustering-based ANNS 天然无依赖→batched I/O→充分利用 NVMe 高带宽。Graph-based ANNS 的串行读取无法利用这一特性。
2. **"硬件进步改变了旧 trade-off——被遗忘的方案值得重新审视"**：clustering 曾因 CPU/IOPS 瓶颈被 graph-based 超越，现在 SSD 带宽提升改变了瓶颈位置。
3. **"ANNS 专用用户态存储栈"**：绕过 kernel I/O stack→SSD 带宽利用率从 20-60% 大幅提升。

- 来源：Helmsman(OSDI'26)

### 实践启发
- **"重新审视被遗忘的方案"是系统研究的重要策略**：当硬件进步改变瓶颈时，曾被抛弃的方案可能重新变得最优
- **"成本不是性能优化后的副产品——成本本身就是优化目标"**：40 台替代 35K core+0.35PB DRAM 不仅仅是效率提升，是范式改变

---

## 宽条带矢量纠删码 (WiseCode)

### 核心问题
宽条带纠删码（n≈100）以极低存储冗余（1.04-1.06×）提供高可靠性。Scalar codes (LRC/RS) 无法同时优化 repair traffic 和 storage overhead——LRC 减少修复流量但增加存储冗余，RS 存储最优但修复需读 k 个 chunks。Vector codes 理论上两者最优，但面对三个可扩展性障碍：sub-packetization 爆炸（Clay code α=426 at n=104）、系数搜索不可行、编解码复杂度过高。

### 关键洞察

1. **"Template-unfold 结构避免 sub-packetization 爆炸"**：不随 n 指数增长——使宽条带（n≈100）的矢量码首次变得实用。
2. **"Repetition-minimized 系数搜索"**：大幅降低系数搜索的计算成本——之前这一步在宽条带下不可行。
3. **"两阶段编解码算法"**：高效处理 ~100 宽条带——将理论上的最优性转化为实际可运行的系统。

- 来源：WiseCode(OSDI'26)

### 实践启发
- **"理论最优 ≠ 工程可行——可扩展性障碍需要结构创新而非参数调优"**：Vector codes 的理论优势数十年已知，但工程化需要打破 sub-packetization 等结构障碍
- **"存储 redundancy 每 1% 都价值数百万"**：在 EB 级集群中，1.04× vs 1.375× 的存储 overhead 差异可以建少一个数据中心

---

## 云本地存储三代演进 (Latte)

### 核心问题
NVMe SSD 硬件快速演进（IOPS 500K→1.5M，吞吐 3→6 GB/s），但软件栈无法匹配——内核态存储栈仅发挥 NVMe SSD 9.54% 的最大 IOPS 却消耗 140% CPU（1.4 核）。核心瓶颈是高频 context switch（VM_Exit + system call + interrupt）。同时，本地存储的固有缺陷（单盘故障→小时级不可用、容量受单 SSD 限制、物理绑定→区域部署受限）使大量场景无法使用。

### 关键洞察

1. **"Context switch 是存储栈性能的第一杀手——每一代演进消除一类 context switch"**：Espresso 消除 system call + interrupt（polling mode），Doppio 消除 VM_Exit（SR-IOV 直通 + 硬件 MSI 中断），Ristretto 在 Doppio 基础上用 ASIC 并行执行消除处理瓶颈。从内核栈到 Ristretto，软件开销累计降低 82.35%。

2. **"ASIC 做快路径、SoC 做灵活路径"的 co-design 是硬件 offload 的甜点**：纯 ASIC（Doppio）固定逻辑跟不上 SSD 代际演进（单 DPU 1.3M IOPS vs Gen4 SSD 1.5M+）且无法支持云特性（LVM/ZNS）；纯 SoC 成本高（ASIC 约 1/20 成本 + 1/3 功耗）。ASIC+SoC co-design（Ristretto）让 ASIC 处理 NVMe controller emulation、DMA routing、MSI injection 等快速路径，SoC 运行 SPDK + block abstraction layer 提供可编程的云特性支持。

3. **"ML-based per-I/O dispatching — 模型必须轻到可以 per-I/O 执行"**：Latte 用 Linear SVM（200ns 推理、30 权重 < 1KB）做 I/O 路由决策（cache vs backend）——关键是选择了极其轻量的模型，使 per-I/O 推理开销可忽略（SSD 延迟 > 10µs）。每 60s 自动检测延迟漂移 → 重训练 (~5s)。类似 LinnOS 和 Heimdall 的 ML 预测 I/O 延迟思路，但 Latte 聚焦于二分类路由而非延迟预测。

4. **"S3-FIFO candidate queue 过滤 one-hit-wonder——极低成本避免缓存污染"**：72% 的 I/O trace 对象只被访问一次。首次 miss 只记录元数据到 candidate queue（不占缓存空间），第二次访问才 promote 到主缓存 → 缓存命中率 > 82%。

5. **"价格是系统架构的一等公民——auto-scale IOPS 使成本从 13× 降到 2.1-4.0×"**：如果始终保证最高 IOPS（Latte Max），价格是本地盘的 13×；启用 auto-scale IOPS（Latte Auto），价格降到 2.1-4.0×。这是 Latte 能从 PoC 走向生产的关键——不是性能最优，而是性能/价格 Pareto 最优。

6. **"Append-only + 统一排序 → 消除 write-back inconsistency"**：两个写入路径（写缓存 + 刷新后端）都走 append-only 模式，且 compaction 期间保持相同顺序 → 无需复杂的事务协议即可保证一致性。

- 来源：Latte(FAST'26)

### 实践启发
- **"每消除一层 context switch 都有可测量的收益——用数据驱动架构决策"**：从 VM_Exit（5-12µs）到 system call 到 interrupt，每一步的量化数据指导了下一代设计方向。适用场景：任何性能敏感系统的瓶颈分析。
- **"ASIC+SoC co-design 适用于任何需要 '快速固定逻辑 + 灵活可编程逻辑' 的场景"**：不仅是存储（SmartNIC、安全 enclave、甚至 AI 推理的 speculative decode + fallback 都类似）。
- **"用最轻量的 ML 模型做 per-request 决策"的工程智慧**：不是追求最高精度（95.6% precision），而是保证 200ns 推理延迟可忽略 + 自动重训练适应 pattern drift。适用场景：任何需要在线决策的系统（缓存准入、负载均衡、QoS 分级）。
- **"价格作为一等架构约束"**：Latte 用 auto-scale 替代固定 IOPS 保证——这不仅是定价策略，更是架构决策（需要 backend 支持弹性 IOPS）。适用场景：云服务设计时，性能和成本的 trade-off 应该设计在架构中，而不是作为定价的 afterthought。

---

## 磁带归档存储系统 (TapeOBS)

### 核心问题
磁带 TCO 比 HDD 低 4.95×（CapEx 低 2.68×，OpEx 低 16.11×），但磁带的物理特征与分布式存储需求直接冲突：磁带库 1000 盘磁带仅 4 个驱动器（低 drive-to-tape 比），装载切换需 ~80s（有效带宽可降一半），磁带随机读需要 wind/rewind（大 seek time）。现有的磁带文件系统（LTFS/GLUFS）无法支撑大规模云归档服务的高吞吐写入和批量恢复需求。

### 关键洞察

1. **"全异步磁带池——异步不是为了不阻塞，而是为了创造批量调度的可能"**：HDD 缓冲池接收同步写入→DataBrain 按生存期（3 月粒度）分组→批量 flush 到同一磁带。没有 HDD 持久缓冲，按生存期分组是不可行的——因为有限的驱动器和 80s 装载时间阻止了为每个生存期组维护"随时可写"的磁带。缓冲池的语义从"性能缓存"升格为"调度可行性的架构前提"。

2. **"Dedicated Drives——静态硬件资源分配的胜利"**：4 个驱动器，2 写 + 1 读 + 1 内部——无动态调度、无抢占。写是 append-only（一个磁带写满才切换→无 thrashing）；内部操作长时间聚焦同一磁带→无 thrashing；读不可避免需要切换但隔离到 1 个驱动。当负载特征明确可预测时，最简单的静态分配就是最优的。

3. **"b-EC——用服务层 batch 替代持久层改造，实现 inter-object EC 效果"**：传统 intra-object EC 使每个对象跨度 m 盘磁带→读一个对象需要 m 个驱动器→大量 thrashing。方案：服务层聚合多个对象→单次 PLog append 密封→对象在 stripe 内横向切割→小对象仅存在于 1-2 盘磁带。不打破分层边界，不修改持久层代码——纯粹的"上层批处理利用下层原语"。

4. **"Wrap 感知的读排序——硬件物理约束直接转化为软件优化"**：现代磁带由数百个 wrap 组成，相邻 wrap 方向相反。TLS 将同一磁带上的请求按 wrap 方向分两队，队内按物理位置排序，先处理一个方向再处理另一个→消除因忽略方向导致的不必要 seek。

5. **"流控对齐驱动缓冲区速度——让硬件自己选择正确的速度"**：不稳定 I/O 提交速率使驱动误判主机速度→选择低速模式→带宽从 336→168 MB/s。TLS 周期性读取驱动缓冲区大小→估算驱动速度→限速提交→避免误判。这是一个"向硬件妥协而不是对抗"的精妙案例。

6. **"按生存期分组写入——让 GC 几乎零开销"**：同磁带上的对象大概率同时被删除→GC 时整盘磁带可直接回收，无需读有效数据+重写。这是"在写入时就为未来的 GC 做优化"的经典实践。

- 来源：TapeOBS(FAST'26)

### 实践启发
- **"全异步 = 可调度"的通用架构模式**：异步不仅隐藏延迟，更打开了全局调度优化的窗口——适用场景：任何"快速同步层 + 慢速持久层"的组合（日志系统、CDC 数据管道、LSM-Tree compaction、甚至 GPU memory offloading）
- **"物理约束建模→软件优化"的系统设计方法论**：每一步优化都源于对硬件物理特性的精确理解——drive-to-tape 比→专用分派；装载时间→批量调度；wrap 方向→读排序；buffer 速度检测→流控
- **"Staging buffer 作为调度基础设施而非性能层"**：类似 DGC 的 RDMA paging 使远程标记可行、LogDrive 的 shared log 使 durability-sequencing 解耦——缓冲的语义从"加速"变为"使能"
- **"服务层 batch = 跨对象 EC 的零伤方案"**：当系统分层不允许跨层语义泄露时，在上层做 batch 可以用下层的单对象原语实现跨对象优化——保持分层干净+实现全局优化
- **"Static allocation wins when workload is predictable"**：专用驱动器+全异步+append-only 使 TapeOBS 的写性能稳定在理论带宽的 93%（336/360MB/s）——不需要复杂的动态调度
- **"Headroom 不是浪费——是维修窗口"**：HDD 池 25% 空余 = 24h+ 用户写入缓冲 = 磁带库完全故障时仍有充分维修时间——容量规划中 headroom 的故障容错价值常被低估

---

## 排序增强压缩只读文件系统 (RubikFS)

### 核心问题
只读压缩文件系统（Squashfs/EROFS）分块压缩时遭遇 data mixture 问题：固定大小块划分将相似数据分散到不同块中→字典压缩（字典大小=块大小）无法消除跨块冗余→压缩比远低于 Direct（整 image 压缩）。增大块可部分缓解但引入严重读放大。现有相似度检测算法（Finesse/Odess）只能做"是否相似"二分类，不能量化部分相似度（0~1），无法用于排序优化。

### 关键洞察

1. **"排序 = 用数据重排替代更大的字典窗口"**：字典压缩的瓶颈是字典大小限制了能搜索重复字符串的距离。通过先按相似度排序 chunk 再分块压缩→相似内容物理上靠近→即使字典很小也能发现和消除冗余。LZ4 字典仅 64KB，排序后压缩比却大幅提升——相当于在数据布局层面做了"字典扩容"。

2. **"子图分割聚类 > 二分类相似度检测"**：传统方法问"两个 chunk 是否相似(0/1)"→精细去重的特例。RubikFS 构建相似度图（节点=chunk, 边=共享特征比例 0~1），用 METIS 子图分割聚类→最大化子图内总相似度→最大化压缩后冗余消除。这是从 yes/no 到 optimization 的范式转变。

3. **"Hotness grouper——用访问热度信息补偿排序的物理局部性损失"**：排序优化压缩比但破坏了 hot/cold 访问局部性→引入 kprobe 追踪启动阶段的 readpage→在排序前预分 hot/cold 子组→用 <0.11× 的压缩比代价换取 -70.70% 读放大。这是"多层信息协同"（语义层+物理层）的经典案例。

4. **"利用 write-once 的奢侈——只读场景允许在线系统不敢承受的优化"**：全图相似度计算（O(N²)→优化后 O(N)）、METIS 子图分割、全量数据重排——这些在可写文件系统上完全不可行（频繁写入→排序过时）。但只读 image 只构建一次→昂贵的一次性优化完全可接受。

5. **"FSC（定长 chunk）优于 CDC（内容定义 chunk），因为排序后页面不对齐的代价被放大"**：CDC 产生变长 chunk→页不对齐→排序后 chunk 被放入不同的大压缩块→读取一个 4KB 页可能触发多次块解压。FSC + 自适应 chunk size 在压缩比和数据局部性间取得了更好的平衡。

- 来源：RubikFS(FAST'26)

### 实践启发
- **"数据重排 = 字典扩容"的通用策略**：当压缩算法受限于字典/窗口大小时，重新排列数据使相似内容落入窗口内——不限于文件系统，适用于任何需要压缩但受限于窗口/块大小的场景（数据库列存压缩、网络包压缩、序列化协议）
- **"利用场景的独特自由度"是系统设计的高价值策略**：只读=可以排序；归档=可以异步；嵌入式=启动 pattern 可预测。识别并利用场景特有的自由度往往比通用优化更有效
- **"语义信息补偿物理副作用"**：hotness（语义层信息）补偿排序（物理层优化）对局部性的破坏——多层信息协同是系统设计中 under-explored 的方向
- **"子图分割作为通用聚类原语"**：当需要将 N 个有 pairwise 关系的实体聚类到 K 个容器中，且目标是最大化容器内的关系强度时，子图分割是自然的建模方式——不仅适用于 chunk 聚类，也适用于 task grouping、数据分区、甚至微服务部署

---

## EB 级跨地域对象存储 (ACOS)

### 核心问题
Apple 需要为 iCloud/Apple Music/Apple TV/Maps 等全球服务存储 EB 级对象数据，面临三重设计约束：高可用（容忍 disk/host/rack/DC 故障）、低成本（RF 每降 0.01 = 巨量资金）、可扩展（透明增加容量和吞吐）。ACOS 1.0 的双 region 全副本 + local LRC 总 RF=2.40→太贵；如何在不牺牲 11 nines 耐久性 + 5 nines 可用性的前提下将 RF 降至 1.50？

### 关键洞察

1. **"N-way XOR parity 替代跨域全副本——region 数量增长使简单编码获得低 RF"**：ACOS 2.0 从 2 region 扩展到 5 region → 将每个对象分 5 segment (4 data + 1 XOR parity) → 跨域 RF=5/4=1.25（vs 全副本 2.00）。不是编码算法的创新，而是"更多 region = 可容忍 1 个 region 故障同时让 (N-1)/N≈1"的架构决策。

2. **"两层故障分离——local LRC（高频低严重度）+ regional XOR（低频高严重度）"**：Local 层 (20,2,2) LRC 自动处理日常的盘/主机/机架故障→避免触发跨域修复流量（占 99.9%+ 事件）；Regional 层仅在 stamp/region 故障时使用 XOR parity 重建→低频触发，可接受较长修复时间。

3. **"Sealed container 不可变性——迁移零 I/O 放大"**：一旦 cluster sealed → 不可变 → rebalancer 跨 stamp 迁移时直接 file-level copy，无需对象级重建、无需重新 EC 编码→迁移 = 复制文件。不可变性在运维中的价值被系统性低估。

4. **"Metadata optimistic prefetch——用 99.999% 一致率 gamble 隐藏跨域延迟"**：GET 请求同时发 consistent + inconsistent metadata 读→ inconsistent 本地完成（个位数 ms P99.9）→ 立即触发 segment 预取→ consistent 返回后比对→匹配则流式返回→不一致（0.001%）则丢弃重读。

- 来源：ACOS(FAST'26)

### 实践启发
- **"Region 数量 = RF 优化的杠杆"**：更多 region → 可用更简单的纠删码达到更低 RF → N-way XOR 在 N=5 时 RF=1.25，在 N=10 时 RF=1.11。geo-distribution 不仅是为了更低延迟——也是存储成本优化的架构工具
- **"两层故障模型分离——local 和 regional 处理不同频率的故障"**：避免"一刀切"的复制策略——将频繁的小故障隔离在 local 层（快速自动修复），将罕见的大故障留给 regional 层（可接受人工介入时间）
- **"不变性 = 运维简化"**：一旦拥有不可变数据段（sealed containers），跨节点/跨数据中心迁移变为纯文件复制——对于 EB 级数据，这个简化意味着操作可行性的质变

---

## 十亿级图-based 在线 ANNS (OdinANN)

### 核心问题
十亿级 ANNS 索引需要在线向量更新（新数据不断产生→索引重建需数天不可接受）。现有图-based 索引（DiskANN）使用 buffered insert——先写入内存索引→达到阈值→批量 merge 到磁盘。但这有三个致命问题：(1) merge 期间磁盘读干扰前端搜索→P50 延迟抖动 2.44×；(2) 内存飙升——merge 3% 向量到十亿索引需 125GB；(3) merge 本身瓶颈——吞吐被 in-memory merge 的逐向量磁盘搜索限制在 ~3000 QPS，不随 batch 增长。

### 关键洞察

1. **"Fixed-size records → GC-free out-of-place update combining"**：图索引使用固定大小 record → 更新时写新 record 到预留空 slot，旧位置直接标记复用→无需 log-structured GC。空间过度分配（默认 2×）+ 三条分配规则（empty/page-path pages 优先）→组合多个 record 更新到一次页面写入→写放大仅 2×。用 ~$100 的 1TB SSD 换 >$200 的 128GB DRAM——TCO-driven 架构决策。

2. **"ANNS 的近似性 = 并发控制的自由度"**：不要求 ACID 的 atomicity 和 strict isolation→per-record consistency（搜索仅保证每条 record 一致快照）+ approximate neighbor snapshot（插入不验证结果集不变）→消除 per-node RW-lock 争用（DiskANN P99 spike 来源），降低临界区。

3. **"Delta pruning——假设历史状态正确，仅验证增量"**：已有邻接大概率满足三角不等式→仅检查新插入邻接→从 O(R²) 降为 O(R) →插入临界区计算开销骤降→仅当无法 prune 任何 neighbor 时 fallback 到 O(R²)。

4. **"Write-back cache + 后台 I/O 线程 → 磁盘 I/O 移出临界区"**：插入所需的磁盘读写都在搜索已缓存的页面中进行→写入仅更新 cache→后台提交到磁盘。临界区仅剩锁定+验证+裁剪+缓存更新→极短。

- 来源：OdinANN(FAST'26)

### 实践启发
- **"数据结构约束 = 系统优化机遇"**：Fixed-size records 被视为局限→但恰是 out-of-place 复用+GC-free 的基础。适用场景：任何已使用 fixed-size data layout 的存储系统——将其从约束转变为"原地复用"的优势
- **"TCO-driven overprovision——用便宜存储换昂贵内存"**：2× SSD 空间开销 < 内存节省的美元价值。这是"硬件价格比驱动架构决策"的又一案例——类似 Latte 的 auto-scale IOPS 降价格、ACOS 的 XOR-5 降 RF
- **"近似 = 放松一致性换并发"**：no atomicity, no isolation, approximate snapshots——在近似系统中，一致性可以降级为 per-record consistency→大幅简化并发控制。适用场景：推荐系统、缓存、流处理等 soft-state 应用
- **"Delta pruning = 增量验证的乐观策略"**：假设大部分旧状态正确→只检查新增→fallback to full check when needed。类似数据库的 incremental view maintenance——"乐观假设 + 安全降级"是通用优化模式

---

## 云块存储 Range-as-a-Key 树索引 (RASK)

### 核心问题
EBS-index 消耗 ~57% 节点内存，存储利用率受内存约束。I/O compaction 和 CU alignment 可将索引粒度从 per-block 扩大到 per-CW → 理论内存节省 58-91%。但现有索引（B-tree/ART/interval tree/segment tree/HINT）要么是 point-based（需要 eager/lazy 适配→overlap 处理代价高），要么是 range-aware 但面向 secondary index（不自动移除 covered ranges→内存浪费）。需要一种原生支持 range-as-a-key 的高性能低内存索引。

### 关键洞察

1. **"改变索引粒度而非优化索引结构——range-as-a-key 匹配连续写 workload"**：65-81.5% 写请求属于连续写序列(CW)→每个 N-block CW 用 1 个 range entry 替代 N 个 per-block entries→内存减少 N-1 个 entry。这是从 workload 特征出发的根本性优化——不是"让索引更快"，而是"让索引索引更少的对象"。

2. **"Log-structured leaf = LSM 思想的 leaf 级应用"**：append-only 写入→range overlap 不立即处理→leaf 满时 GC 批量回收 covered ranges。leaf 作为 GC 单元（足够小以保证及时回收+足够大以摊还开销）→在 range overlap 的写入代价和内存浪费间取得平衡。

3. **"Two-stage GC：73.8% 仅需 O(1) LT Map（同左界检查）→剩余 26.2% 用 NonOverlap List（并集检查）"**：发现绝大多数可回收 entries 被同左界的新 range 覆盖→hash map 极简处理 common case→仅必要时用有序列表做完整并集检查。先处理容易的→amortized cost 极低。

4. **"Ablation-based search：反向遍历 + Unfound List 逐步消融"**：不是一次性找所有重叠区间→反向 append-only leaf traversal + 维护 target range 未找到子区间有序列表→已找到部分 O(1) 移除→一旦 Unfound List 为空→early termination。log-structured layout 使新数据在后→反向遍历天然优先最新数据。

5. **"Range-conscious split：Ps 选 NonOverlap List 左界（天然无 overlap）→平衡 entry count"**：利用 GC 阶段已构建的 NonOverlap List 作为 split 候选（其左界一定不与任何 range 相交→零 fragmentation split）→选最平衡的。Fallback: leaf 内 range boundaries 中位数→保证不会触发级联 split。Merge 通过 Nfrag 计数器感知 fragmentation severity→触发 workload-aware 调整。

- 来源：RASK(FAST'26)

### 实践启发
- **"改变索引粒度匹配 workload 特征 > 优化索引结构"**：不是 faster per-block index→是 index fewer things。适用场景：任何发现"key 空间天然可聚合"的场景（时序数据的 time range index、日志的 session index、文件系统的 extent-based index）
- **"Log-structured leaf = append + batch GC 的 leaf 级 LSM"**：同时受益于 append 的写入效率和 GC 的批量处理——不限于 range index。适用场景：任何有大量 overwrite/覆盖更新的 in-memory index
- **"Two-stage GC = common case 极简 + complex case 完整"**：先统计 common case 占比→若高→用极简方案处理→仅剩余部分用完整方案。通用工程模式
- **"User-provided MergeRange/DivideValue = 索引与 value 语义解耦"**：索引不知道 value 是否可合并/如何拆分→通过回调函数让上层定义 value 语义→索引保持通用性。这是"机制与策略分离"在索引设计中的应用

---

## EBS 镜像预加载与 I/O 预测 (ThinkAhead)

### 核心问题

云 EBS 服务中，虚拟机/容器的虚拟磁盘（VD）从远程 OSS 创建的 lazy loading 模式虽然将冷启动时间从分钟级降到亚秒级，但首次访问数据块时仍需从远程拉取，导致大量 slow I/O。在阿里巴巴 EBS 的生产 trace 分析中，lazy loading 贡献了超过 40% 的慢 I/O（端到端延迟 >1s），成为 SLO 违规的主导因素。现有方案各有局限：缓存受限于 VD 创建的时空动态性，P2P 受限于镜像热度，新镜像抽象（FlacIO）不兼容已有生产架构。

### 关键洞察

1. **"同一镜像的 VD 创建存在强 intra-image 访问模式相似性"**：84.8% 的公共镜像和 72.7% 的用户自定义镜像中，同一镜像创建的不同 VD 的 I/O 序列余弦相似度 >0.9。这是数据驱动预加载可行性的基础——可以从历史 trace 推断未来访问。

2. **"PDF 峰值 + local minima 自动分类替代手工标注"**：不同 VD 创建的访问块数存在 PDF 多峰分布（如 40 GiB 镜像可访问 400 或 500 块，分别为 4% 和 2.5% 的 trace 序列）。ThinkAhead 用 PDF 的 local maxima→local minima 自动切分 category，再用 PCC 聚类进一步分组，无需人工标注，解决了 I/O 重排和丢失带来的 trace 变异问题。

3. **"Score = α×access_count + β×time_factor + (1-α-β)×min_time — 但 α,β 必须对每个网络带宽 bin 单独用遗传算法搜索"**：手工硬编码参数无法跨镜像和带宽条件通用（Figure 24 证明了 this）。遗传算法在无监督场景下自动搜索最优 (α,β) 组合，使预加载序列适应动态网络条件。

4. **"Zero-shot 的三级选择策略"**：对于无历史 trace 的镜像，先选同一 image family → 再选同一用户 → 再选元数据特征完全匹配的镜像，用 Jaccard Index 量化相似度。P50 JI 从同 family 不同用户的 0.08 跃升到同 metadata 的 0.87，说明分层过滤的必要性。

5. **"Hit rate > Accuracy 的设计取舍"**：在磁盘预加载场景中所有 fetched 数据最终都会被用到（与 CPU 缓存不同），因此 ThinkAhead 优先最大化 hit rate 而非 accuracy。这解释了为什么 HB（全知策略）的 accuracy 高但 latency 反而更差——它忽略了 access count，在低带宽下排队严重。

- 来源：ThinkAhead(FAST'26)

### 实践启发

- **"PDF 自动聚类是处理 noisy trace 序列的轻量方案"**：不需要 ML/深度学习，仅用统计分布 + PCC + 聚类即可有效从变异大的 trace 中提取稳定 pattern。适用于任何"同一任务多次执行的 trace 分析"场景（CI/CD pipeline profiling、数据库 query plan regression、分布式 job 性能分析）。
- **"遗传算法 + 带宽 binning 是处理动态网络条件下参数搜索的通用模式"**：将连续带宽离散化→每个 bin 独立搜索参数→运行时按实时带宽查表→切换。适用场景：CDN routing、streaming ABR、adaptive prefetching。
- **"Zero-shot 的层级相似度匹配可推广到任何 cold-start 问题"**：先 metadata 粗选→再 feature 精选→逐层放宽直到找到足够的训练数据。适用于推荐系统 cold-start、新 VM 类型 sizing、新容器镜像启动优化。
- **"Preloading vs caching 的根本差异：所有数据最终都会被用到 → hit rate > accuracy"**：这一洞察可指导任何"确定性最终消费所有数据"的预加载场景（软件包下载、game asset streaming、ML 模型 artifact 加载）的设计决策。
- **"Three priority queues 解耦 preload 和 on-demand"**：Missed block（高优）→ Preload（中优）→ Left block（低优）的优先级分离，确保预加载永远不会 block 正在等待的用户请求。这是一个通用的"speculation should never hurt correctness"的模式。

---

## 容器镜像快速启动文件系统 (CoFS)

### 核心问题

容器冷启动中，image pulling 占 76% 的启动时间，但仅 6.4% 的数据被实际读取。现有 on-demand pulling 方案（Nydus-fuse、eStargz）基于 FUSE 实现，但 FUSE 的固有设计导致每次 LOOKUP 和 READ 都需要 context switch 到 userspace daemon，带来显著的元数据查找延迟和数据拷贝开销。Nydus-erofs 试图通过内核态 erofs+fscache 绕过 FUSE，但首次访问的调用链（erofs→fscache→userspace daemon→同步写盘→通知→返回）反而比 Nydus-fuse 更慢，且 fscache 增加了维护复杂度。

### 关键洞察

1. **"容器镜像只构建一次，文件系统树是固定只读的——这是 MPHF 的理想应用场景"**：MPHF（Minimal Perfect Hash Function）是零冲突、空间最优的哈希函数，但需要固定的 key 集合。容器镜像的文件集合在 build 时固定不变，恰好满足 MPHF 的前提。CoFS 在 build 时构建 MPHF（以 parent inode + filename 为 key），将文件元数据按哈希值密集排列存储，lookup 时仅需计算哈希值 + 一次 I/O 即可定位目标 inode，完全绕过 FUSE userspace round-trip。

2. **"少于一次 I/O 的元数据查找"**：若目标磁盘块已在 page cache 中，则 0 次 I/O；否则仅需 1 次。对比传统本地文件系统（ext4）的 inode 查找需要遍历目录项，I/O 次数依赖目录大小和深度。这一差距在深层目录结构和大目录中尤为显著。

3. **"双 MPHF 实现并行路径解析"**：MPHF 算法允许任意指定目标哈希值后逆向构造哈希函数。CoFS 构造两个 MPHF——一个用 (parent inode + filename) 映射，另一个用 (full path) 映射到相同的哈希值。通过 kprobe 拦截 do_filp_open，当检测到深度 >3 的 CoFS 路径时，workqueue 内核线程自底向上并行解析各层 inode（底层的 inode 已在内存中→其祖先也必然已在内存中），与 VFS 自顶向下的顺序路径解析并发执行。

4. **"kernel-space 直接访问缓存数据消除 FUSE read 开销"**：CoFS 在 host 文件系统上维护稀疏文件（sparse file）镜像远程文件。首次读取时走 FUSE 慢路径（cofs-driver→cofs-snapshotter→下载→返回），同时 cofs-snapshotter 异步将数据写入稀疏文件对应偏移。后续读取时，cofs-driver 通过 vfs_lseek(SEEK_HOLE) 判断数据是否已缓存，若是则直接调用 vfs_read 从 host 文件系统读取——零 context switch、零数据拷贝。此外，利用文件系统 inode 锁保证 write 和 lseek 互斥，确保并发安全。

- 来源：CoFS(FAST'26)

### 实践启发

- **"MPHF 适用于任何'固定 key 集合 + 频繁查找'的场景"**：不限于容器镜像——包管理器索引、静态网站的 file routing、firmware 文件系统、read-only database 索引都可受益。MPHF 零冲突 + O(1) 查找 + 空间最优（~2.46 bits/key）的特性在这些场景中是对传统哈希表或 B-tree 索引的降维打击。
- **"双哈希函数（不同 key→相同 value）+ 并行解析"是可推广的加速模式**：任何需要"从不同入口定位同一资源"的场景都可以用多个 MPHF 共享 value array，然后并行查询。例如：文件系统同时按 inode number 和 full path 查找、DNS 同时按域名和 IP 查找。
- **"kernel-space cache + sparse file + SEEK_HOLE 是零开销 FUSE 缓存的通用方案"**：利用 host 文件系统的 sparse file 特性，不需要维护独立的缓存元数据——vfs_lseek(SEEK_HOLE) 本身就是缓存命中判断。适用于任何 FUSE-based 读缓存场景。
- **"异步写回 + inode lock 的并发控制"**：cofs-snapshotter 异步写数据到镜像文件，cofs-driver 通过 host FS 的 inode lock 保证与 lseek 互斥——不引入额外锁机制，直接利用 VFS 已有的并发控制。这是一个"不要重新发明锁"的工程范例。
