# Storage Infrastructure & Data Pipelines

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| LLM 预训练数据管线 | cross-DC checkpoint replication, proactive hot-file replication, storage-tier CPU offloading, HDFS | ByteDance DataPipeline(OSDI'26) |
| 多核可扩展文件系统 (LFS) | decentralized locking, per-core domain, log-structured, critical/deferrable path disentanglement | DeLFS(OSDI'26) |

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
