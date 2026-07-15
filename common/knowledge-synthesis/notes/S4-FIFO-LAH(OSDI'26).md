# S4-FIFO / LAH(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-xia.pdf
- **类型**: 论文-算法/系统
- **一句话 TL;DR**: Learning-Augmented Heuristics (LAH)——将数据面和控制面解耦，静态启发在数据面做快速读写，控制面异步学习 cache 级参数。S4-FIFO = Smart S3-FIFO，效率 +26%（vs S3-FIFO），最差 trace miss ratio 仅增加 0.8%（vs 3L-Cache 8.8%）。

## 核心问题

缓存淘汰算法分为两类：静态启发（S3-FIFO/LRU/2Q——简单、可预判、工业采用）和智能算法（ARC/LRB/LHD——自适应、可学习但复杂性高、易不稳定、未工业采用）。智能算法理论上应在效率和鲁棒性上同时超过启发式，但实际上**很少被采用**——原因是：objective mismatch（学习目标与真实缓存性能不一致）+ instability（在某些 trace 上差很多）。

## 关键洞察

1. **"Learning-Augmented Heuristics = 数据面+控制面解耦"**：数据面 = 静态启发逻辑（快速读写、简单、可预判），控制面 = 异步学习 cache 级参数（偶尔、非阻塞）。不是取代启发式——是用学习增强启发式的参数调优。
2. **"Cache-level learning > object-level learning"**：cache 级特征学习（如缓存大小、访问模式）比 per-object 预测（如 reuse distance）更稳健——不会因单个对象预测错误导致灾难性后果。类似 Merlin "per-object characterization" 但方向不同——LAH 认为 cache-level granularity 比 object-level 更稳健。
3. **"单模型预训练+嵌入 Static heuristic"**：4140 production traces 上预训练一个模型→直接嵌入 S4-FIFO→1035 evaluation traces 上无需 per-workload tuning。

- 来源：S4-FIFO / LAH(OSDI'26)
