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
| CXL sub-µs Stall 回收 | stall harvesting, hardware-software co-design, 20ns software switch, middle gap | LiteSwitch(OSDI'26) |
| 容器粗粒度调度抽象 | BOID, scheduling chaos, inter-core migration, two-level balancing, container thread bundling, CFS | vBOIDs(OSDI'26) |

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
| **MAC(OSDI'26)** | **NMP 加速内核元数据回收** | **Page descriptor / Xarray node** | **Metadata latency** |

---

## CXL 内核元数据管理

### 核心问题
大容量 CXL DRAM 使系统总内存膨胀，内核元数据（page descriptors 1.6% + Xarray）随容量线性增长。在 DDR:CXL = 1:4 的典型配置下，元数据可占 DDR 容量的 **24-40%**，迫使其溢出到慢速 CXL DRAM → kswapd 回收效率 -42% → 应用被迫做前台回收 → p99.99 尾延迟 +2.8×。

### 关键洞察

1. **元数据溢出 → kswapd→foreground 连锁反应**：
   - 元数据放在 CXL (2.4× latency) → kswapd 访问变慢 → free pages 不足 → 应用线程做 foreground reclamation (on critical path)
   - Foreground reclamation frequency +6.5× → p99.99 tail latency +2.8×
   - page descriptor traversal 慢 3.6×（超过 2.4× 差异 → 更深层效率损失）
   - 来源：MAC(OSDI'26) §3

2. **内核 direct-map 消除了 NMP 的地址转换成本**：
   - Linux 内核将所有物理内存通过 direct-map 线性映射 → `__pa(vaddr)` 只需一次减法
   - 这意味着 CXL 侧的 NMP 无需 MMU/page table walk → 可以直接用物理地址访问 metadata
   - 来源：MAC(OSDI'26) §3.2

3. **Pin metadata in DDR 的 hidden cost**：
   - 强制将 Xarray node 分配 pin 到 DDR → slab allocation contention → allocation latency 从 2-4µs 涨到 10-600µs
   - 反直觉：**把 metadata 放 CXL + NMP 加速 比 强制 pin 在 DDR 更好**
   - 来源：MAC(OSDI'26) §5.3

4. **标准 CXL.mem write 作为无协议修改的 NMP 触发**：
   - 不定义新 CXL 协议命令 → 用 packet filter 匹配写的地址范围来识别 NMP 请求
   - 完全兼容现有硬件，仅需 CXL controller 侧小改动
   - 来源：MAC(OSDI'26) §4.2

### 实践启发

- **"元数据的元数据"是 scaling 中容易被忽视的瓶颈**: 系统总内存增长 → metadata 增长 → metadata access 成为瓶颈
- **Kernel direct-map 是 NMP-friendly 的设计**: 任何 OS 内 NMP offload 都应优先考虑利用 direct-map
- **简单+重复的 kernel 操作是最佳 NMP target**: page descriptor flag check (bitmask) + Xarray walk (arithmetic) — 无复杂控制流
- **Second-order effect 陷阱**: 看起来"把 metadata 放回 DDR"是 obvious fix，但实际引发了 slab contention 的新瓶颈

### CXL 全视角（6 篇 CXL 论文）

| 论文 | CXL 用途 | 粒度 | 维度 |
|------|---------|------|------|
| TMO(ASPLOS'22) | Offloading 目标（swap 后端） | cgroup | 容量 |
| PACT(ASPLOS'26) | Slow memory tier（page migration） | Page | 延迟归因 |
| CAMP(ASPLOS'26) | Slowdown 预测目标 | Workload | 建模 |
| M5(ASPLOS'25) | CXL controller 硬件追踪 | Page+Word | 观测 |
| RamRyder(OSDI'26) | 弹性带宽 + 容量资源池 | Channel | 带宽+容量独立 |
| **MAC(OSDI'26)** | **NMP 加速内核元数据** | **Metadata node** | **Metadata latency** |
| **NEMO(OSDI'26)** | **可编程 MC telemetry engine** | **任意 (mask-shift-add 可编程)** | **Observability** |

---

## 内存碎片化与 Frontend-Backend 解耦

### 核心问题
现有所有 tiering backend 都假定"页面级的 cold/hot 信号足够好"，但 Google 6 个生产 trace 显示活跃页中 **70-90% byte 从未被访问** — 根本原因是 allocator 按 size 分配对象，不考虑 access pattern → 热对象和冷对象在同一页内交错混合（hotness fragmentation）。

### 关键洞察

1. **Page utilization 是第一性瓶颈**：
   - 如果 page utilization <20%，backend 识别"热页"也是假热 — 页内冷数据被"困"在快 tier
   - 先提高页面质量再优化 tiering policy，顺序不能颠倒
   - 来源：OBASE(OSDI'26) §2

2. **Frontend-Backend 解耦 = Address-space engineering + Reclamation**：
   - Frontend (OBASE): 组织 address space → HOT/COLD heap → 整页均匀热或冷
   - Backend (kswapd/TMO/TPP/Memtis): 现有页面回收机制 → 面对均匀页面时决策质量倍增
   - 零 backend 修改：COLD heap 页面自然被任何 backend 标记为 inactive
   - 来源：OBASE(OSDI'26) §3

3. **C++ 中实现 safe concurrent object migration**：
   - Guide abstraction（替代 raw pointer）+ Epoch-based ATC + Optimistic CAS migration
   - Thread 永不阻塞，迁移失败 → 对象留在原位
   - Overhead 仅 2-5%（vs PEBS 采样的 >50% at >1% sample rate）
   - 来源：OBASE(OSDI'26) §3.2, §3.5

### 实践启发

- **测量 page utilization 是 tiering 优化的第一步**：如果 page util 低，换个更好的 backend 也没用
- **Tiering = Layout + Reclamation**: 将"哪些页该回收"的问题拆为两个子问题 — 前者优化数据组织，后者优化迁移决策
- **OCC-style migration 在 OS-level 对象管理中实用**: 简单、无锁、失败安全

### 内存层级论文 7 篇全景

| 论文 | 优化层面 | 核心贡献 |
|------|---------|---------|
| **OBASE(OSDI'26)** | **Layout (frontend)** | **消除 hotness fragmentation，page util ↑ 2-4×** |
| TMO/TPP/Memtis | Reclamation (backend) | 页级迁移策略 |
| PACT(ASPLOS'26) | Reclamation (backend) | Criticality-driven migration |
| CAMP(ASPLOS'26) | Modeling | Slowdown prediction |
| M5/NEMO/MAC | Observability | 更好的 telemetry/追踪 |
| **MDK(OSDI'26)** | **Theory/Policy** | **OPP + MPC + eviction properties — 回收策略设计框架** |

---

## 数据中心内存回收理论

### 核心洞察
传统内存管理是"给定固定内存，最小化 miss rate"；数据中心的问题是反过来的——在满足 per-window 性能 SLO（如 promotion rate）的前提下最大化内存节省。这使得 OPT/VMIN 不再是最优（它们将 page faults 聚类在少数 window 中违反 SLO），MRC 也不再适用。

### 关键知识

1. **优化目标翻转**：
   - 传统: `min miss_rate s.t. cache_size ≤ M`
   - 数据中心: `max memory_savings s.t. promotion_rate ≤ target per window`
   - 来源：MDK(OSDI'26) §2

2. **OPP — 反问题的最优策略**：
   - 两遍算法：统计 per-window unique pages → 对每次 access 决定回收（当且仅当未来不违反 promotion rate）
   - 核心行为：**尽可能早回收，让 faults 均匀分散到各 window**（而非最小化总数）
   - 来源：MDK(OSDI'26) §3.2

3. **Eviction decisions/times — 理论性质**：
   - 更 aggressive 参数 → eviction 更多 + 时间相同 → 只需计算 critical parameter → O(n) MPC 生成
   - 传统缓存理论（包含性质）的数据中心版本
   - 来源：MDK(OSDI'26) §3.3

4. **AGE vs PAW/PACE — 保守 vs 激进**：
   - AGE: 等 page 冷却后才回收（保守，适合不可预测 workload）
   - PAW/PACE: 基于 reuse distance 立即回收（激进，适合可预测 workload，+8-10% 内存节省）
   - 来源：MDK(OSDI'26) §5.4

### Google 内存管理三部曲

| 论文 | 层面 | 角色 |
|------|------|------|
| **MDK(OSDI'26)** | **理论** | OPP + MPC — 回答"离线最佳策略是什么" |
| TMO(ASPLOS'22) | **工程** | PSI + Senpai — 回答"如何在线近似" |
| OBASE(OSDI'26) | **Layout** | Address-space engineering — 回答"如何让输入数据更好" |

---

## CXL 内存 Stall 回收 (LiteSwitch)

### 核心问题
CXL 内存延迟（200-600ns）是本地 DRAM 的 3× 或更高——延长已有的 CPU 内存停顿→浪费更多 CPU 周期。现有方案在 DRAM 延迟尺度（SMT，~100ns）或 flash 尺度（Interrupt/IOP，>10µs）工作——两者之间的 **"中间空白"（200ns-1µs）** 无人覆盖。内存密集型工作负载将 20-80% CPU 周期浪费在 memory stalls 上，CXL 加剧了这一效率损失。

### 关键洞察

1. **"中间空白"概念**：相邻的现有机制（SMT→interrupt）之间存在未被覆盖的延迟区间 → CXL 延迟恰好落在其中
2. **硬件精确识别 + 软件快速切换的分工**：硬件精准识别 "这是 CXL stall"（零数据路径延迟）→软件以 <20ns 保存最小上下文并切换到 ready thread
3. **20ns 软件切换比传统 context switch 快一个数量级**：只抢救必要的寄存器——不执行完整 OS 上下文切换
4. **在不修改应用的前提下回收 CXL 延迟损失的 80%**：前提是每个 core 有足够数量的可用线程
- 来源：LiteSwitch(OSDI'26)

### 实践启发
- "中间空白"是系统设计中的一个通用分析概念：当两种机制覆盖相邻的延迟区间时，中间可能留下未被覆盖的空白
- 硬件-软件协同设计的分工原则：硬件做精确识别（低成本）、软件做快速响应（精简上下文）
- CXL 不仅是"容量/带宽问题"——如何在 CPU 层面回收被延长的 stall 周期是一个同等重要但被忽视的维度

### CXL 论文全景（10 篇）

| 论文 | 层面 | 角色 |
|------|------|------|
| TMO(ASPLOS'22) | 工程 | PSI + Senpai — 在线反馈控制 |
| PACT(ASPLOS'26) | 执行 | Per-page criticality — 页面迁移 |
| CAMP(ASPLOS'26) | 预测 | CXL slowdown 预测 |
| M5(ASPLOS'25) | 观测 | Hot-page/word hardware tracking |
| RamRyder(OSDI'26) | 管理 | Channel-level bandwidth allocation |
| MAC(OSDI'26) | 元数据 | NMP 加速 metadata reclamation |
| NEMO(OSDI'26) | 可观测 | 可编程 MC telemetry |
| OBASE(OSDI'26) | 布局 | Address-space engineering |
| MDK(OSDI'26) | 理论 | OPP+MPC 回收策略设计 |
| MDK(OSDI'26) | 理论 | OPP+MPC 回收策略设计 |
| **LiteSwitch(OSDI'26)** | **CPU 前端** | **CXL sub-µs stall 回收** |
| **vBOIDs(OSDI'26)** | **调度** | **容器的粗粒度调度抽象** |

---

## 容器粗粒度调度抽象 (vBOIDs)

### 核心问题
云运行时每台机器部署数千容器（Alibaba RunD: 2500+/node, Junction: 3000+）。容器比 VM "轻量"但性能比 VM 更差——可达 **80%+ 下降**。根本原因是**抽象泄漏**：容器将内部并发直接暴露给 host 内核。Hotel Reservation（24 微服务）容器化后产生 500+ host-visible 线程，而 VM 仅暴露 50 个 vCPU。CFS 面对数千线程→频繁做负载均衡→inter-core migration 比 VM **高一个数量级**→TLB shootdown + cache invalidation + branch predictor disruption → **调度混沌**。

### 关键洞察

1. **"VM 性能更好不是因为隔离更重，而是因为 vCPU 将内部并发折叠为少量调度单元"**：容器缺少等效的粗粒度抽象→线程泄漏到 host→CFS 过度反应→大量跨核迁移→硬件局部性崩溃。
2. **"BOID = 容器的 vCPU"**：将每个容器的线程打包为少量调度单元→host scheduler 只管理少量 BOID→内核级完全透明（不改应用/编排框架）。
3. **"两级均衡解耦全局和局部"**：host scheduler 迁移 BOID 跨核（粗粒度、低频），local balancer 在 BOID 内重新分配线程（细粒度、局部）→消除跨核颠簸同时保持利用效率。

- 来源：vBOIDs(OSDI'26)

### 实践启发
- **"粗粒度抽象不是更弱——是更稳定"**：VM 的 vCPU 抽象恰好在高密度场景下提供了稳定性。容器的完全透明在这里变成了诅咒。**适当的抽象 > 完全的透明**
- **"不要给调度器太多选择"**：CFS 在数千线程面前过度反应→减少选择空间（只调度少量 BOID）→调度器表现更好
- **"两级调度 = 全局稳定性 + 局部灵活性"**：全局层粗粒度管理资源分配，局部层细粒度优化内部效率——适用于任何分层调度系统
