# RASK(FAST'26)

- **来源**: https://www.usenix.org/system/files/fast26-zhao.pdf, FAST '26
- **作者**: Haoru Zhao, Mingkai Dong, Erci Xu (SJTU), Zhongyu Wang (Alibaba), Haibo Chen (SJTU)
- **一句话 TL;DR**: 云块存储的 **range-as-a-key 树索引**——利用写请求倾向于连续块范围(CW ratio 65-81.5%)，直接索引块范围而非单块，通过 log-structured leaf + ablation-based search + two-stage GC + range-conscious split/merge，内存降 98.9%，吞吐升 31.0× vs 10种 SOTA 索引。
- **资料类型**: 论文-系统（存储索引+数据结构）

---

## 重要术语解释

| 术语 | 解释 | 作用 |
|------|------|------|
| EBS-index | 云块存储中映射 LBA→DFS 位置的索引（LBAIndex + CompressIndex） | 内存瓶颈来源（占 ~57% 节点内存） |
| CW (Consecutive Write) | 观察窗口内时空连续的写请求序列 | 核心 workload 模式发现 |
| Long CW Ratio | 属于 long CW(≥2 请求)的写请求占比 | 65-81.5%，验证 range-as-a-key 价值 |
| I/O Compaction | SegmentCache flush 时重排+合并写入为 CWs | 第一层优化：扩大索引粒度到 CW |
| CU Alignment | 自适应压缩：CW>4 blocks 按 CW 压缩 | 第二层优化：CompressIndex 粒度从 4-block→CW |
| RKey (Range as a Key) | 以 LBA range 为索引 key，替代 per-block key | 核心范式转变 |
| RASK | Range-AS-a-Key tree index，ART 内部节点 + log-structured leaf | 本文系统 |
| Log-structured Leaf | append-only leaf，GC 批量回收 covered ranges | 高效处理 range overlap |
| Ablation-based Search | 反向遍历 leaf，逐步消融(ablate)目标 range 的未找到子区间 | 重叠 range 的高效查找 |
| Two-stage GC | Lightweight GC(检查同左界→O(1)) + Normal GC(NonOverlap List 并集检查) | 减少写阻塞时间 |
| NonOverlap List | 有序不重叠区间列表，追踪已处理 ranges 的并集 | Normal GC 的核心数据结构 |
| LT Map | 左界→最大右界的 hash map | Lightweight GC (73.8% reclaim 仅靠此) |
| Range-conscious Split | 选取 Ps 候选（NonOverlap List 左界）中平衡 entry count 的 | 避免 split 导致的 range fragmentation |
| Nfrag | leaf header 中计数碎片化 range 插入次数 | 触发 merge/resplit 的阈值 |
| MergeRange / DivideValue | 用户注册函数(merge/divide range 的 value) | value 也可能是 range |

---

## 背景与动机

### EBS 索引成为内存瓶颈

阿里云 EBS-index 消耗 ~**57.1%** 节点内存，最严重时 ~10% 集群面临 ~35% 存储浪费（无法索引=不可用）。

**根因分析**：EBS-index 的 LBAIndex + CompressIndex 虽然已极度优化（优于 B-tree/ART/PGM-Index），但：
- LBAIndex per-write entry + log-structured 多版本→内存开销大
- CompressIndex per-4-block CU→与数据量等比增长

修改架构/替换索引结构/换压缩方案均无法根本解决——需要利用 workload 特征。

### 核心发现：写请求倾向连续块范围

- **65-81.5%** 写请求属于 long CW（≥2 请求的 write sequence）（观察窗口=36）
- **>85.4%** 读请求从 CW 起始位置开始
- **根因**：FS journaling + app-level sequential writes (Redis/MySQL/ES 等)
- 不仅限于阿里云：Google(51.6%), Meta(90.3%), Tencent traces 均呈现相同模式

### Range-as-a-Key 的潜在收益

- **I/O Compaction**：SegmentCache 重排合并→LBAIndex entry count **-58.4~77.0%**
- **CU Alignment**：按 CW 自适应压缩→CompressIndex entry count **-69.1~91.1%**
- **整体理论内存节省**：**58.4~91.1%**

---

## 方案设计

### RASK 结构

```
Internal nodes: ART (trie, path compression, memory-efficient)
Leaf nodes:    Log-structured (append-only, globally ordered by anchor key)
               ├─ Range Array (ranges sorted by insertion time)
               ├─ Value Array
               ├─ Header (entry count, concurrency info, Nfrag)
               └─ Prev/Next pointers (doubly-linked list)
```

### Challenge-1: Range Overlap

| 技术 | 原理 | 效果 |
|------|------|------|
| **Log-structured leaf** | Append-only + GC 仅在 leaf 满时批量回收 covered ranges | 写路径不阻塞在 overlap 处理 |
| **Ablation-based search** | 反向遍历 leaf + Unfound List 追踪未找到子区间 | O(1)移除已找到交集 |
| **Two-stage GC** | Lightweight GC (O(1) LT Map: 检查同左界→回收) + Normal GC (NonOverlap List: 并集检查) | **73.8%** reclaimable entries 仅靠 lightweight GC |
| **Early termination** | 一旦 target range 完全被找到→停止搜索 | log-structured 布局天然支持 |

### Challenge-2: Range Fragmentation

| 技术 | 原理 |
|------|------|
| **Range-conscious split** | Ps 候选从 NonOverlap List 左界取→选最平衡 entry count 的。Fallback: 从 leaf 内 range boundaries 取中位数→保证不溢出 |
| **Workload-aware merge/resplit** | Nfrag 超过阈值→normal GC both leaves→合并 entries→若 fit→merge；否则 resplit（产生更适应新 workload 的分区） |
| **MergeRange function** | 用户定义同源 range 能否合并（e.g., 连续 LBA + 连续 DFS location） |
| **DivideValue function** | 用户定义当 range 跨越 split point 时如何拆分 value |

---

## 评估数据

| 指标 | 结果 |
|------|------|
| 内存 vs 10 SOTA indexes | **-45.3~98.9%** |
| 吞吐 vs 10 SOTA indexes | **1.37~32.0×** |
| 尾延迟 | **-48.2~97.4%** |
| RocksDB 集成（DFS metadata） | 吞吐 **6.46×** vs skiplist RocksDB |
| 四生产 trace（Alibaba/Google/Meta/Tencent） | 全面验证 |

---

## 整体评估

### 新意

1. **"Range as a Key"是索引范式转变**：不是优化 per-block index→而是从 workload 本质（连续写入）出发，改变索引粒度。65-81.5% long CW ratio 是使这一范式可行的工作负载基础。

2. **"Log-structured leaf = 为 range index 特化的 LSM"**：传统 LSM 的 level 间 merge→RASK 的 leaf 内部 append+GC。leaf 作为 GC 单元（fine-grained enough to be timely, coarse enough to be efficient）→在 range overlap 和 write performance 间取得平衡。

3. **"Ablation-based search = range-aware 的增量查找"**：不是一次性找所有重叠区间→逐步消融目标 range→Unfound List 单调缩小→O(1) 移除已找到部分。

4. **"Two-stage GC：LT Map(O(1))先回收73.8%→NonOverlap List 再彻底回收"**：发现"大部分回收只需看同左界的覆盖关系"→用极简的 hash map 处理常见 case→复杂逻辑仅在必要时执行。

### 优点

- workload 分析扎实：Alibaba EBS 四集群两周 trace + Google/Meta/Tencent 交叉验证
- 问题根源追踪完整：从 EBS 架构→Index 瓶颈→workload 特征→Range-as-a-Key→RASK 设计
- 两个挑战（overlap + fragmentation）的解决方案互相配合（log-structured leaf 同时服务 write/read/GC）
- 跨场景验证（EBS + flash cache + DFS metadata service + RocksDB 集成）

### 局限

- 当前为 in-memory index，持久化由上层应用负责
- CW detection 依赖 SegmentCache 的存在→对无缓存层的系统需额外适配
- Cross-leaf read 的一致性 ≈ point index 的水平（~0.0394% inconsistent），未做全 leaf snapshot
- Range fragmentation 的 Nfrag 阈值是经验值，未提供自适应

### 适用条件

- Range-write heavy workloads（连续写占比 > 50%）
- 云块存储/Flash cache/DFS metadata service 等需要 LBA→物理位置映射的场景
- 内存是瓶颈

### 可复用启发

1. **"改变索引粒度匹配 workload 特征——不是优化索引结构，是优化索引的对象"**：不是 faster per-block index→是 index fewer things (ranges instead of blocks)。类似 OdinANN 的"fixed-size record→GC-free"——利用 workload/data 的固有属性而非优化现有操作。

2. **"Log-structured leaf = LSM 思想的 leaf 级应用"**：append + GC batch 回收→同时受益于 append 的写入效率和 GC 的批量处理。适用场景：任何需要处理 overlapping range updates 的索引结构。

3. **"Two-stage GC = 最常见 case 极简处理 + 复杂 case 完整处理"**：73.8% reclaimable 仅需 O(1) LT Map 检查同左界→剩余 26.2% 用 NonOverlap List 并集检查。先处理容易的→剩余交给完整逻辑→amortized cost 极低。

4. **"User-provided MergeRange/DivideValue = 索引与 value 语义解耦"**：索引不知道 value 是 range 还是 point→通过用户注册函数处理 value 连续性判断和拆分。使 RASK 成为真正的 general-purpose range index。

### 讨论问题

- 如果 workload 的 CW ratio 下降（如大量随机写覆盖），range-as-a-key 是否退化为 per-block index（每个 range 长度=1）→RASK 是否有 fallback 路径？
- 多节点分布式的 range index（如跨多个 BlockServer 的分片）如何协同处理 range overlap？
