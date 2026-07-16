# OS Performance Tuning & Code Optimization

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| LLM 驱动的大规模代码优化 | fleet-wide profiling, embedding-based localization, anti-pattern mining, multi-stage verification | ECO(OSDI'26) |
| 可编程内核页缓存框架 | stacked file system, userspace cache policy runtime, non-blocking UPC, interruptible prefetch, XPU affinity, I/O template | PPC+MAIO(FAST'26) |

---

## LLM 驱动的大规模生产代码优化

### 核心问题
LLM 优化代码在 benchmark 上已被证明可行，但直接应用于生产环境的百万/十亿行代码面临两个**非 ML 系统**挑战：如何找到"值得优化且 LLM 能优化"的高价值目标（opportunity localization），以及如何确保 LLM 生成的代码不引发生产事故（reliability）。

### 关键洞察

1. **"大海捞针"式的目标定位**：不是对每行代码跑 LLM → 用 fleet-wide continuous profiling 找热点 + embedding-based semantic search 匹配 anti-pattern 词典 → 精确定位 0.01% 高价值优化候选
2. **多阶段验证链**：自动测试 + LLM self-review + 部署后监控 → 99.5% commits 无回滚
3. **LLM 推理成本 vs fleet-wide 节省**：推理成本可忽略不计（比 fleet-wide CPU/energy 节省小几个量级）
4. **代码优化中的人类审查**：960 个人类评估作为质量基准，而非仅看 pass@k 或 benchmark 分数
- 来源：ECO(OSDI'26)

### 实践启发
- "不是每一个 LLM 解决的问题都是 ML 问题"——opportunity localization 和 verification pipeline 是纯系统设计挑战
- Fleet profiling + embedding search + anti-pattern dictionary 是"大海捞针"型代码优化的通用模式
- 大型团队的代码优化需要人类评估基准（960 edits），而非仅看 LLM eval metrics
- 6,400+ commits / 25,000+ lines 数字表明大规模代码优化已从"demo"进入"production"阶段

---

## 可编程内核页缓存框架 (PPC)

### 核心问题
内核页缓存策略（预取/淘汰）对模型加载场景极其低效（SSD 带宽利用率仅 17%，忽略 XPU NUMA 亲和，淘汰无法感知一次性消费特征）。但重写内核页缓存不可接受（生产环境数百上千节点升级内核需数年）。需要一种同时满足三个约束的方案：非侵入（独立内核模块+兼容现有 FS）、灵活（支持复杂策略+.so 热切换）、轻量（低 front-end I/O overhead）。现有方案各缺一项：FUSE 太重（~14% overhead）、eBPF 太受限（不支持复杂策略+需内核修改）、fadvise 太弱（无法深度协作）。

### 关键洞察

1. **"可堆叠 FS = 劫持 cache miss 的最小侵入路径"**：不需要修改 VFS 或底层 FS——RFS（Routing File System）利用 Linux stacked filesystem 机制劫持底层 FS 的 read/page fault 的 cache miss 路径。Cache hit→直接返回（快速路径）；cache miss→封装 I/O 信息→UPC 事件→用户态策略→执行预取/淘汰→调用底层 FS 读数据。开销 ~3-6%（vs FUSE ~14-15%）。

2. **"UPC = per-core 无锁事件队列 + 非阻塞入队"**：Per-core xarray 队列避免锁竞争；非阻塞发送仅入队开销（无上下文切换）；用户态通过 poll/epoll 监听。CPU overhead 1-11%（随并发度变化）。

3. **"VFS 风格编程框架 = 用户只需实现四个函数"**：ppc_init/exit/prefetch/evict→编译为 .so→reg_policy 注册。CPRT 提供线程池+Cache Manager（core-bound 加载线程+ioctl 高效调用底层 FS 读+fadvise 淘汰+可中断+XPU 亲和感知）。策略与执行完全解耦。

- 来源：PPC+MAIO(FAST'26)

### 实践启发
- **"内核机制 + 用户态策略 = 可堆叠 FS + 事件队列"**：可堆叠 FS 是内核中最干净的扩展点——改操作而非改实现。RFS/UPC/CPRT 的分离设计是"内核提供原语、用户态提供策略"的典范——类似 sched_ext 将 CPU 调度策略移到用户态
- **"非侵入性的代价 ≤ 3-6%——对于 I/O 密集型场景可接受"**：如果 3-6% 的 overhead 可以换来完全可编程的缓存策略（进而可能获得 79% 的延迟缩减），这是极好的 trade-off
- **"I/O 模板 = 部署元数据→I/O 预测——zero online learning"**：同一模板的 I/O 是确定性的→只需一次 tracking→永久复用。这是"利用系统已有的分类信息进行 I/O 预测"的思路——类比 JIT 编译中的 profile-guided optimization
