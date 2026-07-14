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
