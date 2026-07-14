# libDSE(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-li-tianyu.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 分布式推测执行——durable execution 的抽象与物理执行解耦，绕过故障无关路径上的同步持久化，端到端延迟降 up to 10×。

## 核心问题

Durable execution 引擎（Temporal/Azure Durable Functions/Beldi）自动持久化状态→透明恢复故障。但**频繁的同步持久化导致显著延迟**——而且随分布程度增长（更多分布式组件→更频繁的持久化→更高延迟）。这是 correctness-performance 的传统困境。

## 关键洞察

1. **"Decouple durable execution 的抽象与物理持久化"**：开发者代码假设同步持久化（简化编程），DSE runtime 透明地绕过并 delay 实际持久化→故障时反应式修复。类似 CoPilotIO "split SQ/CQ"——解耦语义保证和物理执行。
2. **"Speculation sandbox"**：runtime 缓冲对外的输出（用户/legacy DB）直到底层状态真正 durable→对外部系统隐藏推测性。内部分布式组件可以 speculative 通信。
3. **"Trade-off 在 speculation unit 的故障概率"**：只要单次 RPC request 成功的概率 > 失败概率，绕过同步持久化就是净收益。

- 来源：libDSE(OSDI'26)

### 实践启发
- **"语义-物理解耦"是云应用持久化的通用策略**：类似 VTC virtual tensor 和 InfiniDefrag GPA remap
