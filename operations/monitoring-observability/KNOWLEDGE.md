# Monitoring & Observability

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 网络根因分析 (RCA) | abstention algebra, PAM-style composition, deterministic decisions, Clos fabric, gray failures | CoreSec(OSDI'26) |
| LLM 推理在线 Tracing/诊断 | key sync points, critical path, abnormality-only detailed tracing, dynamic roofline, correlation diagnosis | StriaTrace(OSDI'26) |
| 应用定义资源的性能诊断 | LLM semantic inference + static analysis, resource bottleneck attribution, runtime tracking | gigiprofiler(OSDI'26) |
| GPU SDC 生产诊断 | silent data corruption, deterministic replay, homogeneous replay, full-state comparison, SDC-defective GPU | SDCHUNTER(OSDI'26) |

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
