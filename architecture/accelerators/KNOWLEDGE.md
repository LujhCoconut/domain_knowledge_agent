# Accelerators Architecture

加速器架构设计与编译优化。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| Spatial 数据流加速器 Tile 编译 | tile-to-core mapping, dataflow planning, MLIR, Triton, spatial architecture, on-chip network, data reuse | TileLoom(OSDI'26) |
| Microkernel FPGA Shell | μShell, hardware IPC, composable modules, vFPGA, capability isolation, component-aware scheduling | μShell(OSDI'26) |
| 混合量子-经典加速 | hybrid tensor network, quantum-classical compilation, QPU-GPU co-execution, tensor contraction, declarative hybrid programming | qTPU(OSDI'26) |
| SSD 总线挂载 GNN 空间加速器 | systolic array, vector aggregation, spatial accelerator, in-storage computing, multi-level NDP, die-level sampler, channel-level router | BeaconGNN(HPCA'24) |
| CXL 内存 NDP 通用加速单元 | RISC-V vector, FGMT, μthreading, memory-mapped ISA, packet filter, register provisioning, scratchpad memory | CXL-M2NDP(MICRO'24) |

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

---

## SSD 总线挂载 GNN 空间加速器 (BeaconGNN)

### 核心问题
GNN 计算（embedding aggregation + GEMM update）高度并行适合加速器，但数据（subgraph + feature vectors）存储在 SSD 中。传统方案通过 PCIe 将数据从 SSD→host memory→discrete accelerator → 57% 能耗在 PCIe 传输上。即使将计算卸载到 SSD 内部 FPGA（GList/SmartSage），page-granular 数据传输和 firmware 调度的 overhead 限制了后端吞吐。

### 关键洞察

1. **"Spatial accelerator 挂 SSD 内部总线，而非通过 PCIe"**：1D vector array (aggregation) + 2D systolic array (GEMM) 直接挂在 SSD 内部总线上 → 数据在存储内部完成计算 → 消除 PCIe 往返。类似 TileLoom "on-chip network 转发数据避开 von Neumann 瓶颈"→ BeaconGNN "SSD internal bus 转发数据避开 PCIe 瓶颈"。

2. **"Pipeline 数据准备与计算——不是简单的 offload 串行"**：Firmware GNN engine 将当前 mini-batch 的数据准备（flash backend 采样）与上一 batch 的计算（spatial accelerator）流水线化 → flash backend 和 accelerator 同时工作。关键：需要将上一 batch 的 feature vectors 和 subgraph 结构缓存在 SSD DRAM 中。

3. **"SRAM buffer 共享 + 可配置数据分区——灵活性 > 专用性"**：Accelerator 的 SRAM buffer 由 vector array 和 systolic array 共享，可灵活配置不同的 input/weight/output 数据分区 → 适配不同的 GNN 模型和 batch size，而不是为单一模型 hardcode 数据流。

- 来源：BeaconGNN(HPCA'24)

### 实践启发
- **"Bus-attached accelerator > PCIe-attached accelerator for data-in-storage workloads"**：当数据已经全部在存储内部时（全流程 offload），bus-attached accelerator 是自然选择——数据走内部总线而非 PCIe。**可推广模式**：任何 "compute follows data" 的架构中，加速器应该挂在数据所在的 bus 上而非独立的 PCIe endpoint。
- **"GNN 的 compute 和 data prep 天然可流水线"**：GNN 每层只依赖上一层的输出 → mini-batch N 的数据准备可以与 mini-batch N-1 的计算完全重叠。这利用的是 GNN 训练的数据流特性——不是 BeaconGNN 特有的优化。

---

## CXL 内存 NDP 通用加速单元 (CXL-M2NDP)

### 核心问题
CXL 内存扩展器需要通用 NDP 加速单元——不能是 application-specific（每个 workload 定制 HW 面积和 NRE 成本太高），也不能直接复用 CPU/GPU core（CPU OoO 逻辑太重、GPU SIMT-only 冗余地址计算达 ~30% 动态指令）。核心挑战：在 CXL 控制器的面积和功耗约束下（~20mm² at 7nm、远小于 GPU 的数百 mm²），设计既能覆盖 OLAP/KV/LLM/graph/DLRM 等多种 memory-bound workload、又具有高成本效率的执行单元。

### 关键洞察

1. **"RISC-V + Vector extension = 标量 + SIMD = 比 SIMT-only 更适合 memory-bound workload"**：Memory-bound 数据并行 kernel 需要标量操作（变址计算、边界检查、循环控制）和向量操作（实际数据处理）。GPU SIMT 用向量 lane 模拟标量 → 32 个线程同一条指令运行，即使只需要 1 个做标量操作 → 浪费 31 个 lane。RISC-V V extension 天然支持 SISD + SIMD → 消冗余。

2. **"μthread 用 memory-mapped 地址取代 thread ID → 消除 ~30% 冗余地址计算"**：GPU 线程通过 `index = blockIdx.x * blockDim.x + threadIdx.x` 关联数据 → 每个 warp 内所有线程重复相同计算（只是 threadIdx 不同）。μthread 直接以目标内存地址的 (base, offset) pair 创建 → 单个 scalar 操作完成 → 不需要并行冗余计算 → 这部分指令从 ~30% 降到接近于 0。

3. **"FGMT with register provisioning = 寄存器文件面积约束下的最优并发度"**：每个 kernel 在注册时声明需要的寄存器数（如 5 int + 3 vector）→ NDP 控制器按此分配物理寄存器 → 同一个寄存器文件可以容纳远多于分配全量 ISA 寄存器的硬件线程数 → 更高的线程并发度 → 更好的 DRAM 延迟隐藏。这是"利用 memory-bound workload 的 low register pressure"的架构优化。

4. **"Scratchpad + cache = 比纯 cache 更适合 NDP 的数据局部性管理"**：NDP kernel 通常一次处理一个数据块然后丢弃 → scratchpad 提供显式控制（类似 GPU shared memory），避免 cache 的 capacity/conflict miss 和 tag 开销。结合 L1/L2 cache 处理不规则的跨块访问和 stack data。

- 来源：CXL-M2NDP(MICRO'24)

### 实践启发
- **"RISC-V 是 NDP 的理想 ISA——不是因为性能，而是因为可定制性和开放性"**：RISC-V 允许仅实现 kernel 需要的子集（如不需要浮点的 kernel 可以省略 FPU → 节面积）。类似 M²NDP 去掉虚拟内存、TLB、特权模式 → 只保留 user-mode RV64IMAFDV 子集。可推广到任何"嵌入式计算单元需匹配特定 workload profile"的场景。
- **"CPU 的 SISD+SIMD 在 NDP 中比 GPU 的 SIMT 更合适"**：SIMT 假设所有线程同一指令 → memory-bound kernel 的变址计算打破这个假设 → SIMT 浪费 lane。RISC-V vector 提供数据级并行但不强制 lockstep → 更灵活。NDP 场景中 memory latency hiding 是主要目标，不是计算峰值 → RISC-V + FGMT 的弹性优于 GPU warp 的 rigidity。
- **"不是所有 workload 都适合 NDP——低算术强度是关键判据"**：M²NDP 明确定位 memory-bound workload。Compute-bound workload 应该留在 host CPU/GPU。类比分段设计原则——不是 everything in NDP，而是 right thing in NDP。
