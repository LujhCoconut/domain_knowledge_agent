# DeLFS(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-ahn.pdf
- **全称**: DeLFS: A Decentralized Log-Structured File System for Manycores
- **作者**: Taehwan Ahn, Chanhyeong Yu, Sangjin Lee, Yongseok Son (Chung-Ang University)
- **类型**: 论文-系统 (file system + concurrency)
- **一句话 TL;DR**: 现有 LFS（F2FS、MAX、ScaleLFS、F2FSJ）在 128 核上扩展性极差——多全局锁串行化 I/O，NVMe 原生 5.24 GB/s 但 LFS 仅 1.06 GB/s。DeLFS 实现去中心化 LFS 架构：per-core metadata/data domain + LFS-aware decentralized locking + 去纠缠的关键/延迟路径。vs F2FS 最高 **4.34×**, vs MAX 4.29×, vs F2FSJ 4.50×, vs ScaleLFS 2.00×。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **LFS** (Log-Structured File System) | 日志结构文件系统——将随机写入转化为顺序追加写入 |
| **DeLFS** | 去中心化 LFS——per-core domain + decentralized locking |
| **Per-core domain** | 每个 core 拥有自己的本地 metadata 和 data 区域——one(core)-to-one(resource) |
| **LFS-aware decentralized locking** | 将锁所有权分布到各 core，无死锁获取 + 解耦关键/可延迟路径 |
| **MAX** | 多核友好的 LFS——多独立 log，但仍有锁竞争 |
| **ScaleLFS** | 可扩展的 GC——并行化 GC + 并发 victim 管理 |
| **F2FS** (Flash-Friendly File System) | 从移动设备到服务器的广泛部署 LFS |

## 背景与动机

### 问题
- 现代 NVMe SSD 原生性能随 core 数扩展（128 核 5.24 GB/s）
- 现有 LFS 仅在 1.06 GB/s 水平——无论 core 数如何增加
- 即使添加 F2FS+ScaleCache（可扩展页缓存）也几乎无改善——瓶颈在**锁竞争**

### 三个挑战
1. **集中式的 metadata/data 管理**：全局锁在文件操作上串行化所有 core
2. **锁竞争在 GC 路径上也存在**：ScaleLFS 并行化 GC 但 victim 管理仍有全局竞争
3. **关键路径 vs 延迟路径纠缠**：必须原子完成的 critical updates 和可延迟的操作（如 block allocation）串行执行

## 方案介绍

### DeLFS 三组件

**1. Per-core metadata & data domain**
- 将 LFS 的元数据和数据布局分解为 per-core 域
- "One-core-to-one-resource" 模型——每个 core 主要操作本地资源
- 跨 core 交互最小化

**2. LFS-aware decentralized locking**
- 将锁所有权分布到 core，而非全局锁
- 死锁安全的获取协议
- 将某些更新解耦为**独立可执行操作**，同时保持原子性

**3. Disentangling critical & deferrable paths**
- 关键路径（必须原子完成）从延迟路径（可推迟）中分离
- 提高 concurrency
- 例：block 分配可以推迟，但文件 inode 更新必须原子

## 证据与评估

| 对比 | 加速 |
|------|------|
| vs F2FS | 最高 **4.34×** |
| vs MAX | 最高 **4.29×** |
| vs F2FSJ | 最高 **4.50×** |
| vs ScaleLFS | 最高 **2.00×** |
| 平台 | 128 核 + NVMe SSD (原生 5.24 GB/s) |

## 可复用启发

- "One-core-to-one-resource" 是消除锁竞争的根本方案——不优化锁，而是**消除共享**
- Per-core domain 是传统的分区策略在文件系统中的体现（类似 per-core slab allocator 或 per-cpu data structure）
- 路径解耦（critical vs deferrable）是提高并发度的通用策略——不是所有操作都需要原子完成
