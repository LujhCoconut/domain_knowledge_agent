# Murakkab(OSDI'26)

- **来源**: OSDI '26, osdi26-chaudhry.pdf
- **全称**: Murakkab: Resource-Efficient Agentic Workflow Orchestration in Cloud Platforms
- **作者**: Gohar Irfan Chaudhry (MIT CSAIL), Esha Choukse, Haoran Qiu, Íñigo Goiri, Rodrigo Fonseca (Microsoft Azure Research), Adam Belay (MIT CSAIL), Ricardo Bianchini (Microsoft Azure)
- **类型**: 论文-系统 (cloud platform + agentic AI serving)
- **一句话 TL;DR**: 现有 agentic workflow 在三层独立优化（workflow-level / agent-level / hardware-level）→ 无法端到端推理代价-准确率-latency 的权衡。Murakkab 引入**声明式 workflow 规范**（解耦逻辑与执行配置）+ **profile-guided optimizer** + **adaptive runtime**，实现跨层全局优化。比 LangGraph 减少 GPU 用量 **2.8×**、能耗 **3.7×**、成本 **4.3×**，同时满足 SLO。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **Agentic workflow** | 多模型+多工具的复合推理流程，包含 LLM 调用、工具执行、数据依赖 |
| **Declarative specification** | 声明式 workflow 规范——描述"做什么"而非"怎么做"，分离逻辑与执行配置 |
| **Profile-guided optimizer** | 离线 profiling → 推理各种 model+hardware 组合的 cost/latency/accuracy trade-off → 在线选择最优配置 |
| **Cross-layer optimization** | 跨 workflow-agent-hardware 三层的端到端优化——之前三层各自为政 |
| **Adaptive runtime** | 动态调整执行配置以响应 workload 变化，同时维持 SLO |

## 背景与动机

### 问题
- Agentic workflow 正在成为 AI 应用的主导范式
- 现有部署方式在三层独立优化：workflow 结构、每个 agent 的 model 选择、底层硬件 provisioning
- 这三层**互相不可见** → 无法做全局 trade-off（如用更便宜但略不准确的模型→省 GPU 但会违反 accuracy SLO 吗？）

### Murakkab 的答案
1. **声明式 workflow 规范**：开发者描述 workflow 的 goals/behavior/constraints，不指定具体 model 或 hardware
2. **Profile-guided optimizer**：离线 profile 每个 model+hardware 组合的 cost/latency/accuracy → 在线选择满足 SLO 的最低 cost 配置
3. **Adaptive runtime**：动态重配置以适应流量变化

## 证据与评估

| 指标 | vs LangGraph |
|------|-------------|
| GPU usage | **-2.8×** |
| Energy | **-3.7×** |
| Cost | **-4.3×** |
| SLO preservation | ✅ |
| Workflows tested | Multi-round debate, video security analysis, video query processing |

## 可复用启发

- "声明式规范 + profile-guided 优化"是 agentic workload 的 natural fit：分离"想做什么"和"用什么做"
- Cross-layer optimization 的核心价值：三层独立优化无法回答"用更便宜的模型会不会违反 SLO"这类跨层问题
- Agentic workflow 的 inference 负载特性与 standard LLM API calls 有本质区别（多轮依赖、tool 调用、条件分支）→ 需要专门的 orchestration 系统
