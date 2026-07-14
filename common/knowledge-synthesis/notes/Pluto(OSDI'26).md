# Pluto(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-wu-ying-wei.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 分布式图分析的 advanced mirroring——静态部分镜像消除非生产性复制（memory -4×）+ 无镜像架构 + work migration compute-comm overlap，比 full mirroring 快 up to 3.8×，比现有开源系统快 up to 12×。

## 核心问题

Full mirroring（复制所有可能需要的远程数据）在分布式图分析中是标准做法，但内存开销 up to 4×，在高连接图上更大。内存容量增长落后于数据增长 → full mirroring 不可持续。

## 方案

1. **Static partial mirroring**：利用 "mirror heterogeneity"——不是所有数据复制都有生产性。识别并消除非生产性复制 → 减少内存的同时保持性能
2. **Mirror-free architecture**：对可无镜像高效运行的算法变体——完全消除复制开销
3. **Work migration**：将计算迁移到数据所在节点 + 早启动网络传输与本地计算重叠 → 隐藏通信延迟

## 可复用启发
- **"不是所有复制都有用——mirror heterogeneity"**：类似 DINGO 的 "不是所有 IO 都需要立即执行" 和 SPADE 的 "不是所有任务都需要立即调度"——识别并消除非生产性的资源消耗
- 来源：Pluto(OSDI'26)
