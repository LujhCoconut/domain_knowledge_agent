# Sepia(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-song.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: DDIO 的 LLC miss 主要来自**冲突缺失**（而非容量缺失）——page coloring 可提升有效 LLC 容量 77.8-94.4%，仅需 3.5 核饱和 200Gbps（vs Linux 默认 6 核）。

## 核心问题

Intel DDIO 使 NIC 接收的数据可直接从 LLC 访问（避免 DRAM 往返），但 "leaky DMA"——数据在处理前被逐出 LLC。传统认为是 DDIO 保留容量太小。**本文发现冲突缺失（cache conflict）是主要共因**——Linux 默认内存分配器导致 page working set 在 sliced LLC 中分布不均。

## 方案：Sepia

- **Color-aware page allocator**：将 page 均匀分布到 LLC sets——消除冲突缺失
- DDIO 容量缺失只在 working set > LLC 总容量时发生（高负载时），而冲突缺失在容量充足时也可发生
- **仅 3.5 核饱和 200Gbps**（vs Linux 默认 6 核），LLC miss rate 仅 0.4%

## 可复用启发
- **"冲突缺失常被误诊为容量缺失"**：不仅是 DDIO——page cache、KV store 索引等场景中 page coloring 可大幅提升有效缓存容量
- **Sliced LLC 架构下 page placement matters 更多**——现代 CPU 的分布式 LLC 使 page coloring 比单 LLC 时代更重要
- 来源：Sepia(OSDI'26)
