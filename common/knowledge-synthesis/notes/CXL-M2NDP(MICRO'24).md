# CXL-M2NDP(MICRO'24)

- **来源**: 2024 57th IEEE/ACM International Symposium on Microarchitecture (MICRO)
- **作者**: Hyungkyu Ham*, Jeongmin Hong*, Geonwoo Park, Yunseon Shin, Okkyun Woo, Wonhyuk Yang, Jinhoon Bae (POSTECH), Eunhyeok Park (POSTECH), Hyojin Sung (SNU), Euicheol Lim (SK hynix), Gwangsun Kim† (POSTECH) (* equal contribution, † corresponding author)
- **URL**: https://arxiv.org/pdf/2404.19381v1
- **一句话 TL;DR**: 在 CXL 内存扩展器的控制器中设计通用近数据处理架构，通过 CXL.mem 原生的 memory-mapped 函数调用（M²func）替代高延迟 CXL.io 卸载，并通过 memory-mapped μthread（M²μthr）实现低成本高并发的 NDP 核执行，最高 128× 加速、87.9% 节能。
- **资料类型**: 论文-系统（MICRO'24）

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| CXL (Compute Express Link) | 开放标准的 CPU-设备互联协议，支持 CXL.mem（内存语义）、CXL.cache（缓存一致性）、CXL.io（设备管理）| 核心技术背景——CXL 内存扩展器是 NDP 的载体 |
| M²func (Memory-Mapped Function) | 在 CXL.mem 地址空间预留专门的"函数区域"，通过特定地址的 store/load 指令触发 NDP 管理操作 | 核心创新——用 CXL.mem 替代 CXL.io 做 NDP 卸载，消除 µs 级延迟 |
| M²μthr (Memory-Mapped μthreading) | 每个 μthread 与一个内存地址直接关联（而非像 GPU 用 threadblock/thread ID 间接计算地址），使用少量寄存器 | 核心创新——低成本通用 NDP 执行单元 |
| Packet Filter | 放在 CXL 内存输入口的硬件单元，检查 CXL.mem 包的地址是否命中 M²func 区域 | 关键使能——区分普通内存访问和 M²func 调用 |
| μthread | 仅使用 kernel 实际需要的寄存器子集（如 5 个整数 + 3 个向量寄存器）的轻量级线程 | M²μthr 的执行单元——类似 GPU 线程但更轻量、直接 memory-mapped |
| FGMT (Fine-Grained Multithreading) | 大量线程并发执行隐藏内存访问延迟 | M²μthr 核心执行模型 |
| HDM-DB | CXL Type-3 设备一致性模型——设备可通过 back-invalidation 维护主机缓存一致性 | NDP 使能的 CXL 内存必须使用此模型 |
| RISC-V ISA + Vector Extension | 支持标量 + SIMD 的指令集 | M²μthr 用此替代 GPU 的 SIMT-only，消除冗余地址计算 |

## 背景与动机

### CXL 内存扩展的矛盾

CXL 内存可以低成本解决大内存需求的容量问题（推荐系统、LLM、图分析的 TB 级数据），但存在两个矛盾：

1. **延迟瓶颈**: CXL.mem 虽比 PCIe 延迟低（~150ns load-to-use），但对延迟敏感应用（如 KV store）仍不可忽视
2. **带宽瓶颈**: CXL 链路带宽远低于内存内部带宽 → 带宽密集型应用在被动 CXL 内存上受限

**解决方案**: 在 CXL 内存控制器中做 NDP → 在数据所在地计算 → 避免 CXL 链路的延迟/带宽瓶颈。

### 现有 NDP 的三重不足

| # | 不足 | 根因 | 影响 |
|---|------|------|------|
| **1** | Application-specific HW | 每种 workload 专用硬件 → 无法通用 + 面积/NRE 成本高 | 不适合商品化 CXL 内存 |
| **2** | CPU/GPU core 成本效益差 | CPU 的 OoO 控制逻辑大、GPU 的 SIMT-only 冗余地址计算 | 面积和能效达不到 NDP 的成本约束 |
| **3** | CXL.io 卸载开销高 | 传统 MMIO/ring buffer 的 NDP 卸载涉及 CXL.io 协议栈 + 内核态切换 | 4.5-13.9µs 延迟 → 细粒度 NDP 不可行 |

## 问题定义

**要解决什么**: 在 CXL 内存扩展器中实现**低开销、通用、低成本**的近数据处理。具体包含两个子问题：(1) 如何低延迟地卸载 NDP kernel？(2) 如何在面积/功耗受限的 CXL 控制器中高效执行内存密集型 NDP 计算？

**现有工作为什么不够**:
- 专用硬件方案（如 GNN accelerator in CXL memory）: application-specific，不 general
- 用 CPU/GPU core 做 NDP: 面积和能效不匹配 NDP 的成本约束
- 基于 CXL.io 的卸载: µs 级延迟 → 细粒度 NDP 的 offload overhead 超过计算本身

## 方案介绍

### 方案概述

CXL-M²NDP = M²func (通信层) + M²μthr (执行层)，两者协同实现端到端低开销通用 NDP。

```
Host CPU                    CXL Memory with M²NDP
┌─────────────┐            ┌─────────────────────────────┐
│ User Process │            │ CXL Controller               │
│ ┌─────────┐  │  CXL.mem   │ ┌─────────────────────────┐ │
│ │store/load│──┼────────────▶││ Packet Filter           │ │
│ │to M²func │  │            │ │ (check addr vs M²func)  │ │
│ │region    │  │            │ └────────┬────────────────┘ │
│ └─────────┘  │            │          │                  │
│              │            │   Normal │ M²func call      │
│              │            │   mem    │ ▼                │
│              │            │   access │ NDP Controller   │
│              │            │          │ (manage kernels) │
│              │            │          │ ▼                │
│              │            │ ┌────────┴────────────────┐ │
│              │            │ │ NDP Units (RISC-V + V) │ │
│              │            │ │ ┌──┐ ┌──┐ ┌──┐ ┌──┐   │ │
│              │            │ │ │U0│ │U1│ │U2│ │U3│   │ │
│              │            │ │ └──┘ └──┘ └──┘ └──┘   │ │
│              │            │ │ FGMT μthreads          │ │
│              │            │ └────────────────────────┘ │
│              │            │              │              │
│              │            │  ┌───────────┴──────────┐  │
│              │            │  │ DRAM (data arrays)    │  │
│              │            │  └──────────────────────┘  │
│              │            └─────────────────────────────┘
└─────────────┘
```

### 关键模块

#### 1. M²func — 基于 CXL.mem 的低开销通信

**核心思想**: 在 CXL 内存物理地址空间中预留 M²func region → 通过特定地址 offset 的不同 CXL.mem store/load 实现不同的 NDP 管理函数 → packet filter 在 CXL 内存输入口拦截并路由。

**为什么不需要修改 CXL.mem 标准**: CXL.mem 本身就支持 memory read/write。M²func 只是**重解释**（repurpose）到达特定地址的读写请求——不需要新的 packet type，不需要修改 CPU 硬件。

**关键设计**:
- **Packet Filter**: 每进程 18B 元数据（64-bit base + 64-bit bound + 16-bit ASID）→ 18KB 支持 1024 进程
- **M²func 调用 = store instruction**: host 执行 `sd rs, offset(base)` 到 uncacheable M²func 区域 → bypass host cache → 直接送到 CXL device
- **参数传递**: vector register（如 RISC-V vse64.v）一次写入多个参数
- **返回值**: 后续 load 到同一地址读取
- **预定义函数** (按 offset stride=32B):

| Offset | Function | 参数 |
|--------|----------|------|
| 1<<5 | Kernel Registration | CodeLoc, ScratchpadMemSize, Register counts |
| 2<<5 | Kernel Launch | Synchronicity, KernelID, μthreadPoolRegion, args |
| 3<<5 | Kernel Unregistration | KernelID |
| 4<<5 | Status Poll | KernelInstanceID |
| 0 | Barrier | — |

**对比 CXL.io 卸载** (以 DLRM SLS B32 kernel 为例):

| 方案 | 延迟 | 并发 |
|------|------|------|
| CXL.io ring buffer (GPU-style) | ~13.9µs (2.5 CXL.io round-trips × 2) | ✓ 支持 |
| CXL.io direct MMIO | ~6.47µs | ✗ 单 kernel |
| **M²func** | **~6.4µs** (kernel 运行时间; offload ~35ns) | ✓ 支持 |

**效果**: 端到端 NDP 延迟 -31.2–53.5%（针对细粒度 kernel），Speedup 最高 3.89×（34.1% overall）vs CXL.io 卸载。

#### 2. M²μthr — 低成本高并发通用 NDP 执行

**核心思想**: 为 NDP 定制的执行模型——比 CPU 更轻量（无 OoO、无全寄存器集）、比 GPU 更高效（无冗余地址计算、无 threadblock 资源浪费）。

**μthread 的设计选择**:

| 维度 | CPU Thread | GPU Warp | M²μthr |
|------|-----------|----------|--------|
| 线程粒度 | 单个 (OS 管理) | 32-thread warp (TB batch) | **单个 μthread (HW 管理)** |
| 寄存器 | ISA 全量 (~32 int + 32 vector) | SIMT 固定 | **仅 kernel 需要的子集** |
| ISA | SISD+SIMD | SIMT-only | **SISD+SIMD (RISC-V + V extension)** |
| 地址计算 | 软件间接 | SIMT 冗余计算 (线程数 30%) | **Memory-mapped: 起始地址直接给** |
| 资源释放 | OS 回收 | Threadblock 全完成才释放 | **μthread 完成后立即释放** |
| 调度 | OS + 硬件 | 硬件 warp scheduler | **硬件 FGMT** |

**三大核心优势**:

1. **Memory-mapped 消除冗余地址计算**: GPU 的地址计算 (threadblockID × blockDim + threadID) 占动态指令的 ~30% → μthread 直接用内存地址创建 → 消除这些指令

2. **按需寄存器分配降低成本**: memory-bound workload 算术强度低 → 用寄存器少 → 只分配 kernel 实际需要的寄存器 → 寄存器文件面积可控 → 可容纳足够多 μthread 并发隐藏内存延迟

3. **细粒度资源管理**: GPU threadblock 完成后才释放 SM 资源 → inter-warp divergence 导致利用率波动（Fig. 5: 0.5-1.0）。μthread 完成后立即释放 → 一致高利用率

**硬件实现**:
- 基于 RISC-V ISA + vector extension (RV64IMAFDV)
- 简化版：无虚拟内存（基址+偏移）、无 TLB、无 OoO
- SIMD vector unit: 每 NDP unit 4 个 INT32 lanes + 1 个 FP32 lane
- 标量 ALU + 分支预测器
- 每个 NDP unit 带 on-chip scratchpad memory
- 4 个 NDP units 共享 L1 cache、DRAM 通道、CXL 端口

#### 3. 系统支持

- **Address Translation**: CXL device 用 PCIe ATS 请求翻译，带 device-side ATC cache → 避免每次都走 ATS 的 µs 级延迟
- **缓存一致性**: HDM-DB 模式 → CXL memory 通过 back-invalidation 维护与 host cache 的一致性 → host 用 clflush/clwb 保证写完的数据对 NDP 可见
- **多进程**: 每个进程分配独立 M²func region → packet filter 用 ASID 区分
- **安全性**: M²func region 通过虚拟内存页表保护 → 不同进程无法访问彼此的 NDP 功能

## 证据与评估

### 测试环境

- **模拟器**: 自研周期精确 CXL-NDP 模拟器（基于 gem5 + SST + DRAMSim3）
- **CPU Baseline**: 16-core OoO CPU at 2 GHz, DDR5 4800, 8 通道, 32GB
- **CXL Memory**: DDR5 4800, 2 通道, PCIe 5.0 ×8 lane (32 GT/s), 1 CXL port
- **M²NDP**: 4 个 NDP units at 1 GHz, 32KB L1 I$/D$ per unit, 256KB shared L2, 128KB scratchpad/unit
- **GPU-NDP**: scaled GPU SM (A100-derived): 1-16 SMs at 1 GHz, 32KB scratchpad/SM, 32 threads/warp
- **面积约束**: M²NDP around 1.5 mm² at 7nm（参照 SK hynix CXL 控制器 die shot 估计为 ~20 mm² 总控制器面积）

### Workloads

| Workload | 类别 | 特点 |
|----------|------|------|
| T6, S1_3 (OLAP) | In-memory DB | 内存密集扫描+聚合 |
| SPMV, PGRANK | 图分析 | 稀疏矩阵/图遍历，不规则访问 |
| SSSP | 图算法 | 单源最短路径，不规则 |
| DLRM (SLS)-B4/B256 | 推荐系统 | 稀疏 lookup + embedding |
| OPT-30B (Gen) | LLM 推理 | 大模型 token 生成，内存密集 |

### 主要实验结果

#### Perf/Energy 对比 (Fig in Evaluation section)

| Workload | M²NDP vs CPU baseline | M²NDP vs GPU-NDP (EqFLOPS) |
|----------|----------------------|---------------------------|
| T6 (OLAP) | ~10× speedup | ~1.5× |
| S1_3 (OLAP) | ~4× | ~1.3× |
| SPMV | ~6× | ~1.2× |
| PGRANK | ~5× | ~1.5× |
| SSSP | ~16× | ~2× |
| DLRM(SLS)-B4 | ~30× | ~2× |
| DLRM(SLS)-B256 | ~3× | ~1.1× |
| OPT-30B (Gen) | ~128× | ~1.3× |
| **Overall (geomean)** | **11.5×** | — |

**数据解读**:
- OPT-30B 加速最显著（128×）：LLM 推理的内存占用远大于缓存 → PCIe 传输 bottleneck → NDP 消除此瓶颈 → 巨大收益
- SPMV/PGRANK 加速适中：graph 访问不规则 → memory-level parallelism 受限 → NDP 收益有上限
- GPU-NDP(EqFLOPS) 被 M²NDP 全面超越：GPU 的 threadblock 粗粒度资源分配 + 冗余地址计算 → 成本效益不如 M²μthr

#### GPU-NDP scaling comparison

GPU-NDP 需要 **4-16×** FLOPS 才能匹配 M²NDP，但仍不如。这表明仅增加 compute 无法弥补 GPU SIMT 执行模型的结构性低效。

#### 能耗

- M²NDP: **-80.1% overall** vs CPU+DDR5 baseline
- M²NDP vs GPU-NDP(EqFLOPS): significantly lower → 更高效的执行模型 = 更少 wasted energy

## 整体评估

### 真正的新意

1. **M²func = 用已有协议的已有语义实现新功能**: 不修改 CXL.mem 标准、不修改 host CPU 硬件 → 只需一个 packet filter（18B per process）→ 就能在 CXL.mem 上做细粒度 NDP 卸载。这是"不做协议创新"的创新。
2. **M²μthr = 定制计算模型的成本效益**: 不比 CPU 也不比 GPU，而是从 NDP 的独特约束（面积受限 + memory-bound workload）出发设计执行模型——按需分配寄存器 + memory-mapped 消除地址计算 + 细粒度资源管理
3. **两个组件协同**: M²func 解决 offload 开销（→细粒度 NDP 可行），M²μthr 解决执行效率（→通用 NDP 成本可控）——端到端优化

### 优点

- 设计 philosophy 清晰: 每个设计决策都有量化的必要性论证
- 向量 ISA 的选择有充分理由: 比 SIMT-only 减少 ~30% 动态指令（消除地址计算）
- 实验多样性好: 5 类 workload（OLAP/KV/LLM/DLRM/graph）
- GPU-NDP 的 scaling comparison 有说服力: 证明了不是单纯"加更多 compute"能弥补架构差异

### 缺点

- 模拟器验证，无 RTL/FPGA/ASIC prototype
- 与 DRAM-PIM (如 UPMEM) 的对比不够深入
- RISC-V vector extension 的实际 RTL 面积未报告（仅给了大概估计 ~1.5mm² at 7nm）
- 未探索 CXL switch + multi-CXL-memory 的 P2P NDP 扩展
- 编程模型的易用性未评估（需要手写 RISC-V 汇编？还是 C with intrinsics？）

### 局限与假设

- 假设 memory-bound workload with low arithmetic intensity → compute-bound workload 应跑在 host/GPU 上
- 假设 HDM-DB 一致性模型 → 需要 host CPU 支持 clflush/clwb
- Packet filter 假设每进程 1 个 M²func region → 多线程共享需额外同步
- μthread 的内存地址直接映射不适合需要动态分配内存的 kernel

### 适用条件

- 系统配备 CXL 内存扩展器
- 内存密集型、低算术强度 workload（推荐系统、图分析、LLM token 生成、KV store）
- Host CPU 支持 CXL.mem 和 cache flush 指令
- 数据在 CXL 内存上 → 避免先从 SSD/host memory 搬数据到 CXL memory

### 可复用启发

1. **"不修改协议，重解释协议"**: M²func 在标准 CXL.mem 上构建 NDP 命令通道 → 无需改标准或 CPU 硬件。类似 Rakaia "在最早介入点重构语义"——利用现有机制的新解释而非发明新机制
2. **"Memory-mapped 是比 thread ID 更自然的并行抽象"**: 当每个 thread 处理特定数据块时 → 直接用内存地址标识线程更直观 → 消除 30% 冗余地址计算
3. **"按需分配 > 固定全量分配"**: 内存密集型应用的线程用寄存器少 → 只分配需要的 → 同样的寄存器文件面积可容纳更多硬件线程 → 更好的内存延迟隐藏
4. **"CXL.mem 可以做控制通道": 150ns 延迟让 store/load 成为可行的细粒度卸载原语 → 类比 RDMA immediate data（UEP/UCCL-Tran 也用此技巧）
5. **"Packet filter 是最轻量的 CXL controller 定制": 18KB 表 → 支持 1024 进程的 M²func → 在商用 CXL controller 上实现成本极低

### Discussion 中值得关注的扩展方向

- Multi-CXL-memory 的 P2P NDP（CXL 3.0 支持 device-to-device access）
- DRAM-PIM + NDP 的 hybrid：PIM 处理 per-bank local reduction → NDP 做 cross-bank aggregation
- M²func 的思想可以扩展到其他 CXL 设备（FPGA、SmartNIC）→ 通用的低延迟设备管理
