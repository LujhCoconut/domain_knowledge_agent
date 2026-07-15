# Monitoring & Observability

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 网络根因分析 (RCA) | abstention algebra, PAM-style composition, deterministic decisions, Clos fabric, gray failures | CoreSec(OSDI'26) |
| LLM 推理在线 Tracing/诊断 | key sync points, critical path, abnormality-only detailed tracing, dynamic roofline, correlation diagnosis | StriaTrace(OSDI'26) |
| 应用定义资源的性能诊断 | LLM semantic inference + static analysis, resource bottleneck attribution, runtime tracking | gigiprofiler(OSDI'26) |
| GPU SDC 生产诊断 | silent data corruption, deterministic replay, homogeneous replay, full-state comparison, SDC-defective GPU | SDCHUNTER(OSDI'26) |
| GPU SDC 在线检测 | cSensor-cVerifier, mixed-precision checksum, self-equivalence, algorithmic detection, permanent SDC | AEGIS(OSDI'26) |
| LLM 训练Bitwise调试 | bitwise alignment, semantic-stable boundary, schedule-tolerant mapper, longest prefix match, benign nondeterminism | OpGuard(OSDI'26) |
| SMART SSD 遥测 LLM 解释 | representation layer, SMART logs, temporal trend tokens, CNN patches, online pattern memory, chain-of-thought, SSD failure prediction | SMARTTalk(OSDI'26) |
| 数据类型感知性能分析 | type-centric profiling, DWARF, Linux perf, data locality, struct field reordering, memory layout optimization | TypeCraft(OSDI'26) |

---

## 网络根因分析 (RCA)

### 核心问题
Clos 网络在持续背景故障中运行（CRC 错误、链路抖动），当客户工作负载失败时，数十个实体同时显示异常——大多数只是常规噪声。传统加权打分方法在嘈杂/部分/异步遥测下不稳定。

### 关键洞察

1. **显式弃权优于强制决策**：当证据模糊时，说"我不知道"比给出可能错误的确定性答案更好
2. **PAM 弃权代数移植到 RCA**：从 Unix 认证框架的 success/ignore/abstain/deny 模式获得了灵感
3. **拓扑感知 + 确定性组合**：Clos 物理结构编码为故障面，遥测代理在拓扑约束内组合信号
4. **单调收敛**：随着更多证据到达，决策只向正确方向移动，从不翻转
- 来源：CoreSec(OSDI'26)

### 实践启发
- "弃权"应作为任何基于不完整数据进行决策的系统的一等状态
- 确定性 > 概率性：相同的输入永远产生相同的输出，这对运维可解释性至关重要

---

## LLM 推理在线 Tracing 与诊断

### 核心问题
LLM 推理有严格的 SLO（TTFT < 10s, TPOT < 100ms），偶发性异常即可违反。通用 tracing 工具（TorchProfiler/Nsight）开销 10-20%，不能在严格 SLO 下使用；训练诊断工具无法捕捉推理中偶发的、用户触发的异常。

### 关键洞察

1. **"默认轻量 + 异常时详细"是最优的采集策略**：正常运行 <1% overhead，仅在异常时自动升级为详细 trace
2. **同步点是 LLM pipeline 的最佳观测点**：prefill 开始、KV cache 加载完成、GEMM 完成、AllReduce barrier、decode step 完成——这些点已暴露大部分延迟异常
3. **动态 roofline model 可用于异常检测**：基于回归的在线 roofline 区分"正常变慢"和"应该调查的异常"
4. **相关性诊断自动定位根因**：异常时自动关联 GPU util、KV cache hit rate、batch size、通信延迟等多维指标
- 来源：StriaTrace(OSDI'26)

### 实践启发
- "关键路径+tracing"优于"全量 tracing"——在 LLM 推理中，同步和 barrier 点已经足够
- 将 roofline model 从性能分析扩展到异常检测是一次好的跨领域思路
- 生产 tracing 系统最核心的设计选择是"默认采集什么"和"何时升级"——这决定了开销和信号质量的根本平衡

---

## 应用定义资源的性能诊断

### 核心问题
应用级资源（buffer pool、查询缓存、任务队列、WAL）的性能问题不被系统级指标（CPU util、内存）覆盖——开发者 57% 的工作时间花在性能问题诊断上，这类问题是**最难定位**的。现有工具要么只看系统级指标（看不到应用语义），要么需要手动 instrument（需要深入理解应用内部）。

### 关键洞察

1. **LLM 语义推断 + 静态分析验证的混合方法**：LLM 从代码中识别"这可能是资源管理代码"的语义线索 → 静态分析验证候选的真实性 → 结合两者优点
2. **"请求→资源交互→瓶颈"的三层归因模型**：追踪每个请求如何与已识别的资源交互 → 从聚合事件中检测瓶颈 → 归因到触发请求 → 链接回源代码路径
3. **应用定义资源的 visibility gap 是严重低估的问题**：很多"CPU busy but no throughput"的生产事故根因不在系统层面
- 来源：gigiprofiler(OSDI'26)

### 实践启发
- LLM + 静态分析的组合模式（"语义推断→形式化验证"）可推广到其他程序分析场景
- 性能诊断的核心是"归因"——不仅要找到 bottleneck，还要解释"谁的什么请求、通过什么代码路径、如何触发了这个 bottleneck"
- 15/15 全命中 + 2 新 bug 证明应用定义资源的诊断是一个有真实需求但工具空白的问题域

---

## GPU SDC 生产诊断 (SDCHUNTER)

### 核心问题
在数万 GPU 的 LLM 训练集群中，Silent Data Corruption (SDC) 表现为与软件 bug 无法区分的异常（unexpected CUDA error、NaN loss、shape mismatch）——工程师常花数天到数周调试代码，最终才发现是硬件缺陷。行业标准诊断方案（DCGMI stress test）漏检 >60%，因为 SDC 高度数据依赖且计算单元特定。

### 关键洞察

1. **"SDC 不是新硬件的专利——老化更常见"**：23 块缺陷 GPU 分析显示 SDC 常出现在中期生命周期，而非早期。需要持续全生命周期监控而非仅在验收时测试。

2. **"合成 benchmark 漏检 >60%"**：SDC 高度依赖具体的计算单元（complex math unit > Tensor Core）和输入数据。通用 GEMM stress test 无法覆盖。

3. **"确定性训练以 <0.01% 代价换取 bit-wise reproducibility"**：固定 RNG + 强制确定性 kernel + 标准化 reduce 顺序。无吞吐损失但 debug 时间减少 70%。

4. **"解耦恢复和诊断是关键"**：Phase 1 快速隔离到 parallel group → 训练恢复（1 小时内）；Phase 2 离线精确到 device → 硬件修复决策（1 小时内）。不需要等定位到具体 GPU 才开始恢复。

- 来源：SDCHUNTER(OSDI'26)

### 实践启发
- **"生产数据特征化比模拟有说服力得多"**：23 块真实缺陷 GPU 的分析是可信度的根本——benchmark miss rate >60% 这个发现直接影响实践
- **"确定性训练的代价-收益比极佳"**：<0.01% throughput loss → 70% debug time reduction。任何大规模训练集群都应默认开启
- **"先在粗粒度隔离、再精确定位"的分层诊断模式**：类似 SPADE 先缩小搜索空间再精确调度——适用于任何大规模集群故障定位
- **"与硬件团队的工具互补而非替代"**：SDCHUNTER 的诊断结果是给硬件团队提供 actionable 的输入（具体哪个 GPU、哪个 kernel 出错），而非替代硬件工具

---

## SMART SSD 遥测 LLM 解释 (SMARTTalk)

### 核心问题
SMART 属性是 SSD 健康监控的主要遥测——每个 drive 每天报告 multivarite counters（reallocated sectors、pending sectors、media errors）。但原始数值长序列 (1) LLM 无法直接理解——长历史+多变量使 token 预算溢出、时序结构不可见、LLM 产生幻觉趋势 (2) 现有 ML 方法依赖大量特征工程+标注数据，需随 firmware/workload/硬件变化重训练 (3) 大多数方法将复杂时序行为压缩为数值评分或分类标签→可解释性差。核心需要：一个**表示层**桥接 numeric telemetry 和 language reasoning，而不是更强的预测模型。

### 关键洞察

1. **"Representation layer 而非 model tweak——CNN 编码 temporal patches→聚类趋势 token 库→LLM 理解"**：核心创新不是如何更好地预测 SSD 故障，而是如何将 raw SMART 数值遥测**翻译**为 LLM 可可靠推理的符号语言。CNN 编码短时间窗口的 temporal patches→聚类形成 attribute 级和跨 attribute 的趋势模式→将每个模式转化为稳定的自然语言 token（"media_errors spiked 3× in last 5 days"）。类似 Mimesys "trace→workload 逆映射"——表示层的创新 > 模型创新。
2. **"Online pattern memory——检测新行为无需重训练"**：当出现未见过的 SMART 模式时，智能检测并加入 token 库→不需要重新训练整个 pipeline。类似 vBPF "late-binding"——适应性不依赖离线重训练。
3. **"LLM chain-of-thought 提供可解释性和交互"**：不仅输出健康分类，还提供自然语言解释和 actionable 建议。操作员可以交互式追问。LLM-as-judge 评分：解释和建议 ~4.5/5，perturbation robustness >80%。Time-to-failure 估计 MAE ~10 天。

- 来源：SMARTTalk(OSDI'26)

### 实践启发
- **"Numeric telemetry → symbolic tokens → LLM reasoning 是通用三层 pipeline"**：不只是 SMART 日志——任何 multivariate time-series 遥测（网络流量、CPU metrics、sensor data）都可以受益于这种表示层桥接。类似 Mimesys "diffusion for workload synthesis"——核心是找到正确的中间表示
- **"Online adaptation 比定期重训练更实用"**：生产环境中 firmware/硬件的持续变化使离线训练的模型快速过时→online pattern memory 在不重训练的情况下吸收新行为

---

## 数据类型感知性能分析 (TypeCraft)

### 核心问题
Google 数据中心 40-60% CPU cycle 用于等待内存。现有 perf 工具（Linux perf、VTune、SCALENE）提供 code-centric 视图（hot functions/instructions）和 data-centric 视图（hot allocations），但**缺少连接两者的桥梁**——不知道一个 hot cache miss 对应的到底是什么数据类型的什么字段。现有分析说 "这行代码 cache miss 很多"，但不提供 "因为 struct task_struct 的 clock 字段跨越了两个 cache line 的边界"。优化者需要手工猜测→耗时长、不可规模化。

### 关键洞察

1. **"Type-centric profiling——不是只看代码或数据，而是看数据类型的访问模式"**：每个内存访问指令被注释上其对应的 type 和 field→性能 profile 可以按 type、按 field 聚合和排序。类似 Merlin "per-object characterization" 和 LifeLine "object-page lifetime alignment"——更细粒度的语义感知使优化意图更明确。
2. **"DWARF debug info→perf annotations——桥接调试世界和性能分析世界"**：DWARF 记录本质为调试设计→在优化后二进制上准确度大打折扣（AutoFDO/LTO/BOLT 严重破坏 DWARF 质量）。TypeCraft 修正这些退化以获得高准确度类型解析。
3. **"轻量级集成 + 数据中心 profiler 生态"**：不增加额外在线数据采集负担→适合持续生产 profiling。已上游化到 Linux perf→可作为数据中心标准 profiler 的一部分。Google 规模的生产验证。

- 来源：TypeCraft(OSDI'26)

### 实践启发
- **"Type-centric 是 code-centric 和 data-centric 之外的第三维度"**：不仅要知道 "哪里慢" 和 "哪个数据对象热"，还需要知道 "什么数据类型的什么字段产生了这些慢操作"。这是 profiling 的三维空间——code×data×type
- **"Struct reordering = 最廉价且最高效的内存优化之一"**：Linux 内核 rq 结构体的 clock 字段重排→将频繁共同访问的字段紧凑到同一 cache line。这是 per-type profile 直接引导的优化
