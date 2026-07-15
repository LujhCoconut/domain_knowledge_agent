# Drs.NAS(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-wang-ruixuan.pdf
- **类型**: 论文-系统/ML
- **一句话 TL;DR**: 超高效 NAS for 推荐系统——superproxy 度量替代昂贵训练验证，搜索从 5-18 GPU-hours 降到 2 分钟 CPU。模型 108× 更小、89× 更少 FLOPs，AUC 持平或更优。

## 核心问题

推荐系统占 Meta 70%+ AI 推理 cycle，但人工设计架构不 scalable。NAS 自动化搜索但搜索成本极高（5-18 GPU-hours），且搜索结果仍计算-内存密集。两个瓶颈：(1) 搜索成本过高→不能快速迭代 (2) 搜索结果不够高效→实际部署困难。

## 关键洞察

1. **"Superproxy 度量替代训练验证"**：NAS 的主要搜索成本在反复训练-验证每个 candidate architecture。Superproxy 是一个无需训练的 metric，从 architecture graph 直接评估其质量和效率→消除训练 cost。类似 Merlin "per-object characterization 替代 workload classification"——用一个智能 metric 替代昂贵的过程。
2. **"Ultra-efficient results → 部署友好"**：不仅搜索快（2 min CPU），搜索结果也极致高效：模型 108× 更小、89× 更少 FLOPs，但 AUC 持平或更优。类似 ADAngel "oracle policy map"——搜索+结果同时优化。

- 来源：Drs.NAS(OSDI'26)
