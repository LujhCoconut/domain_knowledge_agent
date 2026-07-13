# PACT: A Criticality-First Design for Tiered Memory

- **来源**: ASPLOS '26, PACT_ASPLOS.pdf
- **年份**: 2026
- **作者**: Hamid Hadian, Jinshu Liu*, Hanchen Xu*, Hansen Idden, Huaicheng Li (Virginia Tech)
- **类型**: 论文-系统
- **一句话 TL;DR**: 提出 PAC (Per-page Access Criticality) 指标，用 CPU stall 而非访问频率来衡量每个内存页的性能影响，并基于 PAC 设计了首个在线、页粒度的 criticality-first tiered memory 系统 PACT，在 13 个 workload 上比 7 个 SOTA 方案最高提升 61% 性能，同时减少最多 50× 的页迁移次数。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **PAC** (Per-page Access Criticality) | 量化每个页面对 CPU stall 贡献的指标，单位是 CPU stall cycles | 核心指标，替代 hotness 作为页面放置决策依据 |
| **MLP** (Memory-Level Parallelism) | 内存级并行度，即同时进行的未完成内存请求数 | 用于"摊销"延迟成本，MLP 越高则单次访问的 stall 代价越低 |
| **TOR** (Table Of Requests) | Intel CPU 中 CHA 的请求队列表 | 提供 per-tier MLP 的硬件观测窗口 |
| **CHA** (Caching and Home Agent) | 位于 CPU 核心与 offcore (DRAM/CXL) 之间的缓存一致性代理 | PACT 用于区分 per-tier 内存流量的关键硬件结构 |
| **Freedman-Diaconis Rule** | 自适应直方图分箱宽度: `W = 2×(Q3−Q1)/∛n` | PACT 用于动态调整 promotion bin 宽度 |
| **Reservoir Sampling** | 在线均匀抽样算法，不需要预先知道总数 n | PACT 用于低开销维护 PAC 分布的近似样本 |
| **Eager Demotion** | 主动降级策略，不等内存压力就提前腾出 fast-tier 空间 | PACT 的核心迁移策略之一 |

## 背景与动机

### 问题
- DRAM 扩展放缓，CXL tiered memory 成为趋势，但 CXL 延迟是 DRAM 的 2–3×
- 现有 tiered memory 系统全部基于 **hotness（访问频次）** 做决策
- **hotness ≠ performance impact**：顺序遍历（高 MLP）vs 指针追踪（低 MLP），相同频率下 stall 代价相差可达 65×

### 作者的核心观察 (Figure 1)
用 Masim（合成）、GUPS（随机更新）、tc-twitter（真实图计算）展示：
- 同一访问频率的页面，PAC 可以分散在极大范围内
- 高频率不一定高 PAC
- tc-twitter 中 1 次访问的页面 stall 从 7 到 460 cycles（65× 差异）

## 问题定义
如何在 CXL/NUMA tiered memory 中，基于**页面的真实性能影响（PAC）**而非访问频率，在线做出页面放置和迁移决策？

三个核心挑战：
1. 如何在线、页粒度地量化 per-tier CPU stall（无直接硬件支持）？
2. 如何持续监控 PAC 并适应动态 phase 变化而不引入过高开销？
3. 如何设计基于 PAC 的迁移策略应对高度偏斜的 PAC 分布？

## 方案介绍

### 1. Per-tier Stall 建模 (§4.2)

**核心公式**: `LLC-stalls = k × (LLC-misses / MLP)`

- **k**: per-tier 系数，捕获 loaded latency + memory controller queuing delays + 架构常数
- **Per-tier MLP**: 通过 CHA 的 TOR 队列 occupancy 计算 `MLP = TOR_OCCUPANCY / TOR_OCCUPANCY_COUNTER0`
- **跨平台**: AMD 无 TOR 时可用 Little's Law 近似 `MLP ≈ Latency × Bandwidth`
- 在 96 workloads × 3 配置下验证，Pearson > 0.98（vs LLC-misses alone 的 0.82-0.89）

**架构洞察**: CHA 位于 core 与 offcore 之间，TOR 队列记录了所有 outstanding memory requests，是区分 per-tier 流量的理想观测点。

### 2. PAC 在线采样 (Algorithm 1, §4.3)

每 20ms 周期：
1. 读取 slow-tier LLC-misses delta 和 MLP delta（TOR 计数器）
2. 计算 slow-tier stalls: `S = k × LLC-misses / MLP`
3. PEBS 采样 slow-tier 页面访问（默认 1:400），记录 `vaddr` 和 `A_p`
4. 按比例属性: `S_p = S × A_p / A_total`
5. 更新累积: `PAC[p] = α × PAC[p] + S_p`（默认 α=1.0，纯累积）

**关键假设**: MLP 在 20ms 窗口内稳定（phase stability），使得均匀分摊合理。

**局限**: 同一 tier 上混有不同 MLP 的访问模式时（多租户 colocation），比例属性会稀释精度。Sapphire Rapids+ 的 PEBS per-load latency 可解决。

### 3. 迁移策略 (§4.4-4.5)

**Eager Demotion** (Algorithm 2):
- 不等 fast-tier 满才降级，主动从内核 LRU 腾空间
- 维持 `N_demoted ≥ N_promoted + m`
- 早期 aggressive → 随利用率增长收敛到按需降级

**Adaptive Promotion** (Algorithm 3):
- **Freedman-Diaconis binning**: `W = 2×(Q3−Q1)/∛n`
- **Reservoir Sampling**: 维护 100 样本近似 PAC 分布
- **Scaling Optimization**: 候选人过多时加倍 bin 宽度防 collapse
- 最高优先级 bin 保持小（top 1-5% 页面），稳定候选集

### 4. 实现 (§4.6)
- Linux 5.15, 2 个专用线程 (PEBS + migration)
- 每 4KB tracked page: 25 bytes (0.6% overhead)
- THP: 4KB 采样粒度 + 2MB 迁移粒度 (move_pages)

## 评估

### 测试环境
- Intel Xeon Skylake 双路, CloudLab
- DRAM 90ns / NUMA 140ns / CXL 模拟 190ns (2.1× DRAM)
- 7 baseline: Soar, Alto, Memtis, Colloid, Nomad, TPP, Linux NBT
- 13 workloads (图分析, GPT-2, Redis, SPEC HPC), 7 种 tier ratio, 4KB + THP

### 关键结果

| 实验 | 结果 | 要点 |
|------|------|------|
| bc-kron, 全部 ratio (4KB) | PACT 始终最优, 2.1-10.4× fewer promotions vs Colloid | 核心 benchmark |
| bc-kron, THP | PACT 1-19% 优于 Memtis (THP-aware) | 跨 page size 泛化 |
| 12 workloads, 1:1 | PACT 几乎全部最优; gpt-2 是唯一优于 NoTier 的系统 | 全面验证 |
| vs Soar (offline) | 6/10 接近 Soar, bc-kron 反超 2% | 在线 vs offline tradeoff |
| PAC vs Frequency head-to-head | PAC 提升 12-22% | 直接验证 criticality 优于 hotness |
| 敏感度分析 | 默认参数在所有 workload 上距最优 < 5% | 无需手动调参 |
| 带宽竞争 (1-8 MLC) | PACT 维持性能, 2.2-4.7× fewer promotions | 压力下仍 robust |
| Colocation (seq+random) | 61% 总提升, 300K vs 12M migrations | 混合访问模式 |
| Redis breakdown | +Adaptive + Both 逐步增益, max 40% vs Colloid | 各组件贡献 |

### 为什么 PACT 在图 workload 上尤其好
- 高 degree hub node: 频繁 + 低 MLP pointer-chasing → PAC 自然识别
- Frontier-based traversal: 每个 BFS/SSSP iteration 内重复访问同一 working set → PAC 累积
- Hotness 系统把所有频繁访问页面平等对待，无法区分

## 整体评估

### 真正的新意
1. 首次将 **online, page-granular performance criticality** 作为一等设计原则
2. **Per-tier MLP 分解** 通过 CHA/TOR 而非系统级 offcore MLP
3. **Freedman-Diaconis + Reservoir Sampling** 在内存管理中的新颖组合
4. **Eager demotion + Adaptive promotion** 更像流控而非简单阈值策略

### 局限
1. 比例属性在 multitenant colocation 下降级（作者承认）
2. 仅采样 load（store 影响视为 negligible）
3. PAC 纯累积 (α=1.0) 在极端 phase change 下可能有历史负担
4. Demotion 仍依赖内核 LRU 而非 PAC 驱动

### 可复用启发
1. "Criticality 作为一等设计原则"可推广到 CDN cache、DB buffer pool、MQ 优先级
2. CHA/TOR 是 Intel 平台做 per-tier 延迟归因的最佳观测点
3. Freedman-Diaconis + Reservoir Sampling 组合用于在线偏斜分布的自适应分箱
4. Eager demotion 流控模式可应用于 K8s scheduling、DB page eviction
5. Little's Law `MLP ≈ Latency × Bandwidth` 在无 TOR 平台上的替代方案
6. 20ms 作为开销-噪声-响应性之间的经验最优采样窗口
