# Cloud Orchestration & Agentic Workflows

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| Agentic workflow 编排 | declarative specification, profile-guided optimization, cross-layer orchestration, SLO-aware runtime | Murakkab(OSDI'26) |

---

## Agentic Workflow 跨层优化

### 核心问题
Agentic workflow 的部署涉及三层独立优化：workflow 结构、每个 agent 的 model 选择、底层硬件 provisioning。三层互相不可见 → 无法端到端推理"用更便宜的模型是否仍能满足 accuracy SLO"。

### 关键洞察

1. **声明式规范分离逻辑与执行**：开发者描述"做什么"而非"用什么做"→ 系统自动匹配最优 model+hardware 组合
2. **Profile-guided optimizer 是跨层优化的关键**：离线 profiling 每个 model+hardware 组合的 cost/latency/accuracy → 在线选择满足 SLO 的最低 cost 配置
3. **Adaptive runtime**：动态重配置以响应流量变化和 model 更新
4. **Agentic infere nce ≠ standard LLM API calls**：多轮依赖、工具调用、条件分支——需要专门的 orchestration 系统而非通用 serving
- 来源：Murakkab(OSDI'26)

### 实践启发
- 声明式范式在 agentic workflow 中特别有效：workflow 结构复杂多变，手动指定每个 agent 的 model+hardware 组合不可扩展
- 跨层优化需要 profile 数据支撑——cost/latency/accuracy 三者之间存在可量化的 trade-off 曲面
- 能耗和成本的节省（3-4×）表明 agentic workflow 的资源浪费比 standard inference 更严重——因为有更多"过度配置"的自由度
