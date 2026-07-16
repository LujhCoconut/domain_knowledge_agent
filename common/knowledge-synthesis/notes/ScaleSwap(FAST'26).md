# ScaleSwap(FAST'26)

- **来源**: https://www.usenix.org/system/files/fast26-ahn.pdf, FAST '26
- **作者**: Taehwan Ahn, Chanhyeong Yu, Sangjin Lee, Yongseok Son (Chung-Ang University)
- **一句话 TL;DR**: 面向多核+全闪 swap 阵列的**去中心化 OS swap 系统**——one-to-one core-centric swap 模型(每核独占 swap metadata/cache/space) + opportunistic inter-core assistance(跨核委托 metadata 访问) + core-affinity LRU(每核独立 LRU 列表), 128核+8 NVMe SSD 下吞吐 3.4× Linux swap, 延迟 -11.5×。

## 核心问题

Linux swap 的 all-to-all 模型在多核+多 SSD 下严重不可扩展: 所有核心共享 swap metadata + LRU 列表 → 锁争用剧烈 → 128核 8 SSD 时吞吐仅 ~2GB/s (vs RAID 0 raw throughput ~20GB/s)。Redis/图计算等 memory-intensive 工作负载需要 >物理内存容量(DRAM cost ~$4.22/GB vs SSD ~$0.16/GB → 26×)。全闪 swap 阵列是低成本内存扩展的实用方案, 但 OS swap 系统自身成为瓶颈。

## 方案设计

### 1. Core-Centric Swap Resource Management (One-to-One 模型)

每个 core 独占:
- swap metadata (swap_info_struct → 无全局锁)
- swap cache (per-core page cache → 无跨核查找争用)
- swap space (per-core SSD allocation)

→ 消除 all-to-all 模型中的集中式锁竞争

### 2. Opportunistic Inter-Core Swap Assistance

当前 core 需要访问其他 core 的 swap metadata 时:
- 通过 lightweight message passing 委托目标 core 执行(而非直接加锁访问)
- 保证 memory consistency 的前提下不阻塞当前 core

### 3. Core-Affinity Page and LRU Management

- 每 core 独立 LRU 列表 → 消除 per-node LRU 的争用
- 页面分配亲和于发起 swap 的 core → 提升 locality

## 关键数据

| 指标 | ScaleSwap vs Linux swap | vs TMO | vs ExtMEM |
|------|------------------------|--------|-----------|
| 吞吐 | **3.4×** | **+64%** | **5×** |
| 平均延迟 | **-11.5×** | — | — |
| 128 核 + 8 SSD 扩展性 | 近线性 | — | — |

## 可复用启发

1. **"All-to-all → one-to-one 是消除锁争用的根本解法"**: 不优化锁→消除共享。类似 DeLFS 的 per-core domain 和 OdinANN 的 GC-free overprovision — 根除共享而非优化竞争

2. **"Inter-core assistance = 消息传递替代共享内存锁"**: 需要跨核访问时→委托而非加锁。异步协作机制比全局锁的扩展性好得多

3. **"Per-core LRU = LRU 的 NUMA 化"**: 全局 LRU 锁是 swap 性能的主要瓶颈→per-core 独立 LRU 消除此瓶颈。代价是全局 LRU 精度降低→但全闪 swap 场景下带宽优先级高于 LRU 精度

## 归档

已归档到 `performance/system-tuning/` (OS 内核 swap 优化)。
