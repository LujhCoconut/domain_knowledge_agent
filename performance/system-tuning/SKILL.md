# System-Level Performance Tuning

系统层性能调优知识与经验，涵盖 CPU、内存子系统、内核参数、NUMA 等。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| Tiered Memory 管理 | CXL, NUMA, page migration, hotness vs criticality | PACT(ASPLOS'26) |
| 透明内存 Offloading | PSI, Senpai, swap, zswap, reclaim, memory tax | TMO(ASPLOS'22) |
| CXL 硬件辅助追踪 | Hot-Page/Word Tracker, CXL controller, near-memory, sparse hot pages | M5(ASPLOS'25) |
| CXL 性能预测与建模 | slowdown decomposition, weighted interleaving, closed-form model, PMU | CAMP(ASPLOS'26) |
| 内存延迟归因 | CHA/TOR, MLP, PMU counters, PEBS, stall attribution | PACT(ASPLOS'26) |
| 资源压力感知 | PSI some/full, cgroup 控制, feedback loop | TMO(ASPLOS'22) |

---

## Tiered Memory 管理

### 核心问题
在 DRAM + CXL/NUMA 的 tiered memory 系统中，如何决定哪些页面放在快 tier。

### 关键洞察

1. **Hotness (access frequency) 不等于 Performance Impact**：
   - 相同访问频率的页面，stall 代价可差 65×（取决于 MLP）
   - 顺序遍历（高 MLP）可隐藏延迟，指针追踪（低 MLP）完全暴露延迟
   - 启发来自 PACT §3 (violin plots), PACT(ASPLOS'26)

2. **PAC (Per-page Access Criticality) 建模**：
   - 核心公式: `LLC-stalls = k × (LLC-misses / MLP)`
   - `k` 是 per-tier 系数（捕获延迟 + 架构开销）
   - 在 96 workloads × 3 延迟配置下，Pearson > 0.98
   - 来源: PACT §4.2, PACT(ASPLOS'26)

3. **Per-tier MLP 观测**：
   - Intel: 用 CHA 的 TOR_OCCUPANCY / TOR_OCCUPANCY_COUNTER0 计算 per-tier MLP
   - AMD (无 TOR): 用 Little's Law 近似 `MLP ≈ Latency × Bandwidth`
   - 来源: PACT §4.2.2, PACT(ASPLOS'26)

4. **MLP Phase Stability**：
   - MLP 在 tens-of-ms 尺度上保持稳定
   - 这允许在短窗口（20ms）内按访问频率比例属性 stall 到各页面
   - 来源: PACT §4.3, PACT(ASPLOS'26)

### 实践启发

- **做内存性能分析时，同时看 LLC-misses 和 MLP**，不要只看 miss rate/count
- **CHA/TOR 计数器是 per-tier 流量分析的最佳观测点**，比系统级 offcore 指标信息量大
- **20ms 是一个实用的采样窗口**：perf 不支持 sub-10ms 精确计数器，20ms 足以捕捉 MLP 动态
- **默认 PEBS 采样率 1:400** 在准确性和开销之间平衡良好
- **Eager demotion**: 早期主动降级建立 headroom，成熟后降低频率。类似 TCP 拥塞控制的思路

### 相关 Workload 特征
- **MLP 方差大的 workload**（同时有 streaming + pointer-chasing）从 criticality-driven 管理获益最大
- **纯 streaming workload**: PAC ≈ frequency，hotness-based 方法即可
- **图计算 + LLM 推理**: 典型的有 MLP 方差场景，是最佳应用领域

---

## 待补充

- NUMA 自动平衡调优
- Hugepage / THP 在 tiered memory 中的交互
- 其他平台（ARM, RISC-V）的 PMU 等价设施

---

## 透明内存 Offloading (Swap/Zswap)

### 核心问题
在数据中心环境中，如何在不修改应用的前提下，自动将冷内存透明地 offload 到更便宜的存储介质（压缩内存、SSD、NVM），同时最小化对应用性能的影响。

### 关键洞察

1. **PSI 直接测量生产力损失**：
   - PSI = 非 idle 进程中因等待资源而 stalled 的时间占比（%）
   - 分为 `some`（至少 1 进程 stall）和 `full`（全部进程 stall）
   - Memory PSI 涵盖 3 类 stall：direct reclaim、file refault、swap-in
   - 来源：TMO(ASPLOS'22) §3.2

2. **Promotion rate 是不够的**：
   - Promotion rate（swap-in 次数）忽略 backend 延迟差异
   - 快 SSD 上更高 promotion rate 反而带来更好性能（因为 offload 释放 DRAM 给热数据）
   - PSI 天然包含延迟因素 → 自动适配异构 backend
   - 来源：TMO(ASPLOS'22) §4.3 (Figure 12)

3. **Senpai 闭环控制公式**：
   - `reclaim_mem = current_mem × reclaim_ratio × max(0, 1 - PSI_some / PSI_threshold)`
   - 维持"subliminal pressure"——PSI 略高于 0 但不造成可感知性能损失
   - 单一全局配置 `PSI_threshold=0.1%` 适用于所有应用
   - 来源：TMO(ASPLOS'22) §3.3

4. **Non-resident cache tracking**：
   - 文件页被回收时存储 fault 计数器到 shadow entry
   - 下次 fault 时用 reuse distance 区分 refault vs first-time access
   - 只有 refault 才算入 memory PSI
   - 内核 reclaim 据此平衡 file cache vs swap 回收
   - 来源：TMO(ASPLOS'22) §3.4

### 实践启发

- **指标优先级**：Low-level count（次数）< High-level time（时间损失）。任何基于计数的阈值在异构系统中都不可靠
- **PSI 是 Linux 通用资源健康指标**：可通过 `cat /proc/pressure/{cpu,memory,io}` 查看，已默认启用于所有主流发行版
- **从低风险开始渐进推广**：先 offload 基础设施内存（SLA 宽松）→ file-only → 加入 swap
- **生产 offload 的保守节奏**：每 6 秒回收最多 1% 当前内存，收缩分钟级，扩展即时
- **Zswap backend**：延迟 ~40μs（比 SSD 快一个数量级），适合可压缩数据（压缩比 3-4×）
- **SSD backend**：每字节成本 <1%（vs DRAM），适合不可压缩数据（如 quantized ML 模型，压缩比仅 1.3-1.4×）
- **SSD 耐久性**：通过 Senpai 调节写入速率（1MB/s 阈值）避免提前损耗

### 生产数据 (Meta Fleet)
- Datacenter tax 占 13% 内存（基础设施）
- Microservice tax 占 7% 内存（框架开销）
- TMO 总节省：20-32% 总内存（数百万台服务器）
- Senpai CPU 开销：0.05% 所有 CPU cycles
- 压缩算法：zstd（最佳压缩比/开销平衡），内存池：Zsmalloc

### 与 PACT 的对比

| 维度 | TMO(ASPLOS'22) | PACT(ASPLOS'26) |
|------|---------------|-----------------|
| 粒度 | cgroup 级 | page 级 |
| 反馈信号 | PSI (% stall time) | PAC (stall cycles/page) |
| 信号来源 | 纯软件（进程状态） | 硬件 PMU + 分析模型 |
| 策略 | proportional feedback (PSI→reclaim rate) | priority-based (PAC→bin→promote top) |
| demotion | LRU 驱动 | eager demotion |
| 部署 | Meta 生产（数百万服务器） | 实验环境（CloudLab） |

---

## CXL 硬件辅助内存追踪

### 核心问题
CPU 侧的热页追踪（PEBS 采样、PTE access bit 扫描）存在三个根本局限：采样精度不足（warm 被误判为 hot）、无法观测页内访问分布（稀疏热页造成 read amplification）、profiling 本身有 CPU 开销。

### 关键洞察

1. **"测量点靠近数据源"**：
   - 将 hot-page/hot-word 追踪器嵌入 **CXL 内存控制器**（非 host CPU）
   - 零 CPU 开销、精确计数（非采样）、透明（应用和 OS 无需修改）
   - 来源：M5(ASPLOS'25)

2. **稀疏热页 (Sparse Hot Pages)**：
   - 许多应用（尤其 DLRM 推荐模型）中，一个 4KB 页内仅少量 64B word 真正热
   - 整页迁移导致 read amplification：热的 64B 带上 4032B 冷数据占用 fast-tier
   - 需要 per-word 粒度追踪才能发现这个现象
   - 来源：M5(ASPLOS'25)

3. **Hot-Page Tracker (HPT) + Hot-Word Tracker (HWT)**：
   - HPT：跟踪 top-K 最热 4KB pages
   - HWT：跟踪 top-K 最热 64B words
   - 均为硬件 priority structure（类似 sorted heap），在 CXL controller 内
   - M5-Manager（用户态软件）组合 HPT/HWT 输出驱动迁移策略
   - 来源：M5(ASPLOS'25) §Design

### 实践启发

- **"热"是一个相对概念，需要精确区分 warm vs hot 才能有效利用有限的 fast-tier 空间**
- **Word 粒度追踪揭示了 page 粒度不可见的浪费**：如果应用有稀疏热页特征，应考虑 cache-line 粒度迁移或 partial page pinning
- **硬件 profiling 消除观察者效应**：CPU 侧的 profiling 自身消耗被测量资源，near-memory 追踪无此问题
- **M5 验证了 PACT 的动机**：CPU 方案把 warm 当 hot → 印证了 frequency-based 方法不够精确

### 三篇论文对比

| 维度 | TMO(ASPLOS'22) | PACT(ASPLOS'26) | M5(ASPLOS'25) |
|------|---------------|-----------------|---------------|
| **方法** | 纯软件 | 软件 + 标准 PMU | 硬件(CXL controller) + 软件 |
| **反馈信号** | PSI (% stall) | PAC (cycles/page) | HPT/HWT (精确访问计数) |
| **粒度** | cgroup | page (4KB/2MB) | page (4KB) + word (64B) |
| **CPU 开销** | 0.05% cycles | PEBS 采样开销 | 零（全部 offload） |
| **可部署性** | 即插即用（Linux 主线） | 需要 Intel PMU | 需要新硬件 |
| **核心洞察** | 直接测生产力损失 | hotness ≠ criticality | CPU 侧观测有精度瓶颈 | CXL 延迟通过 3 条微架构通路转化为 stall |
| **部署规模** | Meta 数百万台 | CloudLab 实验 | 实验环境 | 265 workloads 跨 3 种 CXL 设备 |

**演进脉络**: SupMario(表征) → CAMP(预测) → PACT(执行)
- SupMario: 最大规模 CXL 表征，12 counters → 线性模型 91-94% fit
- CAMP: 闭式 3-分量分解 + 加权交错模型 → 预测任意 DRAM/CXL 比例
- PACT: 在线 per-page criticality → 驱动实际页面迁移
- TMO: 替代执行路径（反馈控制，不需要预测模型）
- M5: 观测层增强（硬件精确追踪，可提供更精确的输入）

---

## CXL 性能预测与建模

### 核心问题
异构内存（DRAM + CXL）的 slowdown 高度取决于 workload 的微架构特征，但枚举测试所有 DRAM/CXL 配置组合开销太高。需要一个低成本的方式预测"如果 X% 页面在 CXL，性能会怎样"。

### 关键洞察

1. **一次 DRAM-only profiling 足以预测所有配置**：
   - Workload 在纯 DRAM 下运行一次，暴露的微架构压力点（stall events）已经编码了它对延迟敏感度的全部信息
   - 对于带宽密集型 workload，额外加一次 CXL-only run
   - 来源：CAMP(ASPLOS'26)

2. **三-分量正交分解**：
   - CXL slowdown 可分解为 3 个独立分量：
     - **Demand reads**: LLC miss 后直接等待 CXL 数据返回
     - **Cache/prefetching**: CXL 延迟破坏了预取器和缓存的时间窗口
     - **Stores**: store buffer 因 CXL 写延迟而阻塞
   - 这 3 个分量正交，各自捕获了不同的微架构 stall 通路
   - 来源：CAMP(ASPLOS'26)

3. **闭式加权交错模型**：
   - 仅需 **12 个 PMU 计数器** + 一次 DRAM-only run
   - 可直接计算任意 DRAM:CXL 页面交错比例下的 slowdown
   - 无需枚举测试所有配置
   - 预测精度 **91-97%** (≤10% absolute error)，横跨 265 个 workload
   - 来源：CAMP(ASPLOS'26)

### 策略应用

**Best-shot Interleaving**:
- 用 CAMP 模型一次性算出最优 DRAM/CXL 交错比例
- 带宽密集型 workload 接近理想聚合带宽
- **最高 21% 提升** vs 现有 tiering

**Colocation Placement**:
- 用 CAMP 预测不同 colocation 组合下的 slowdown
- 选择干扰最小的组合
- **最高 23% 提升** vs 现有 colocation 方案

### 实践启发

- **"一次 profiling，预测所有配置"可推广**：任何涉及配置空间搜索的性能优化（缓存大小、网络带宽、GPU 显存）都可考虑类似 closed-form 模型
- **12 个精心挑选的 PMU 计数器胜过全量 ML**：理解微架构因果链比单纯堆数据更有效
- **CAMP + PACT 互补**：CAMP 做粗粒度 capacity planning（DRAM 应该分配多少 GB），PACT 做细粒度 page placement（哪些页应该放 DRAM）
- **SupMario → CAMP → PACT 是 MoatLab 的完整研究栈**：表征 → 预测 → 执行

### 四篇论文对照

| 维度 | TMO(ASPLOS'22) | CAMP(ASPLOS'26) | PACT(ASPLOS'26) | M5(ASPLOS'25) |
|------|---------------|-----------------|-----------------|---------------|
| **方法** | 纯软件 | 软件 + 标准 PMU | 软件 + 标准 PMU | 硬件(CXL controller) + 软件 |
| **反馈信号** | PSI (% stall) | 12 PMU counters → slowdown prediction | PAC (cycles/page) | HPT/HWT (精确访问计数) |
| **粒度** | cgroup | workload | page (4KB/2MB) | page (4KB) + word (64B) |
| **何时测量** | 在线持续 | 一次 profiling | 在线每 20ms | 在线持续 |
| **能做预测?** | ❌ (纯反馈) | ✅ (closed-form) | ❌ (纯追踪) | ❌ (纯追踪) |
| **能做迁移?** | ✅ | ❌ (仅预测) | ✅ | ✅ |
| **CPU 开销** | 0.05% | ~0 (一次性) | PEBS 采样开销 | 零 |
| **可部署性** | 即插即用 | 需要 Intel PMU | 需要 Intel PMU | 需要新硬件 |

### 跨领域共通模式

CXL tiered memory (PACT/TMO/CAMP/M5) 和 LLM KV cache 层次化管理 (Strata(OSDI'26)) 面临的高度相似问题：

| 共通问题 | CXL Tiered Memory | LLM KV Cache (Strata) |
|---------|-------------------|----------------------|
| 碎片化 | 4KB page migration | 1-32 token page 传输 |
| 粒度 tension | 大页 I/O 高效但浪费内存 | 大页 I/O 高效但降低 cache hit rate |
| 延迟隐藏 | 重叠 I/O 与计算 (PACT) | 重叠 I/O 与 prefill (Strata) |
| 反馈信号 | PSI % stall (TMO) / PAC cycles (PACT) | load/compute ratio (Strata) |
| I/O 瓶颈诊断 | Little's Law + CHA/TOR 观测 | Little's Law `X = C × S / L` |
| 布局优化 | — | layer-first vs page-first 解耦 |
| 降级/回收 | eager demotion (PACT) / LRU | write-back/write-through/selective |
| 调度策略 | adaptive promotion binning | balanced batch + delay hit deferral |

**核心教训**: 无论是 CPU 内存层级还是 GPU 内存层级，"冷热数据在不同 tier 之间搬运"这一问题是共通的——关键在于解决碎片化、平衡 I/O 与计算、并选择正确的反馈信号。

---

## 内存带宽隔离与弹性分配

### 核心问题
云计算中 CPU、存储、网络均可弹性分配，但内存带宽仍与容量绑定——云厂商按固定比率（GB/vCPU）提供 VM，缺乏带宽独立分配机制。90% 服务器平均带宽利用率 <44.5%，根源在于 spatial over-provisioning（独占硬件避免干扰）和 temporal over-provisioning（按峰值配置）。

### 关键洞察

1. **用通道替代采样/建模作为带宽控制基元**：
   - 带宽与可用通道数线性相关（DIMM 和 CXL 皆如此）
   - 硬件 all-ways interleaving 最大化单应用带宽但消除隔离可能
   - 通过 BIOS 禁用通道交错 → 每通道独立地址空间 → 软件控制 page-to-channel 映射
   - 来源：RamRyder(OSDI'26) §4.1

2. **容量和带宽可（近似）独立分配**：
   - DIMM 通道提供保证带宽，CXL 提供弹性容量和/或额外带宽
   - Channel-weighted interleaving：按 DIMM/CXL 通道的带宽加权比例跨 tier 分配页面
   - 来源：RamRyder(OSDI'26) §4.2

3. **硬件节流（Intel MBA/AMD QoS）的不可靠性**：
   - L2-LLC 间插延迟 → 不精确、非线性且浪费 CPU cycle
   - 小 VM 的延迟反而因节流增加（"惩罚所有人"而非隔离少数）
   - 来源：RamRyder(OSDI'26) §3.3, §6.1

4. **CXL 作为弹性带宽资源**：
   - CXL 通道也遵循带宽线性 scaling（~27 GB/s per channel）
   - Channel hot-plug + lazy migration → 动态调整带宽而不改变容量
   - 来源：RamRyder(OSDI'26) §4.3

### 实践启发

- **通道是带宽的最自然分配单位**：类似 PCIe lanes、NVLink lanes、network queues → partitionable resource
- **硬件 interleaving 是双刃剑**：峰值性能 vs 隔离/弹性 → 软件定义交错（3.6% overhead）是更好的 tradeoff
- **"通道"值得成为 OS 的一等抽象**：类似 NUMA node，channel 暴露给 guest OS 后可利用现有 NUMA 原语

### CXL 全视角（5 篇 + RamRyder）

| 论文 | CXL 用途 | 粒度 | 维度 |
|------|---------|------|------|
| TMO(ASPLOS'22) | Offloading 目标（swap 后端） | cgroup | 容量 |
| PACT(ASPLOS'26) | Slow memory tier（page migration） | Page | 延迟归因 |
| CAMP(ASPLOS'26) | Slowdown 预测目标 | Workload | 建模 |
| M5(ASPLOS'25) | CXL controller 硬件追踪 | Page+Word | 观测 |
| **RamRyder(OSDI'26)** | **弹性带宽 + 容量资源池** | **Channel** | **带宽+容量独立** |
