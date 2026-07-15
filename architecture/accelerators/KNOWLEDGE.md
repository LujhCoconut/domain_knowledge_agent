# Accelerators Architecture

加速器架构设计与编译优化。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| Spatial 数据流加速器 Tile 编译 | tile-to-core mapping, dataflow planning, MLIR, Triton, spatial architecture, on-chip network, data reuse | TileLoom(OSDI'26) |
| Microkernel FPGA Shell | μShell, hardware IPC, composable modules, vFPGA, capability isolation, component-aware scheduling | μShell(OSDI'26) |
| 混合量子-经典加速 | hybrid tensor network, quantum-classical compilation, QPU-GPU co-execution, tensor contraction, declarative hybrid programming | qTPU(OSDI'26) |

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

---

## Microkernel FPGA Shell (μShell)

### 核心问题
现有 FPGA shell 为**单体应用**设计——所有硬件模块静态连接为单个不可分的加速器在一个 vFPGA 上。但实际应用是模块化的、可组合的（共享函数使用导致模块间达 93% 相关性）。单体方法：改一个模块→重建整个加速器、不可跨 vFPGA 扩展、所有模块被每个应用实例化→资源浪费、切换应用需完全重配置→调度开销大。

### 关键洞察

1. **"Microkernel 原则应用于 FPGA——硬件模块 = 进程"**：加速器分解为可共享、可组合的硬件模块→部署到独立 vFPGA→通过硬件 IPC 动态连接。类似 OS 中 microkernel 将服务分解为独立用户态进程——最小化内核、IPC 作为核心原语。
2. **"Capability-enforced isolation"**：硬件模块间通过 capability 机制隔离——类似 OS 的 capability-based security。不仅是隔离，也是组合的基础——模块不知道也不需要知道其他模块的具体实现。
3. **"Component-aware task scheduler"**：知道哪些模块被哪些应用使用→高效调度 vFPGA 资源。类似 vBOIDs "container-aware scheduling"——理解应用结构优于盲目调度。

- 来源：μShell(OSDI'26)

### 实践启发
- **"Microkernel 思想可迁移到硬件设计"**：IPC 作为硬件模块间通信原语、capability 作为隔离机制、细粒度模块化 > 单体重构。类似 Arca "OS 为 serverless 重新设计"——μShell "FPGA shell 为模块化应用重新设计"
- **"静态连接→动态 IPC 是 FPGA 可组合性的关键"**：类似 Spice "spliceVMA" 和 Nixie "temporal multiplexing"——从静态分配转向动态组合

---

## 混合量子-经典加速 (qTPU)

### 核心问题
经典加速器无法高效表示指数扩展问题（量子纠缠态→需要 2^n 经典内存）；QPU 适合此类问题但噪声大、错误率高、吞吐极低。实际应用需要**混合量子-经典执行**——但现有编程范式是手工 partition+orchestrate 的 ad hoc 方式，缺乏统一抽象→无法做跨量子-经典边界的全局优化。

### 关键洞察

1. **"hTN (hybrid tensor network)——统一量子-经典计算的单一抽象"**：张量网络不仅能表示量子态，还能捕获经典计算与量子计算之间的数据流和依赖关系。类似 VTC "virtual tensor" 但跨 quantum/classical 边界——一个张量可以部分在 GPU 上收缩、部分在 QPU 上执行。
2. **"编译器平衡经典成本与量子误差——非平凡 trade-off"**：在经典端多做计算可以降低 QPU 需要的 qubit 数或电路深度→减少量子误差。qTPU 编译器全局优化这个 trade-off，类似 Kareus "joint optimize dynamic+static energy"——两个目标不是独立的。
3. **"Declarative specification → holistic optimization——compiler-driven for quantum"**：声明式编程使编译器可以跨量子-经典边界做全局优化，类似于 classical domain 中 Twill/GraCE/MPK 的 compiler-driven 方法。

- 来源：qTPU(OSDI'26)

### 实践启发
- **"hTN 是 quantum-classical 的 IR"**：张量网络作为中间表示统一量子+经典计算→编译器可见全貌→可全局优化。类似 TileLoom "MLIR-based"——统一 IR 是异构编译的基础
- **"经典计算可以减少量子误差——不是独立目标"**：经典 overhead 和量子 error rate 之间存在 trade-off→多做经典端工作可以降低量子端错误率→编译器需要同时优化两者
