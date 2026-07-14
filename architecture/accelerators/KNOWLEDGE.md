# Accelerators Architecture

加速器架构设计与编译优化。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| Spatial 数据流加速器 Tile 编译 | tile-to-core mapping, dataflow planning, MLIR, Triton, spatial architecture, on-chip network, data reuse | TileLoom(OSDI'26) |

---

## Spatial 数据流加速器 Tile 编译 (TileLoom)

### 核心问题
Spatial dataflow accelerators (Tenstorrent/Cerebras/Groq 等) 通过 on-chip network 直接转发数据绕过 von Neumann 内存瓶颈——64 核片上带宽可达 24.5 TB/s（vs H100 L2 6 TB/s）。但 programmability 是主要障碍：将 tile-based 程序 (Triton kernel) 编译到空间架构时，"tile-to-core 分布 + on-chip network 数据移动规划" 是核心困难——naive mapping 性能极差，大多数用户依赖厂商手工调优库。

### 关键洞察

1. **"编译器挑战从代码生成变为 dataflow planning"**：与传统 GPU 编译不同——空间架构上数据不需要回 shared cache→直接 core-to-core 转发→编译器必须显式规划数据流路径。类似 cpu 的 instruction scheduling 但对象是 tile 级的数据移动。
2. **"Hardware representation 捕获拓扑+内存层次+计算能力"**：使 dataflow planning 可以 (a) 自动化 (b) 架构感知 (c) 跨目标可移植。在 Tenstorrent 两代系统上匹配 vendor library 性能。

- 来源：TileLoom(OSDI'26)

### 实践启发
- **"Spatial architecture = 显式数据移动管理——编译器的角色根本不同"**：不是生成更好的 SIMD/SIMT 代码，而是规划 tile-to-core 的数据流。这是一个新的编译器设计空间
