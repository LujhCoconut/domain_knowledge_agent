# MDK(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-patel.pdf
- **全称**: MDK: Rethinking the data center memory reclamation problem
- **系统名**: MDK (Memory Designer's Kit)
- **作者**: Shaurya Patel (Google & UBC), Suli Yang, Yawen Wang (Google), Kan Wu (xAI), Alexandra (Sasha) Fedorova (UBC & MongoDB), Margo Seltzer (UBC), Kimberly Keeton (Google)
- **类型**: 论文-系统 (优化理论 + 策略设计框架)
- **一句话 TL;DR**: 传统内存管理优化目标是"给定固定内存，最小化 miss rate"，但数据中心的问题是反过来的——**在满足应用 SLO（如 promotion rate）的前提下，最大化内存节省**。MDK 提供了一套完整的离线策略设计工具箱：provably optimal 的 OPP 策略、Memory Performance Curves (MPC)、理论性质（eviction decisions & times）、以及比仿真快 **12.5-208×** 的 MPC 生成算法。基于 MDK 设计的三个新策略比 Google g-swap 的 AGE 策略**最高多省 10% 内存**，PAW 策略已在 Linux 实现并验证 +4% 内存节省。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **MDK** (Memory Designer's Kit) | 内存回收策略的离线设计框架 | 核心贡献：包含 OPP + MPC + 理论性质 + 高效生成 |
| **OPP** (Optimal Performance Proxy) | 两遍 offline 算法，在 time window 约束下最大化平均内存节省 | 证明最优的回收策略（类似传统 OPT 的反问题版本） |
| **MPC** (Memory Performance Curve) | 数据中心版的 MRC：x 轴 = promotion rate（性能约束），y 轴 = average memory savings | 替代传统 MRC 的策略评估工具 |
| **Eviction decisions property** | 若 R2 比 R1 更 aggressive → ER1 ⊆ ER2（子序列关系） | 使高效 MPC 生成可能的关键性质 |
| **Eviction times property** | 若 R2 比 R1 更 aggressive → eviction 时间相同 | 更强的性质，进一步加速 MPC 构建 |
| **Critical parameter RC** | 导致某个 page fault 的最不 aggressive 参数设置 | 类比传统 MRC 中的 critical capacity |
| **Promotion rate** | Google g-swap 的性能代理指标：page faults / unique pages accessed per time window | 本文约束目标 |
| **AGE policy** | Google g-swap 的 age-based 回收策略（T 时间内未访问就回收） | 主要 baseline |
| **PAW** (Prior Age with Wait) | 基于历史 reuse distance + 1 分钟等待的启发式策略 | MDK 设计的第一个新策略 |
| **PACE** (Prior Age and Current Elapsed) | 双参数（P: 历史 reuse distance, A: 当前未访问时长）策略 | 保证不输给 AGE 的最优两参数策略 |
| **L-OPP** (Learned OPP) | 用 Gradient Boosted Tree 模仿 OPP 决策的 ML 策略 | 证明 OPP 可用于 policy 生成 |

## 背景与动机

### 问题
传统内存管理的优化问题是：给定固定内存大小 M，最小化 miss rate（Mattson's OPT）。

**数据中心的优化问题是反过来的**：
- **目标**: 最大化内存节省（跑更多 job）
- **约束**: 满足 per-time-window 的性能 SLO（如 promotion rate ≤ 阈值）
- **操作模式**: 主动回收（不等内存满，proactive reclamation）

这意味着（1）OPT/VMIN 已不再是最优——它们在 time window 内的 page fault 可能聚类在一起，违反 SLO；（2）传统的 MRC 已不适用——它们以 miss rate 为 y 轴，而数据中心需要 promotion rate→memory savings 的 MPC。

### 为什么需要新工具

| 传统工具 | 为什么不行 | MDK 替代 |
|---------|-----------|---------|
| OPT (most recently reused) | 违反 time-window promotion rate 约束 | OPP |
| MRC (miss ratio vs cache size) | 目标/约束颠倒 | MPC |
| 包含性质 (inclusion property) | 变长内存回收不适用 | Eviction decisions + eviction times |
| 基于包含性质的高效 MRC 构建 | 不适用 | MDK MPC generator |

**Table 1 核心示例**: OPT (cache=3) 和 VMIN (reuse distance=3) 都将 page faults 聚类在 T5（率 = 100%），违反 50% 目标。OPP 通过提前回收 a（在 T1）将 faults 分散到不同 window。

### 关键 insight
数据中心的问题是 **"will my page fault pattern violate a per-window SLO?"** 而不是 **"how many page faults will I have in total?"**。最优策略必须将 faults **均匀分散**到各 time window，而非仅最小化总数。

### 我的分析
这篇论文和 TMO(ASPLOS'22) 来自同一支 Google 团队（Suli Yang, Kimberly Keeton，后者也是 OBASE 的作者）。它是三篇 Google memory 论文的"理论支柱"：TMO 是工程实现，OBASE 是 frontend layout 优化，MDK 是 backend 策略的理论框架。这三篇合在一起构成了 Google fleet memory management 的完整技术栈。

## 方案介绍

### MDK 四组件

**1. Memory Performance Curve (MPC)** — 数据中心版 MRC
- x 轴: promotion rate（性能 proxy 约束）
- y 轴: average memory savings
- 替换传统 MRC 的 miss rate→cache size

**2. OPP (Optimal Performance Proxy)** — offline 最优策略 (§3.2)
- 两遍算法：
  - Pass 1: 统计每个 window 的 unique page count (Uw)
  - Pass 2: 对每次 page access，若回收它在未来 window 不会违反 promotion rate (FB/UB ≤ target)，则回收
- **核心行为**: 尽可能早地回收页面，使 future faults 均匀分散，避免聚类
- 可推广到任何可在 trace 上计算的性能约束
- 证明（Appendix C）保证 optimality

**3. 理论性质** (§3.3): Eviction decisions & eviction times
- **Eviction decisions**: 更 aggressive 参数的 eviction 集合是更保守参数的**超集**
- **Eviction times**: 不同 aggressive 参数下 eviction **时间相同**（更严格的子性质）
- 类比传统缓存中的 inclusion property，但适用于变长回收策略
- VMIN 满足两个性质；AGE 只满足 eviction decisions

**4. 高效 MPC 生成** (§3.4) — 12.5-208× faster than simulation
- 模板方法 (Listing 1): 用户只需实现 5 个 policy-specific 函数
  - `GetCriticalParam` — 给定 page fault，计算最少 aggressive 参数
  - `GetMemorySavings` — 计算因该 fault 省了多少内存
  - `AccumulateSavings` — 递归累积不同参数下的 savings
- 单遍 trace 遍历即可生成所有参数的 MPC
- 时间复杂度: O(n) vs 仿真 O(n²)

### 策略设计 (3 个新策略)

**PAW (Prior Age with Wait)**:
- 若上一 reuse distance > P 且至少 1min idle → 立即回收
- 适合可预测访问模式的 workload (GraphX, NGINX, TaoBench): 比 AGE 多省 **10%** 内存

**PACE (Prior Age and Current Elapsed)**:
- 双参数: P (历史 reuse distance) + A (当前未访问时长)
- 保证 ∀(P, A) 不输给 AGE（P=∞ 退化为 AGE）
- 专用 DP-based MPC generator (~300 LOC)
- Cassandra/GraphX 上比 AGE +8-10% 内存节省

**L-OPP (Learned OPP)**:
- Gradient Boosted Tree 分类器模仿 OPP
- 使用 6 个历史 reuse distances 作为 features
- 离线精确度需要改善（过保守），但展示了 OPP→policy 的路径

### Linux 验证 (§5.4.3)
- GraphX PageRank: PAW 比 AGE 多省 **4%** 内存，无性能损失
- 确认 offline MPC 预测 → online 实际行为的一致性

## 证据与评估

### 测试环境
- 8 个工作负载 (CloudSuite + DCPerf): Cassandra, Memcached, GraphX, NGINX, TaoBench, DjangoBench, FeedSim, MediaWiki
- Trace collection: kstaled-like kernel thread, 30s scan interval
- 8 个策略: LRU, OPT, VMIN, AGE, PAW, PACE, L-OPP, OPP
- MDK MPC generator: C++, 单策略 <87 LOC (单参数) / ~300 LOC (PACE)

### 关键结果

| 实验 | 结果 | 要点 |
|------|------|------|
| MPC 生成 vs 仿真 | **12.5-208× faster** | FeedSim 上 208× 加速; Memcached 55×; Cassandra 110× |
| MPC 精度 | **<1% mean absolute error** vs simulation | 仅舍入误差 |
| OPP vs VMIN/OPT | OPP 维持 promotion rate ≤ target | VMIN/OPT 违反 time-window 约束 |
| PAW vs AGE | +10% 内存节省 (GraphX/NGINX/TaoBench) | 适合可预测 access pattern |
| PACE vs AGE | +8-10% (Cassandra/GraphX) | 保证不输给 AGE |
| L-OPP vs AGE | DjangoBench 上略优 | 离线精确度待改善，展示了框架可能性 |
| Linux 验证 | PAW +4% vs AGE (GraphX), 无性能损失 | 确认 offline→online 转移 |

### 为什么 MDK 能加速 MPC 生成

传统仿真需要 O(n × P) 时间（n = trace events, P = 参数组合数）。MDK 利用 eviction decisions 性质 → 对每个 event 只需计算 critical parameter → 单遍 O(n) 即可生成全局 MPC。本质上将"每个参数单独仿真"变为"一次遍历 + policy-specific 函数"。

## 整体评估

### 真正的新意
1. **重新定义优化问题**: 从 "minimize miss rate given fixed memory" 到 "maximize memory savings while satisfying per-window performance SLO" — 这个 flipped formulation 是论文的 foundation
2. **将传统缓存理论的工具箱完整移植到数据中心回收**: OPT→OPP, MRC→MPC, inclusion property→eviction decisions/times, Mattson's stack algorithm→MDK MPC generator
3. **OPP 的核心 insight**: 最优回收策略是"尽可能早地回收，让 faults 均匀分散到各 time window" — 这是反直觉的（传统 wisdom 是"让 pages 留在内存越久越好"）

### 优点
- **理论扎实**: OPP 有 optimality 证明，eviction 性质有正式定义
- **工程实用**: MDK generator 比仿真快 2 个数量级，单策略 <87 LOC
- **完整的工作流验证**: 从 offline trace → OPP 分析 headroom → 设计新策略 → MPC 评估 → Linux 验证
- **与 Google 技术栈的整合**: AGE (g-swap) + TMO + MDK 形成完整的数据中心内存管理理论
- **metrics 无关性**: MPC 框架支持任何 performance proxy (promotion rate, PSI, STAR...) 和内存节省目标

### 局限
1. **仅 offline**: MDK 不做 online tuning — 需要类似 Senpai (TMO) 的 runtime 来动态调整参数
2. **PAW/PACE 的参数仍需要 per-workload tuning**: 论文中用的是已知 trace 的离线调参；online 自适应 tuning 是 future work
3. **不支持在线指标如 PSI**: PSI 需要在运行时测量系统负载，无法直接从 page access trace 计算 — 需要近似模型
4. **L-OPP 离线精度不够**: 保守 + 低精度 → 在某些 workload 上无法匹配简单策略
5. **单参数/双参数限制**: 框架对单参数策略最方便（eviction decisions 性质保证）；多参数需要特殊处理（如 PACE 的 DP）

### 与本知识库内存论文的关系

MDK 是 Google 三篇内存论文中的"理论基础"：

| 论文 | 角色 | 核心贡献 |
|------|------|---------|
| **MDK(OSDI'26)** | **理论框架** | **OPP + MPC + 高效评估工具** |
| TMO(ASPLOS'22) | 工程实现 | PSI + Senpai (online feedback control) |
| OBASE(OSDI'26) | Frontend | Address-space engineering (layout quality) |

三者关系：
- **MDK 回答**: "给定 trace，最优回收策略是什么？"
- **TMO 实现**: "如何在线近似这个最优策略？"(PSI=online proxy)
- **OBASE 提升**: "如何让 trace 本身质量更好？"(减少 hotness fragmentation)

### 可复用启发

1. **"把问题反过来"的建模范式**: 传统 = minimize miss given fixed size → 数据中心 = maximize savings given performance constraint。这种 constraint→objective 的翻转可应用于任何从 single-machine 到 multi-tenant 场景的迁移（数据库 buffer pool、CDN cache、K8s resource allocation）

2. **将传统缓存理论完整移植到新问题域**: OPT→OPP, MRC→MPC, inclusion→eviction decisions — 不是发明新概念，而是通过重新定义问题来 unlock 传统工具箱的移植。这种研究范式本身有 general lesson

3. **"尽可能早地回收"优于"尽可能晚地回收"**: OPP 的反直觉 insight — 早回收让 faults 均匀分散（减少 per-window concentration），而晚回收容易导致 faults 聚束。在分布式系统、微服务 throttling 等场景中都可能有类似规律

4. **Eviction decisions/times 性质作为"可高效评估"的充分条件**: 只要策略满足这两个性质，就可以用 MDK 的模板构建 O(n) MPC generator。这是"先定义理论性质 → 再构建高效工具"的经典系统工程方法论

5. **Age-based (AGE) 和 Reuse-distance-based (PAW/PACE) 的互补性**: AGE 适合不可预测的 workload（保守但稳定），Reuse-distance-based 适合可预测的（激进但高效）。PACE 的双参数设计是"两全其美"的尝试
