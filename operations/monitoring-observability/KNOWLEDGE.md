# Monitoring & Observability

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 网络根因分析 (RCA) | abstention algebra, PAM-style composition, deterministic decisions, Clos fabric, gray failures | CoreSec(OSDI'26) |
| LLM 推理在线 Tracing/诊断 | key sync points, critical path, abnormality-only detailed tracing, dynamic roofline, correlation diagnosis | StriaTrace(OSDI'26) |

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
