# TMO(ASPLOS'22)

- **来源**: ASPLOS '22, tmo_asplos22.pdf
- **年份**: 2022
- **作者**: Johannes Weiner, Niket Agarwal, Dan Schatzberg, Leon Yang, Hao Wang, Blaise Sanouillet, Bikash Sharma, Tejun Heo, Mayank Jain, Chunqiang Tang (Meta), Dimitrios Skarlatos (CMU)
- **类型**: 论文-系统
- **一句话 TL;DR**: Meta 的透明内存 offloading 方案，通过 PSI (Pressure Stall Information) 实时测量因资源短缺导致的"丢失工作量"，由 Senpai 用户态代理自动调节内存回收量，在数百万台服务器上节省 20-32% 内存，已上游化到 Linux 内核。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **PSI** (Pressure Stall Information) | 内核机制，实时测量 CPU/内存/IO 资源短缺导致的"丢失工作"比例（%） | TMO 的核心反馈信号，替代 promotion rate 等低级指标 |
| **Senpai** | 用户态代理，基于 PSI 动态决定每个 cgroup 应回收多少内存 | TMO 的控制平面 |
| **some pressure** | 至少有一个进程在等待资源的时长占比 | 捕获延迟影响，TMO 用此驱动 offload |
| **full pressure** | 所有进程同时等待资源的时长占比 | 检测严重资源短缺，触发紧急干预 |
| **refault** | 刚被回收的文件页又被 fault 回内存 | 区分"冷页回收"与"working set 误伤" |
| **non-resident cache tracking** | 记录被回收页的 fault 计数器，用于计算 reuse distance | TMO 判断文件缓存 eviction 是否伤及 working set |
| **memory tax** | 非应用本身消耗的内存：datacenter tax（基础设施）+ microservice tax（微服务框架） | TMO 首批生产部署目标 |
| **zswap** | Linux 内核组件，将匿名页压缩后存于 RAM 而非写盘 | TMO 支持的快速 offload backend（~40μs 延迟） |

## 背景与动机

### 问题
- DRAM 成本持续上升，占 Meta 服务器成本的 33%、功耗的 38%
- NVMe SSD 每字节成本比压缩内存低 ~10×，占总成本不到 3%
- 应用中存在大量"冷内存"（19-62% 冷数据比例），但现有方案（g-swap）仅支持单一压缩内存 backend，依赖 static promotion rate 阈值做 offline profiling

### 关键反例（为何 promotion rate 不够）
- 在更快 SSD 上，higher promotion rate 反而带来**更好**的应用性能（因为 offload 释放了更多 DRAM 给真正热的数据）
- 这直接与 g-swap "promotion rate 必须低于设定阈值" 的假设矛盾
- 证明需要一种能**直接反映应用对内存延迟敏感度**的指标

### 我的分析
TMO 是工业界非常经典的系统 paper——核心贡献不是学术创新而是工程洞察："与其猜测应用的性能敏感度，不如直接测量资源短缺造成的生产力损失。" 这个思路在 PACT(ASPLOS'26) 中被引用为 reactive approach，PACT 试图做得更精细（per-page 而非 per-cgroup）。

## 方案介绍

### 整体架构 (Figure 6)

```
Userspace        Kernel
  Workload ─Syscall→ Memory Management ─→ Paging ─→ Backend (zswap/SSD)
     ↑                                     ↑
  Senpai  ──Reclaim──→ cgroup files       PSI
     ↑                                    (report)
     └──── Observation ──────────────────┘
```

三大组件：
1. **PSI**（内核层）→ 测量
2. **Senpai**（用户态）→ 决策
3. **Reclaim 优化**（内核层）→ 执行

### 关键创新 1: PSI — 直接测量"丢失的工作量"

**核心概念**：PSI = 非 idle 进程中因等待资源而 stalled 的比例（%）

**some vs full**：
- `some`：至少 1 个进程在 stall → 捕获延迟级影响
- `full`：所有进程同时 stall → 捕获彻底阻塞

**memory PSI 的三类 stall 来源**：
1. Direct reclaim（分配时内存满 → 等页面回收）
2. 文件缓存 refault（刚回收的文件页又被读回）
3. Swap-in（等 swap 页读回）

**为何优于 promotion rate**：
- Promotion rate 只看 swap-in 次数，忽略 backend 延迟差异（40μs vs 9ms 的 refault 完全不可比）
- PSI 的 stalls 天然包含延迟因素 → 慢 device 上同样 swap-in 次数产生更高 PSI → 自动调整 offload 量
- PSI 还能反映 offload 带来的**正面**效果（更多 DRAM 可用 → 其他 stall 减少）

**开销**：context switch 时更新 PSI 状态，生产中 overhead negligible；已默认启用于所有主流 Linux 发行版（含 Android）

### 关键创新 2: Senpai — 闭环内存回收控制

**核心公式**：
```
reclaim_mem = current_mem × reclaim_ratio × max(0, 1 - PSI_some / PSI_threshold)
```

- `PSI_threshold = 0.1%`（全局最优，无需 workload 特定调参）
- `reclaim_ratio = 0.0005`
- 每 6 秒执行一次
- 当 PSI_some → 0 时，full speed reclaim；当 PSI_some → PSI_threshold 时，逐步减速

**关键实现细节**：
- 使用 `memory.reclaim` 而非 `memory.limit`（避免阻塞正在扩展的容器）
- 反应时间：收缩是分钟级（每周期最多回收 1%），扩展即时生效
- 同时监控 IO PSI（不仅 memory PSI），因为 refault 可能通过 SSD 拥塞间接影响应用

**为何用户态实现**：
1. 可使用浮点运算
2. 发布周期远快于内核（已多次迭代 Senpai 参数）
3. 可对不同 workload 使用不同配置

### 关键创新 3: 内核 reclaim 优化

**non-resident cache tracking**：
- 文件页被回收时，存储当前 fault 计数器到 shadow entry
- 下次 fault 时比较差值（reuse distance）→ 区分 refault vs first-time access
- Mem PSI 只用 refault stalls，排除首次访问的预期延迟

**平衡回收策略**：
- 修改内核 reclaim 算法：只要无 refault 就只回收 file cache
- 一旦 refault 出现 → 平衡 file cache 回收和 swap，基于 refault rate 和 swap-in rate
- 目标：更均匀地 offload file-backed 和 swap-backed 冷内存
- 已上游化到 Linux 内核

### 生产部署结果

| 场景 | 节省 | 说明 |
|------|------|------|
| **Datacenter Tax** | 平均 9% 总内存 | 软件包、profiling、logging 等基础设施 |
| **Microservice Tax** | 平均 4% 总内存 | routing、proxy 等微服务框架 |
| **Application (压缩内存)** | 7-12% 驻留内存 | 取决于数据压缩比 |
| **Application (SSD)** | 10-19% 驻留内存 | 不可压缩数据（如 ML byte-encoded 模型） |
| **总计（fleet-wide）** | **20-32%** | 数百万台服务器 |

## 证据与评估

### 测试环境
- Meta 生产环境，数百万台服务器
- 8 个代表性应用（Ads、Web、Feed、ML Reader 等）
- 2 种 backend：zswap（压缩内存，~40μs P90）和 NVMe SSD（470μs~9.3ms P90）
- 真实 A/B 测试，10+ 台主机每个实验

### 关键实验结果

**PSI vs Promotion Rate (Figure 12)**：
- 快 SSD → 更高 swap-in rate → 更高 RPS（反常识！）
- 慢 SSD → 更低 swap-in rate → 但 PSI memory/IO 更高 → Senpai 自动减少 offload
- **结论**：PSI 自适应 backend 性能，promotion rate 无法做到

**Web 应用 (Figure 11)**：
- 内存紧张时 RPS 逐渐下降（>20% loss over 2 hours）
- TMO 启用后消除 RPS 下降，节省 20% 内存
- 压缩内存比 SSD 更有效（因为 Web 数据压缩比高 4× → zswap 节省 13% vs SSD 4%）

**Senpai 调参 (Figure 13)**：
- 单一全局配置（PSI_threshold=0.1%）适用于所有应用
- 更激进的配置（Config B）获得更多内存节省但导致 RPS 下降和更高 IO PSI（额外文件缓存 eviction 伤害了前端指令获取）
- 证明了需要同时调优 file cache 和 anonymous memory

**SSD 耐久性 (Figure 14)**：
- Senpai 在达到 1MB/s 写入阈值后自动调节，多年运行无 SSD 提前损耗

### 部署策略（分阶段推广）
1. **Phase 1**: 先 offload datacenter/microservice tax（SLA 宽松）
2. **Phase 2**: file-only mode 推广到所有应用（回收 file cache）
3. **Phase 3**: 加入 swap 到最大应用（最严格 SLA，最小增量风险）

## 整体评估

### 真正的新意
1. **PSI 作为一等测量原语**：直接测量"生产力损失"而非推测性的低级指标，适配任意 backend 和应用
2. **Senpai 的控制策略**：基于 PSI 的比例-积分式 feedback loop，类似 PID 控制，全局参数即可工作
3. **Non-resident cache tracking**：把 reuse distance 分析实时化到内核 reclaim 决策中

### 优点
- **生产验证充分**：数百万服务器、>1 年运行、真实 SLO 验证
- **默认配置全局有效**：PSI_threshold=0.1% 不需要 per-workload 调优
- **开源 + 上游化**：PSI 在 Linux 主线，Senpai 在 Facebook Incubator
- **部署策略务实**：从低风险向高风险逐步推广，降低了事故风险

### 局限
1. **手动选择 backend**：zswap vs SSD 需要人工判断应用的可压缩性和延迟敏感度
2. **IO PSI 测量粗粒度**：硬件不提供细粒度设备竞争信息，所有等待 block IO 的进程统一视为 IO stall
3. **层级 backend 未实现**：理想方案是内核自动管理 zswap（warm）+ SSD（cold）+ NVM + CXL 的多级层级，已在 roadmap
4. **无 per-page 精度**：PSI 是 cgroup 级别的，无法识别具体哪些页最关键（这也正是 PACT 的工作）
5. **冷热检测依赖 LRU**：没有像 PACT 那样精确建模每个页面的性能影响

### 与 PACT(ASPLOS'26) 的关系

| 维度 | TMO(ASPLOS'22) | PACT(ASPLOS'26) |
|------|---------------|-----------------|
| 测量粒度 | cgroup 级 (PSI some/full) | page 级 (PAC) |
| 指标类型 | stall 比例 (%) | stall 周期数 (cycles/page) |
| feedback 来源 | 纯软件（进程状态跟踪）| 硬件 PMU 计数器 + 软件模型 |
| 控制方式 | proportional (PSI→reclaim rate) | 优先级排序 (PAC→bin→promote top) |
| demotion 策略 | LRU 驱动 | eager demotion (主动) |
| 部署规模 | 数百万 server, fleet-wide | 实验环境 (CloudLab) |
| 主要贡献 | 工业级 production system | 新指标 (PAC) + 新策略 (criticality-first) |

PACT 引用 TMO 为"stall-based but reactive"——TMO 用 stall 来控制 offload 量，但不知道具体哪些页最 critical。PACT 的贡献是将 criticality 从 cgroup 级缩小到 page 级。

### 可复用启发

1. **PSI 作为通用资源健康的指标**：`lost work due to resource shortage` 这个定义非常通用，任何资源管理场景（K8s scheduling、数据库 buffer pool 大小调节、CDN bandwidth allocation）都可以引入类似的"生产力损失"测量

2. **Senpai 的控制公式**：`reclaim = current × ratio × max(0, 1 - PSI/PSI_threshold)` 是一个简单的线性比例控制器，本质上是"尽可能用满资源，但不引起可感知的性能损失"——这种"维持 subliminal pressure" 的思想适用于很多自适应系统

3. **从低风险到高风险的分阶段部署**：tax → file-only → swap 的推广顺序降低了生产风险，值得任何基础设施变更参考

4. **Non-resident cache tracking 实现 reuse distance**：将 shadow entry 用于记录 eviction 序号，用差值判断 refault vs first-time access —— 这个技术可以推广到其他需要区分"冷回收"和"误伤"的场景

5. **PSI vs Promotion Rate 的对比教训**：低级指标（count）< 高级指标（time lost）。任何基于计数的阈值都隐含地假设"每次事件的代价相同"，在异构系统中不可靠

6. **单一全局配置优于 per-workload tuning**：PSI_threshold=0.1% 全局使用的经验说明一个好的指标应该在不同 workload 上有统一的操作点——这降低了对调参的依赖
