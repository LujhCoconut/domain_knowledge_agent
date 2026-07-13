# System-Level Performance Tuning

系统层性能调优知识与经验，涵盖 CPU、内存子系统、内核参数、NUMA 等。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| Tiered Memory 管理 | CXL, NUMA, page migration, hotness vs criticality | PACT(ASPLOS'26) |
| 透明内存 Offloading | PSI, Senpai, swap, zswap, reclaim, memory tax | TMO(ASPLOS'22) |
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
