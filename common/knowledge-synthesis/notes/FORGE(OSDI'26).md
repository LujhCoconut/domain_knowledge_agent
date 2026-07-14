# FORGE(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-yang-zhijun.pdf
- **全称**: FORGE: Mitigating Synchronization Amplification for Memory-Disaggregated Caching Systems
- **作者**: Zhijun Yang, Yu Hua*, Ming Zhang, Menglei Chen, Yixiao Wang (Huazhong Univ. of Sci. & Tech.)
- **类型**: 论文-系统 (caching + disaggregated memory + distributed systems)
- **一句话 TL;DR**: 分离式内存（DM）将计算和内存分离为独立资源池——使缓存系统可以独立弹性扩展。但 DM 架构迫使关键的缓存管理操作（热度追踪、淘汰协调、内存碎片整理）跨越 CXL/RDMA 高延迟链路执行同步——即**同步放大**问题。FORGE 通过三个设计解决：基于相似性的**组级同步**（摊销开销）、无竞争 FIFO 队列编辑冷组、利用 FIFO 可预测性的**懒同步**（仅淘汰时才更新热度指标，并卸载到 RDMA NIC 片上内存加速）。vs SOTA 提升吞吐 **4.5×**，降低 P50/P99 延迟 **4.0×/7.5×**，1.14× 命中率。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **DM** (Disaggregated Memory) | 计算与内存分离为独立资源池——通过 CXL/RDMA 访问远端内存 |
| **Synchronization amplification** | DM 架构下缓存管理同步操作的数量和延迟因跨节点通信而放大——传统方案在 monolithic 服务器中对这些操作无感 |
| **FORGE** | 针对 DM 缓存系统同步效率的缓存系统 |
| **Group-level synchronization** | 将相似对象分组，按组（而非 per-object）进行同步——摊销跨节点开销 |
| **Contention-free FIFO queue** | 无竞争的热度感知 FIFO 队列——淘汰冷组时避免锁竞争 |
| **Lazy synchronization** | 仅在淘汰时 (just-in-time) 更新热度指标——而非每次访问时（即实时热度更新） |
| **RDMA NIC on-chip memory** | RDMA 网卡的片上内存——FORGE 将热度更新卸载到此以避免 CPU 参与 |
| **CN / MN** | Compute Node (CPU 池) / Memory Node (内存池)——DM 架构中的两类节点 |

## 背景与动机

### 问题
- DM 架构使缓存弹性扩展成为可能：独立扩展 CN（CPU）和 MN（内存）
- 但在 DM 架构下，三个关键的缓存管理任务受到毁灭性影响：
  1. **热度追踪**：每次访问需跨越 CXL/RDMA（∼350ns）更新热度→频率高→同步开销放大
  2. **淘汰协调**：多 CN 共享 MN 上的缓存→淘汰需要跨节点锁→竞争 + 延迟放大
  3. **内存碎片整理**：碎片化导致频繁的跨节点元数据更新
- 在此之前，DM 缓存系统仅关注内存容量扩展——完全忽略了同步放大问题

### 核心洞察
> "Synchronization amplification" 是 DM 缓存不可扩展的根本原因——传统的 per-object 同步在跨节点延迟下被放大到不可接受的水平。需要**将同步粒度从 per-object 提升到 per-group**，并将 hotness tracking 从"每次访问"推至"仅淘汰时"。

## 方案介绍

### FORGE 三个设计

**1. 基于相似性的组级同步**
- 将相似对象（相似热度、相似大小）分组成组
- 按组进行同步（组级粒度），而非每个对象单独同步
- 摊销跨节点通信开销

**2. 热度感知 + 无竞争 FIFO 淘汰**
- 使用 FIFO 队列追踪冷组
- 无锁设计：无竞争→在跨节点场景下至关重要
- 保留高命中率同时减少碎片化

**3. 懒同步 + RDMA NIC 卸载**
- 利用 FIFO 淘汰的**可预测性**：淘汰顺序可以提前知晓
- 仅在淘汰时才更新热度指标（just-in-time），而非每次访问
- 将热度更新卸载到 RDMA NIC 的**片上内存**中执行——避免 CPU 参与

## 证据与评估

| 指标 | 结果 |
|------|------|
| 吞吐 | 最高 **4.5×** |
| P50 延迟 | 降低 **4.0×** |
| P99 延迟 | 降低 **7.5×** |
| 命中率 | 平均 **1.14×** |
| 工作负载 | YCSB + 真实世界生产 trace |

## 整体评估

### 真正的新意
1. **首次命名并解决 DM 缓存中的"同步放大"问题**：之前的工作默认缓存管理是免费的（monolithic 假设），在 DM 架构中暴露出根本瓶颈
2. **"FIFO 可预测性→懒同步"的因果链**：FIFO 淘汰的已知顺序允许将热度更新推迟到最后一刻——这是一种针对 DM 延迟的精巧设计
3. **RDMA NIC 片上内存作为加速载体**：将热度更新计算卸载到 RDMA NIC 的片上内存——避免 CPU 参与和额外的网络往返

### 可复用启发
- "同步放大"是任何将共享数据结构跨高延迟链路扩展的系统中普遍存在的问题——不只是缓存，还包括锁、日志、索引、元数据等
- "懒同步"利用可预测性（FIFO order）来推迟操作——适用于时间结构已知的任何系统
- RDMA NIC 片上内存是一个被低估的计算卸载目标——它不仅用于数据传输，还可以执行轻量级数据操作
