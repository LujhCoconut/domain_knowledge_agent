# DirectKV(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-luo.pdf
- **年份**: 2026 (July 13–15, Seattle, WA)
- **全称**: No Buffer, No Bottleneck: Efficient Zero-Copy KV Cache Offloading for Long-Context LLMs
- **系统名**: DirectKV
- **作者**: Shutian Luo, Haiying Shen (University of Virginia)
- **开源**: https://github.com/shutianluo/DirectKV
- **类型**: 论文-系统 (LLM serving + GPU kernel-memory co-design + zero-copy)
- **一句话 TL;DR**: 首个针对 GH200/GB200 NVLink-C2C 平台的 zero-copy KV cache offloading 系统，通过 SMEM tiling 将带宽瓶颈从 CPU-GPU 互联转移到 HBM + warp 级流水线 + 融合 kernel 消除冗余 KV 传输，减少 GPU 内存 **43%**、传输量 **50%**、性能提升 **1.2×**。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **Zero-Copy** | GPU kernel 直接通过 device-visible pointer 访问 CPU pinned memory，无需 CPU↔GPU staging buffer | 核心设计原则：消除 GPU staging buffer + 减半传输量 |
| **NVLink-C2C** | GH200/GB200 的 CPU-GPU 互联，900 GB/s 双向带宽（7× PCIe Gen5） | 使 zero-copy 从不可行变为可行的硬件前提 |
| **CPU-Memory-Aware Tiling** | 矩阵乘法 tile 策略反转：外层迭代 GPU 侧的 A/C，内层复用 CPU 侧的 B（stationary B） | 将带宽瓶颈从 C2C 转移到 HBM（4 TB/s），CPU-GPU 传输从 O(n³) 降为 O(n²) |
| **SMEM** (Shared Memory) | 每个 SM 内的快速 on-chip SRAM（256 KB on Hopper） | 充当 CPU 端 KV 数据的 on-chip buffer，实现 tile 复用 |
| **Warp-Level Pipelining** | 不同 warp 组独立执行 producer（fetch）/consumer（compute）/storer（write-back）| 重叠通信与计算，隐藏 CPU memory access 延迟 |
| **Fused Kernel** | KV projection + attention score computation 合并为单个 CUDA launch | 消除 K/V round-trip（写到 CPU memory 再读回）→ 减少 50% 传输 |
| **Kernel Generator & Adaptor** | 离线模板预编译多种 kernel 变体 + 运行时按 precision/head dim/phase 选择 | 工程手段：避免运行时 JIT，保证硬件最优化 |
| **GH200 Superchip** | NVIDIA Grace-Hopper: 72-core ARM CPU + H100 GPU + 96GB HBM3 + LPDDR5X + NVLink-C2C | DirectKV 的目标平台 |

## 背景与动机

### 问题
- KV cache 线性增长 → GPU HBM 容量不足（详见 Strata/ECHO 类似动机）
- 现有 swap-based offloading (Pie, FlexGen) 需要 GPU staging buffer → 浪费 HBM + PCIe 往返传输翻倍
- Zero-copy（GPU kernel 直接访问 CPU memory）理想上消除了 buffer，但 **naïve 实现性能极差**

**Naïve zero-copy 的问题** (Figure 2):
- PCIe: 比 swap 慢 **20×**（1122ms vs 56ms）
- NVLink-C2C: 仍比 swap 慢 **2×**（106ms vs 52ms）
- 根因：GEMM kernel 为 HBM 优化设计，反复从 CPU memory 取 operand → 完全暴露 C2C-HBM 带宽差距 + GPU L2 hit rate 从 77% 暴跌到 32.3%

### 核心洞察
**SMEM tiling 可以重构数据访问模式**——通过反转矩阵乘法的迭代策略（外层迭代 GPU-side 数据，内层复用 CPU-side 数据），将带宽瓶颈从 C2C（450GB/s per direction）转移到 HBM（4 TB/s）。C2C 流量从 O(n³) 降为 O(n²)。

### 我的分析
DirectKV 是三篇 OSDI '26 KV cache 论文中最"底层"的一篇——Strata 在应用层做 I/O 和调度优化，ECHO 在框架层做 graph-friendly metadata 和 prefetching，DirectKV 在 CUDA kernel 内部做 tiling 和流水线改造。它的核心贡献是证明了：在 NVLink-C2C 时代，zero-copy attention 可以接近 HBM 性能。这是对 "GPU 内存墙" 问题的一个硬件协同解答。

## 方案介绍

### 整体架构 (Figure 8)

```
KV Cache Manager (CPU pinned memory, zero-copy)
        ↓
Kernel Adaptor (runtime kernel selection)
        ↓
Attention Fusion Engine (fused P+A kernel)
        ├── Prefill: Q-outer / KV-inner tiling
        └── Decode:  KV-outer / Q-inner tiling
        ↓
Kernel Generator (offline template instantiations)
```

### 关键创新 1: CPU-Memory-Aware Tiling (§5.1, Algorithm 1)

**NativeTiling**（传统 GEMM）:
```
for k:  Load A_ik (HBM→SMEM), Load B_kj (HBM→SMEM)
       C_ij += A_ik × B_kj
Store C_ij (SMEM→HBM)
```
→ B 被反复从 CPU memory 加载（O(n³) traffic）

**CpuAwareTiling**（DirectKV）:
```
Load B_kj (CPU→SMEM, once)
for i:  Load A_ik (HBM→SMEM), Load C_ij (HBM→SMEM)
        C_ij += A_ik × B_kj
Store C_ij (SMEM→HBM)
```
→ B 在 SMEM 中 stationary，只加载一次；C 多了 HBM 往返但 HBM 带宽充足

**效果** (Figure 4): CPU-GPU 传输从 33.5 GB → 0.3 GB，延迟从 106ms → 54ms (49% 提升)，L2 hit rate 从 32.3% → 75.1%

### 关键创新 2: Warp-Level Pipelining (§5.2)

利用 Hopper 的异步 warp 组：
- **Producer warps**: TMA 预取下一个 tile（异步硬件拷贝引擎）
- **Consumer warps**: 当前 tile 的 GEMM 计算
- **Storer warps**: 将 K/V 写回 CPU memory（仅 prefill 需要）

**效果** (Figure 6): HBM 吞吐从 0.3 → 1.3 TB/s (4.3×)，延迟 -11%

### 关键创新 3: Fused Projection-Attention Kernel (§5.3-5.4)

**Prefill 融合** (Algorithm 2):
- 同一 kernel 内完成 X→K/V projection + QK⊤ attention
- K/V 生成后留在 SMEM 直接被 attention 消费
- 消除了两次 round-trip（projection writeback + attention re-fetch）
- **Iteration strategy**: 外层 KV（CPU memory），内层 Q（HBM）→ 对应 CpuAwareTiling

**Decode 融合** (Algorithm 3):
- 单 token decode：外层 KV（CPU memory），内层 Q（单 token in register）
- ot 保留在寄存器内跨 tile 累加（勿需反复 HBM R/W）
- 只需 2 warp groups（producer + consumer，无需 storer）
- 新生成的单 token KV 直接 append 到 CPU memory

**效果** (Figure 7): HBM 吞吐 1.6→1.9 TB/s（+15.8%），延迟 85→57ms（49% 加速）

### SMEM 分区策略 (§4.1)
- SMEM 逻辑分区: Projection buffers + Attention buffers
- K 复用 Wk buffer, V 复用 Wv buffer
- 默认 2-stage pipeline → 双倍 buffer，约束: `α·P ≥ 3·m·size(T)·Dim·N`
- Default α=0.8 (80% for SMEM, 20% L1)

### Kernel Generator & Adaptor (§4)
- 离线 C++ 模板预编译 `<T, Dim, N>` 变体
- 运行时根据 precision (FP16/BF16)、head dim、phase 选择
- 5300 行 CUDA/C++ (on top of FlashAttention-3 + CUTLASS) + Python bindings

## 证据与评估

### 测试环境
- **硬件**: GH200 (H100 GPU + Grace CPU + 96GB HBM3 + LPDDR5X + NVLink-C2C 900GB/s), H100 PCIe Gen5 对比
- **模型**: Llama-3.1-8B, OPT-13B, OPT-30B
- **数据集**: ShareGPT, Alpaca (Poisson 到达，1-32K context)
- **Baseline**: SGLang (纯 HBM), Pie (swap-C2C), Neo (CPU offload), FlexGen (multi-tier compressed)

### 关键结果

| 实验 | 结果 | 要点 |
|------|------|------|
| Latency (request rate, Fig 10) | DirectKV 在所有 offload 系统中最低 | 接近 SGLang（当 SGLang 不 OOM 时）|
| OPT-30B at 30 req/s | SGLang OOM; DirectKV **0.75s** vs Neo/Pie/FlexGen 1.55-3.95s | 仅 DirectKV 能撑住大模型高负载 |
| Context length scaling (Fig 11a) | 1.2× avg speedup, 1.3× at 16K, 1.7× vs FlexGen | 越长优势越大（减少了 CPU-GPU 传输 O(n²) vs O(n³) 差异） |
| GPU memory (Fig 11b) | DirectKV **47GB**, others 74-92GB | 节省 **43%** (平均 35GB) |
| CPU-memory-aware tiling (Fig 12) | **50%** CPU-GPU transfer reduction, **70%** latency reduction vs naïve zero-copy | 核心创新验证 |
| Fused kernel (Fig 13) | **3.5×** HBM throughput, **2.5-3×** lower latency vs separate kernel | |
| PCIe vs NVLink-C2C (Fig 14) | C2C 使 DirectKV latency 降 **4.2×** | 硬件条件验证 |
| Warp pipelining (Fig 6) | 4.3× HBM throughput, 11% latency reduction | |

### 为什么 DirectKV 能在 GH200 上胜出

1. **消除往返传输**: swap-based (Pie) 每次需要 GPU staging→compute→writeback，DirectKV 的 KV 数据在 CPU memory 被直接消费
2. **Tiling 策略消除了带宽瓶颈**: NVLink-C2C 虽然 900 GB/s 但仍远慢于 HBM 4 TB/s，CPU-aware tiling 将传输从 O(n³) 降为 O(n²)
3. **融合 kernel 消除冗余**: projection→CPU write→attention CPU re-read 被合并为 projection-SMEM→attention
4. **SGLang 的极限**: 在 32K context 下 GPU 内存耗尽 (OOM)，DirectKV 用 CPU memory 绕过这个硬限制

## 整体评估

### 真正的新意
1. **首次证明 zero-copy KV offloading 可以在 NVLink-C2C 上 practical**: naïve zero-copy 慢 2-20×，通过 kernel-memory co-design 反超 swap
2. **CPU-memory-aware tiling 的策略反转**: outer loop over GPU-side data → 带宽瓶颈从 C2C 转移到 HBM（带宽充足）
3. **Kernel fusion of projection + attention**: 将通常分离的两个 kernel 合并，消除 KV round-trip。这在 dense attention 中是首次

### 优点
- **极简实现**: 5300 行 CUDA（相比完整 serving framework 数十万行），专注解决一个问题
- **兼容现有 stack**: 与 vLLM/SGLang 的调度、prefix cache、eviction 策略完全解耦
- **跨精度/跨模型**: Kernel Generator + Adaptor 支持 FP16/BF16，Llama 和 OPT 系列
- **清晰的硬件适用性**: 明确指出在 PCIe 上主要是 capacity 扩展而非 performance 提升

### 局限
1. **平台绑定**: 核心 benefit 在 NVLink-C2C (GH200/GB200) 上实现，PCIe 上只能做 capacity extension
2. **CPU memory 访问是 coarse-grained 的**: 依赖 ~100KB tile × 100+ SM 的并发来饱和 C2C 带宽。如果 batch size 小 → tile 数少 → 带宽利用不足
3. **不处理 multi-GPU 的 KV 分布**: 对 tensor/pipeline parallelism 或 disaggregated serving 中的跨节点 KV 通信没有优化
4. **解码延迟在极低 batch size 下可能不如 HBM-only**: 单 query 解码时 KV 仍存在 CPU memory → C2C 延迟无法完全隐藏
5. **未与 prefix caching / eviction 等策略集成**: 论文承认 KV Cache Manager 目前是 thin wrapper，后续需要与成熟 serving framework 的全套 KV 管理功能整合

### 与 Strata/ECHO 的对比

| 维度 | Strata(OSDI'26) | ECHO(OSDI'26) | DirectKV(OSDI'26) |
|------|----------------|---------------|-------------------|
| **层次** | Application (I/O + scheduling) | Framework (metadata + prefetch) | Kernel (tiling + pipelining) |
| **目标模型** | Dense (Llama/Qwen) | Sparse (DeepSeek DSA) | Dense (Llama/OPT) |
| **Offloading 模式** | Static request-level | Dynamic token-level | Zero-copy (no staging buffer) |
| **硬件** | H200 PCIe 5.0, GH200 | H20 PCIe Gen5 | GH200 NVLink-C2C |
| **核心技术** | GPU kernel I/O + layout decoupling | Graph-friendly metadata + lossless prefetch | CPU-aware tiling + fused P+A kernel |
| **瓶颈** | PCIe BW 碎片化 | GPU HBM 容量 | C2C→HBM 带宽差距 |
| **GPU 内存节省** | ~0 (布局优化) | ~60% (host pool) | **43%** (no staging buffer) |
| **性能提升** | 3.2-5× vs vLLM-LMCache | 2.1-4.1× vs SGLang | 1.2× vs Pie/Neo/FlexGen |
| **代码量** | 集成到 SGLang | 基于 SGLang + DeepGEMM | 5300 行 CUDA on FlashAttn-3 |

**三篇互补关系**: Strata 解决"搬运效率"(I/O碎片化)，ECHO 解决"搬运什么"(token选择)，DirectKV 解决"如何搬运"(kernel-memory co-design)。从应用层到底层 kernel，构成完整的 KV cache offloading 技术栈。

### 可复用启发

1. **SMEM 作为"on-chip level in hierarchy"**: 在 CPU-GPU 之间引入 SMEM 作为中间的"快速缓冲层"，类似 L2 cache 的设计哲学。这个思想可推广到其他异构数据流场景

2. **Tiling strategy 反转**: "让慢速介质的数据 stationary"（CPU memory B），让快速介质的数据流动（HBM A/C）→ 这个 insight 适用于任何 asymmetric bandwidth 的场景

3. **Kernel fusion 节省 round-trip**: Projection→Attention 融合消除了 KV writeback→re-fetch。任何有 intermediate tensor 跨 kernel 边界的 GPU pipeline（如 MLP→activation→next MLP）都可考虑类似融合

4. **"分离关注点"的 clean interface**: DirectKV 将 kernel execution 和 KV management/scheduling 完全解耦，作为现有 serving stack 的 drop-in。这是系统设计的好模式

5. **硬件趋势驱动软件设计**: NVLink-C2C 使 zero-copy 从"不可行"变为"最优"。随着 Vera CPU(1.8 TB/s C2C) 等新硬件出现，zero-copy 的方向只会更重要
