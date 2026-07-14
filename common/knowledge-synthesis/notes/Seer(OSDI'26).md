# Seer(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-qin.pdf
- **全称**: Seer: Online Context Learning for Fast Synchronous LLM Reinforcement Learning
- **作者**: Ruoyu Qin (Moonshot AI & Tsinghua), Weiran He, Weixiao Huang, Yangkun Zhang, Yikai Zhao, Bo Pang, Xinran Xu (Moonshot AI), Yingdi Shan, Yongwei Wu, Mingxing Zhang (Tsinghua)
- **类型**: 论文-系统 (RL training optimization)
- **一句话 TL;DR**: 同步 RL 训练中 rollout 阶段占总迭代时间的 **63-87%**（Moonlight 84%、Qwen2-VL 63%、Kimi-K2 87%），核心瓶颈是**重尾长轨迹分布**导致的负载不均衡和 KVCache 内存波动。Seer 基于"共享相同 prompt 的请求在输出长度和响应模式上高度相似"的洞察，通过 divided rollout + context-aware scheduling + adaptive grouped speculative decoding 三个协同机制，将 rollout 吞吐提升 **2.04×**，长尾延迟减少 **72-94%**。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **Seer** | Online Context Learning RL 系统——利用请求间的"上下文"信号优化调度 |
| **Divided rollout** | 将 rollout 批次按输出长度预测动态拆分——避免长请求拖累整个批次 |
| **Context-aware scheduling** | 利用共享 prompt 请求的相似性预先判断哪些请求可能变长 |
| **Adaptive grouped speculative decoding** | 将相似 prompt 的请求分组，共享 speculative decoding 的草稿模型 |
| **Rollout stage** | RL 训练的推理阶段——占总时间的 63-87% |
| **Heavy-tailed output distribution** | CoT 推理的长尾效应：少数请求极长但主导了整体延迟 |

## 背景与动机

### 问题
- Rollout 阶段占据了同步 RL 训练的 **63-87%** 的总时间（不同模型），但严重受两个瓶颈限制：
  1. **KVCache 内存波动**：CoT 请求从几百 MB 的 KVCache 开始，在生成过程中爆发到数十 GB → 必须动态缩小 batch size 或触发昂贵的 preempt/re-prefill
  2. **重尾输出分布**：长尾请求使批量中的加速器利用率低下——在 rollout 批次末尾，只有少数超长请求仍在运行
- 已有的异步方案（如 Weave、RollArt）解决了依赖气泡问题，但在**同步 RL** 中上述瓶颈依然严重

### 核心洞察
"共享相同 prompt 的请求在输出长度和响应模式上高度相似"——Seer 利用这个 latent intra-group context 来预测哪些请求会变长（从而采取调度措施）。

## 方案介绍

### 三个协同机制

**1. Divided Rollout**
- 根据预测的输出长度动态拆分 rollout 批次
- 防止长请求拖累整个批次的结构化空闲时间

**2. Context-Aware Scheduling**
- 利用共享 prompt 请求之间的相似性信号
- 提前感知哪些请求可能产生长输出 → 在调度时给予特殊处理

**3. Adaptive Grouped Speculative Decoding**
- 将相似 prompt 的请求分组
- 共享 speculative decoding 的草稿阶段，减少重复计算

## 证据与评估

| 指标 | 结果 |
|------|------|
| Rollout 吞吐提升 | **2.04×** |
| 长尾延迟减少 | **72-94%** |
| 工作负载 | Moonlight, Qwen2-VL-72B, Kimi-K2 |
| Rollout 占比 | 63-87%（占整个 RL 迭代时间） |

## 可复用启发
- "共享 prompt → 相似的输出行为"是利用语义信息进行系统优化的重要信号——不仅适用于 RL，也适用于任何 LLM 批处理/推理场景
- Divided rollout 是处理重尾分布的通用策略：不等待最慢的请求，而是将它们隔离到独立的批中
