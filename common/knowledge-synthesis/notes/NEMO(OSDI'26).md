# NEMO(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-li-shihang.pdf
- **全称**: Finding NEMO: Nimble and Expressive Memory Observability
- **系统名**: NEMO (Nimble and Expressive Memory Observability)
- **作者**: Shihang Li*, Matthew Giordano* (UW), Tushar Garg (Meta), Rohan Kadekodi (UW), Daniel S. Berger (UW & Microsoft Azure), Baris Kasikci, Thomas Anderson, Simon Peter (UW)
- **开源**: https://github.com/vic-lsh/nemo
- **类型**: 论文-系统 (硬件/软件协同设计 + 内存可观测性)
- **一句话 TL;DR**: 在**内存控制器 (MC) 中嵌入可编程 telemetry pipeline** — OS 通过 mask-shift-add 匹配 + 关联/交换更新操作 + 中断通知来定义任意粒度的观测规则。在 FPGA CXL 内存扩展器上原型验证：hot-set 变化检测加速 **5×**，THP 拆分加速 **10.4×**，noisy neighbor 检测 CPU 开销降低 **350×**，KV store/DB 吞吐提升 **1.7×**。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **NEMO pipeline** | MC 内的 match-update-notify 固定功能流水线 | 核心硬件抽象：过滤→翻译→更新→通知 |
| **Translation table** | MC SRAM 中的 key→state index 映射表（8192 entries, ~14 KiB） | 让 OS 动态指定哪些内存区域被追踪 |
| **Mask-shift-add** | 从物理地址提取 primary region key + sub-region offset 的硬件操作 | 无需完整 TLB/CAM — 用简单算术实现灵活聚合 |
| **Telemetry state** | Per-channel SRAM 中的计数器数组（8192 × 64-bit, 128 KiB/channel） | 维护聚合值（计数、带宽、skew 等） |
| **Match-update-notify** | 借鉴可重构匹配表架构（RMT，常用于可编程交换机） | Pipeline 结构：匹配请求 → 更新状态 → 可选中断 |
| **Associative & commutative updates** | 仅支持满足结合律和交换律的操作（ADD, XOR, MIN, MAX...） | 使 per-MC 状态可任意顺序合并为全局视图 |
| **Read-side effect** | 读 telemetry 后自动执行的操作（如 reset-to-zero） | 使每次 poll 获取 interval 增量而非累积值 |
| **Coverage / Timeliness / Granularity / Flexibility / Overhead** | 内存可观测性的五维评估框架 | NEMO 是第一个在所有维度上同时达到高水平的方案 |

## 背景与动机

### 问题定义
现代数据中心服务器内存层级越来越复杂（多 socket DDR + CXL + accelerator UVM），但 **OS 可用的内存观测手段极度匮乏**——现有方案在五维之间只能取其一：

| 方案 | Coverage | Timeliness | Granularity | Flexibility | Overhead |
|------|----------|------------|-------------|-------------|----------|
| 软件 page fault | 高（理论上全部） | 高 | 页级 | 高 | **极高** |
| PTE access bit scan | 低（1 bit/interval） | 低（生产 30s） | 页级 | 中 | 高 |
| PEBS 采样 | 低（0.02% 默认） | 中（1s poll） | cache line | 中 | 采样率↑→开销↑ |
| HW 固定功能计数器 | 高 | 高 | **粗（socket/channel级）** | **无（设计时固化）** | 低 |
| CXL hotness tracking (M5) | 高 | 高 | 页/word | **无（固定 top-K）** | 低 |

**NEMO 的设计目标**: 首次在所有五维度上同时达到高水平。

### 核心洞察
**MC 是观测的理想位置** — 所有内存请求必经 MC，MC 已有 QoS 和监控功能（如 Intel MBM）。只需在 MC 数据路径旁加一个可控 pipeline + 小 SRAM，就能在不增加延迟的前提下实现灵活的全覆盖观测。

### 我的分析
NEMO 和 M5(ASPLOS'25) + MAC(OSDI'26) 共同指向一个趋势：**将智能推入内存控制器**。M5 做 hotness tracking，MAC 做 metadata reclamation acceleration，NEMO 做 general-purpose observability。三者在"MC 内计算"的维度上互补，但 NEMO 的设计最具通用性——它不预设任何特定 telemetry 语义，而是提供可编程的 match-update-notify 原语。

## 方案介绍

### 架构 (Figures 1-2)

```
OS Subsystems (HeMem, MEMTIS, Linux...)
        ↓ NEMO driver (installs telemetry rules, reads state)
Memory Controller (per MC)
  ┌─────────────────────────────────────────┐
  │ Memory requests → headers tapped off     │
  │   → Pipeline 0 (e.g., page hotness)      │
  │   → Pipeline 1 (e.g., page skewness)    │
  │   → Pipeline N                           │
  │ Each Pipeline: Match → Update → Notify  │
  │   ├ Translation Table (SRAM)             │
  │   └ Telemetry States (SRAM, per-channel) │
  └─────────────────────────────────────────┘
        ↓ (original request to DRAM/CXL, unmodified)
```

### 关键创新 1: Match-Update-Notify Pipeline (§3.1)

**Match stage** (mask-shift-add + translation table):
1. 用 OS 指定的 bitmask 和 shift 提取 primary region key（如 2 MiB page number）
2. Key 索引 translation table → 返回 base state index
3. 可选: 第二个 mask+shift 提取 sub-region offset（如 4 KiB basepage within 2 MiB hugepage）
4. `final_index = base_index + offset`
5. Key miss → drop request（不追踪）

**Update stage** (read-modify-write, 1 cycle):
- 支持的操作: ADD, SUB, MIN, MAX, AND, OR, XOR, shift, 等（Table 1）
- **全结合律+交换律**: 保证 per-MC 状态之后可以任意顺序合并
- 使用 value forwarding 消除 RAW hazard（无需 stall）
- 如需 >1 cycle 操作 → 加倍时钟频率或虚拟通道

**Notify stage** (optional predicate):
- 比较更新后的值与阈值（如 counter > N） → 触发中断
- Per-controller 中断因为 fine-grained interleaving 可视为 hint

**Telemetry state access**: 不是 MMIO，而是**映射为普通内存区域** — 读 telemetry 就像读 DRAM，512 bits/cycle/channel，支持 prefetch

**Read-side effect**: 读后自动 reset-to-zero（或任何 update op） — 每次 poll 获得 interval 增量

### 关键创新 2: OS 可编程的 Telemetry 规则 (§3.2-3.3)

**安装 telemetry** 仅需指定 5 项:
1. Filter (R/W/All + address range)
2. Translation rule (primary mask+shift, optional sub mask+shift)
3. Update operation (+ operand)
4. Notify predicate (optional)
5. Read side-effect (optional reset)

**三个代表性 Telemetry 配置**:

| Use Case | Primary | Sub | Update | 效果 |
|----------|---------|-----|--------|------|
| Page hotness (§5.1) | 2 MiB page | none | ADD 1 | 每 hugepage 一个 counter |
| Page skewness (§5.2) | 2 MiB page | 4 KiB basepage | ADD 1 | 512 counters per hugepage |
| Tenant bandwidth (§5.3) | multi-GiB region | none | ADD `request_size` | Per-tenant bandwidth |

**Translation table 动态更新**: OS 通过 `nemo_set_translation()` 可随时增删 translation entries → 支持 time-multiplex（SRAM slot 不够时可以轮换追踪不同区域）

**表达能力边界**: NEMO 不支持单 request 多操作或多地址更新（如 variance 需要 sum + sum of squares），但不同 pipeline 独立操作可后合并

### 硬件实现 (§4)

- **平台**: Altera Agilex 7 FPGA + CXL 2.0 Type-3 IP + 16 GiB DDR4
- **资源**: 4.8% logic + 4.4% M20K SRAM（vs 全 bitstream）
- **Pipeline**: 8192-entry translation table (~14 KiB) + per-channel 8192 × 64-bit state array (128 KiB × 2 channels) ≈ **150 KiB/pipeline**
- **最大部署**: MEMTIS-NEMO 用 8 pipelines ≈ 1.2 MiB SRAM
- **频率**: 400 MHz, 每 channel 每 cycle 处理 1 request
- **Host**: Xeon Gold 6430 (32 cores), CXL DRAM @ 380ns (3.3× host)

## 证据与评估

### 三个 Use Case

**Use Case 1: Hot Set Phase Change Recovery (§5.1) — HeMem integration**

| 配置 | FlexKVS, 1:2 fast:slow, hot set shift at 2 min | 
|------|------|
| HeMem-NEMO | **67s 收敛**, 0.89% CPU overhead |
| HeMem-PEBS (0.02%) | 324s 收敛 |
| PEBS 极限 | 即使提升采样率也无法弥合差距（>1% 采样率损害应用）|
| FASTER KV 大 value | HeMem-NEMO 吞吐 **+69%** vs PEBS；PEBS 无法捕捉 prefetch 流量 → 漏掉热点信号 |

**Use Case 2: THP Split Candidate Selection (§5.2) — MEMTIS integration**

| MEMTIS-NEMO vs MEMTIS-PEBS | Silo (YCSB-C, 90M keys) |
|------|------|
| Split candidates found | **2×** more |
| Detection time | **10.4×** faster |
| Throughput | **+13%** (vs MEMTIS-PEBS) |

**Use Case 3: Noisy Neighbor Detection (§5.3) — Linux bandwidth monitoring**

| Linux per-core PMU counters → NEMO per-tenant bandwidth |
|------|
| CPU overhead | **350× lower** |
| Accuracy | **<0.1% error** vs ground truth |

### FPGA 资源开销 (Table 2)

| | Full Bitstream | NEMO only |
|---|---|---|
| Logic | 17% | **4.8%** |
| Registers | 9.3% | **1.7%** |
| M20K SRAM | 14% | **4.4%** |

## 整体评估

### 真正的新意
1. **将 RMT (Reconfigurable Match Table) 范式从网络交换机移植到内存控制器**: 这是跨领域的架构移植 — match-update-notify 在可编程交换机中广泛应用，但在 MC 中是首次
2. **Mask-shift-add + 小 translation table 替代 TLB/CAM**: 用极简硬件实现灵活的地址→状态聚合，关键洞察是 telemetry 不需要任意 mapping（仅需 aligned power-of-2 regions）→ 允许 simple arithmetic
3. **Associative & commutative 约束作为分布式的 enabler**: 不仅是硬件简化的需要，更使 per-MC 状态可以任意顺序合并成全局视图 — 这在多 MC interleaving 系统中至关重要
4. **五维评估框架本身**: Coverage/Timeliness/Granularity/Flexibility/Overhead — 系统性地定义了内存 telemetry 的设计空间

### 优点
- **通用性**: 三个截然不同的 use case (hot set detection, THP splitting, bandwidth monitoring) 全部用同一套 pipeline 表达
- **简洁**: 每条 telemetry ~10 行配置代码 (Listing 1/2)，无需 per-use-case 硬件修改
- **开销极低**: 4.8% FPGA logic + 4.4% SRAM，OS 侧 CPU 开销大幅降低
- **真实硬件原型**: FPGA + CXL 2.0 原型，非纯仿真
- **与 M5/MAC 互补**: 三者都在 MC/CXL controller 内增加智能，NEMO 提供的是通用可编程框架

### 局限
1. **单 request 单操作**: 不支持 variance、exact top-K 等需要多状态更新的 telemetry（§6.3 讨论了扩展）
2. **Translation table 有限**: 8192 entries/pipeline — 对于全覆盖 per-page tracking 仍然不够（需要 time-multiplex）
3. **仅 CXL slow tier**: 原型只观测 CXL 内存访问，快 tier (DDR) 仍需 PEBS
4. **通知延迟**: Notify 阶段的中断尚未硬件实现（用 1ms 轮询模拟）
5. **仅匹配物理地址**: 无法直接区分 VM/tenant（需要 OS 预先将 tenant→physical range 映射到 translation table）
6. **IMC 集成未实现**: 原型的 FPGA 是 CXL Type-3 设备，不是 host IMC — 如集成到 host IMC 可同时覆盖 fast/slow tier

### 与本知识库 CXL 论文的关系

NEMO 是 CXL 生态中"可观测性"这一维度的填补：

| 论文 | CXL 层 | 做什么 |
|------|--------|--------|
| M5(ASPLOS'25) | Controller 硬件 | Hot-page/word tracking (fixed function) |
| MAC(OSDI'26) | Controller NMP | Metadata reclamation acceleration (fixed function) |
| **NEMO(OSDI'26)** | **Controller pipeline** | **General-purpose programmable telemetry** |
| PACT/CAMP/TMO/RamRyder | Host software | 利用 telemetry 做 policy 决策 |

NEMO 将 M5 的"固定功能 hotness tracking"泛化为"可编程 telemetry engine" — 这是从 ASIC 到 FPGA 的思维跃迁。

### 可复用启发

1. **"可编程观测" > "固定功能观测"**: 数据中心的内存管理 policy 持续演进（新 tier、新 SLO、新 workload pattern）→ 硬件 telemetry 必须是可编程的，否则很快过时
2. **RMT 架构的跨领域移植**: match-update-notify 从网络数据平面到内存数据平面的移植，证明了这个范式的通用性
3. **Mask-shift-add 替代 CAM/TLB**: 对于只需 aligned power-of-2 region mapping 的场景（telemetry、QoS、带宽限制），简单的位操作比完整的地址翻译结构更高效
4. **Associative+commutative 约束作为分布式系统设计原则**: 允许任意顺序合并 per-unit state → 消去全局同步。适用于任何多节点聚合的监控场景
5. **"读时重置"作为 interval estimation**: 比 timestamp + subtraction 更简单，消除了时间同步需求，适合固定轮询周期的监控
6. **五维评估框架**: Coverage/Timeliness/Granularity/Flexibility/Overhead 可用于评估任何观测系统的设计 tradeoff — 不仅是内存，也适用于网络、存储、CPU telemetry
