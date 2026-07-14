# Monitoring & Observability

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 网络根因分析 (RCA) | abstention algebra, PAM-style composition, deterministic decisions, Clos fabric, gray failures | CoreSec(OSDI'26) |

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
