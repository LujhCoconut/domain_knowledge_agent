# TileLoom(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-li-wei.pdf
- **类型**: 论文-编译器/系统
- **一句话 TL;DR**: MLIR-based 端到端框架，将 tile-based 程序（Triton kernel）编译到 spatial dataflow accelerators——自动 tile 到 core 的分布+on-chip network data reuse，在 Tenstorrent 两代系统上匹配 vendor library 性能。

## 核心问题

Spatial dataflow accelerators (Tenstorrent/Cerebras/Groq 等) 有潜力通过 on-chip network 绕开 von Neumann 内存瓶颈——但 programmability 是主要采用障碍。Tile-based 语言 (Triton/Halide/TVM) 提高可编程性，但编译到空间架构时 "tile-to-core mapping" 是核心困难——naive mapping 性能极差。

## 关键洞察

1. **"Automatic dataflow planning across cores"**：不仅是单 tile 内的代码生成→在空间分布的多核之间做 tile 分布+network communication→利用 on-chip 带宽（Tenstorrent 64 核 24.5 TB/s vs H100 L2 6 TB/s）
2. **"Hardware representation 捕获拓扑+内存层次+计算能力"**→使 tile-to-core mapping 可自动化+架构特定+可跨目标

- 来源：TileLoom(OSDI'26)

### 实践启发
- **"Spatial architectures 的编译器挑战从 '优化代码生成'变为 'tile-to-core dataflow planning'"**：与传统 GPU 编译完全不同——数据移动的显式管理是关键
