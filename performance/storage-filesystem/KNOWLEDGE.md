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
