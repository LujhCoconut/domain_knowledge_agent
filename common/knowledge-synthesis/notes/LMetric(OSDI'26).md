# LMetric(OSDI'26)

- **来源**: OSDI '26, arXiv:2603.15202
- **全称**: Simple is Better: Multiplication May Be All You Need for LLM Request Scheduling
- **系统名**: LMetric (LM ETRIC — Large Model metric, 致敬 Lyapunov 稳定性理论和 Markov 排队论)
- **作者**: Dingyan Zhang (SJTU IPADS & Alibaba), Jinbo Han*, Kaixi Zhang*, Xingda Wei (corresponding), Sijie Shen, Chenguang Fang, Wenyuan Yu, Jingren Zhou (Alibaba), Rong Chen (SJTU IPADS)
- **开源**: https://github.com/blitz-serving/blitz-router
- **类型**: 论文-系统 (LLM serving + request scheduling)
- **一句话 TL;DR**: LLM 请求调度仅需**两个指标的乘积**（P-token × BS）作为调度分数——KV$ 命中的新 prefill token 数 × 实例当前 batch size，乘法在比较时自然消去超参数，无需任何 tuning。在真实 chatbot/agent 负载上 TTFT 降低 92% vs vLLM-v1、TPOT 降低 51% vs 生产调度器，已在阿里百炼数百 GPU 的生产集群部署验证。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **LMetric** (LM ETRIC) | 乘法调度分数 `P-token × BS` | 核心贡献：用乘法替代线性组合的调度指标 |
| **P-token** | 路由请求到某实例时需要新 prefill 的 token 数（考虑 KV$ 命中后节省的 token） | KV$-awareness 指标 |
| **BS** (Batch Size) | 实例当前的 batch size（主要反映 decode 负载） | Load-balancing 指标 |
| **KV$** (Key-Value Cache) | 之前请求的 attention 中间结果缓存 | LLM serving 的核心状态 |
| **TTFT** (Time to First Token) | 首 token 延迟 | prefill 阶段的服务质量指标 |
| **TPOT** (Time Per Output Token) | 每输出 token 的平均时间 | decode 阶段的服务质量指标 |
| **PD-colocation** | Prefill 和 Decode 在同一实例上处理 | 本文聚焦的部署模式（vs PD-disaggregation） |
| **Linear combination** | `λ·KV_indicator + (1-λ)·load_indicator` | 当前主流调度框架（需 per-workload 调参） |
| **KV$ hotspot** | 某个 prefix 仅被少数实例缓存，但被大量请求频繁访问 | 乘法策略可能失效的罕见情况 |
| **Indicator Factory** | 文中开发的 Rust 调度框架，自动收集 per-instance 指标 | 分析工具和公平对比平台 |

## 背景与动机

### 问题
LLM 集群中，global scheduler 需要同时考虑两个互相冲突的目标：
1. **KV$-awareness**: 将请求路由到缓存了对应 prefix 的实例（加速 prefill/decode）
2. **Load balancing**: 避免某些实例过载导致排队延迟

现有三类组合策略各有问题：

**线性组合** (BAILIAN，ai-Dynamo):
- `Score = λ × KV$indicator + (1-λ) × load_indicator`
- λ 需要 per-workload tuning，最优值随 workload 动态变化
- 静态 λ 是次优的

**Filter-based** (AIBrix):
- 先检查负载是否不均衡 → 是：纯负载均衡 → 否：纯 KV$ 优先
- 阈值需要 per-workload tuning
- 偏向负载均衡 → 放弃 KV$ 收益

**Simulation-based** (llm-d):
- 模拟每个实例的 TTFT → 路由到最低 TTFT 的实例
- 需要 per-model + per-hardware 的精确模拟器开发
- 即使 well-tuned 仍有 ~10% 请求误差 >20%

### 核心洞察
**乘法天然消去参数**。如果 `λ·KVi + (1−λ)·Li < λ·KVj + (1−λ)·Lj`（线性），则乘法 `KVi × Li < KVj × Lj` 保持相同的偏序关系，但乘法分数比较时 λ 被消去。由此 `Performance ∼ P-token × BS` 成为一个无需调参的统一调度分数。

### 我的分析
这是 OSDI '26 中唯一的一篇调度器/路由方向论文（其他四篇 KV cache 论文都是 I/O 和 kernel 优化）。方法论上非常优雅——通过对 LLM serving 特征的深入分析，将复杂的三类组合策略统一简化为一个乘法公式，并在数学上分析了失效边界条件。特别是 §5.2 中基于排队论的 KV$ hotspot 检测器，展示了从"简单方法能 work"到"什么条件下会 fail"的完整思考链。

## 方案介绍

### 核心调度公式

```
Score(i) = P-token_i × BS_i
Route_to = argmin_i Score(i)
```

其中：
- **P-token_i**: `len(prompt) − KV$.hit_len(request.prompt)` — 如果路由到实例 i 需要新增的 prefill token 数
- **BS_i**: 实例 i 当前的 batch size（queued + running）

### 指标选择分析 (§5.1)

**KV$-awareness 指标**：为什么 P-token 优于 1-KV$ hit ratio？
- 1-KV$ hit ratio 只反映匹配比例，不反映实际节省的计算量
- P-token 额外考虑了每个实例的排队 prefill token 数 → 会绕过积压严重的实例
- 实验：P-token 优于 1-KV$ hit ratio by 14.4% P50 TTFT, 42.8% P95 TTFT

**Load-balancing 指标**：为什么 BS 优于 #Tokens？
- #Tokens 混合了 prefill 和 decode 负载
- Prefill 负载已被 P-token 覆盖 → 只需 BS 来衡量 decode 负载
- BS 更好地反映 decode time（decode time 与 BS 更稳定地成正比）

### 乘法失效分析 (§5.2)

**失效条件**（公式1）：
```
BS_hotspot / BS_other = (BS_0 + x·QPS·t/|M|) / (BS_0 + x̄·QPS·t/|M̄|) > 1
```

**简化边界条件**（公式2）：当 `x/x̄ > |M|/|M̄|` 时，可能发生 KV$ hotspot（某个 prefix 的请求数比例超过缓存该 prefix 的实例比例）

- x/x̄: 请求类 c 的相对流行度
- |M|/|M̄|: 缓存该类 prefix 的实例相对数量

**经验观察** (Figure 20)：在所有 4 条 trace 中，`x/x̄ ≤ |M|/|M̄|` 始终成立 → 乘法不会失效

**两阶段检测器**：
1. Phase 1：实时监控 `x/x̄ − |M|/|M̄|`，超过阈值则报警
2. Phase 2：在报警后，仅当热点实例连续 2|M| 个请求比非热点实例分数更低时才过滤它们 → 避免误报

## 评估

### 测试环境
- **硬件**: 16×H20 GPU (96GB), 160-core Xeon, 1TB DRAM
- **Router**: Rust indicator factory + 高性能 trace replayer
- **模型**: Qwen2-7B (dense), Qwen3-30B (MoE)
- **Instance engine**: vLLM-v1

### 负载 (4 条真实 trace)
| Trace | 类型 | 来源 |
|-------|------|------|
| ChatBot (Qwen) | 对话 | Alibaba 公开 |
| Agent (Qwen) | API 调用 agent | Alibaba 公开 |
| Coder | 编程 agent | BAILIAN 生产 |
| ToolAgent (Kimi) | Agent 服务 | Kimi 公开 |

### 关键结果

| 实验 | 结果 | 要点 |
|------|------|------|
| vs vLLM-v1 (ChatBot) | TTFT **-92%**, TPOT **-24%** | KV$-awareness 的巨大收益 |
| vs BAILIAN (生产) | TTFT **-39%**, TPOT **-51%** | 乘法优于手动调参的线性组合 |
| vs llm-d (simulation) | TTFT 相似，TPOT P99 **-13%** | 不需要复杂模拟器 |
| vs Dynamo (NVIDIA) | 全面领先 | 不需要 per-workload tuning |
| vs Preble (filter+linear) | 全面领先 | 不需要 threshold tuning |
| vs PolyServe (simulation SLO) | 更低的 mean/P99 | PolyServe 为 auto-scaling 牺牲 per-request 延迟 |
| 不同 request rate | 高负载下优势扩大 | 因为更好平衡 → 更高系统吞吐 |
| 生产 canary | 实际 1/3 流量运行 LMetric | Day-long deployment 验证有效 |

### 对比表（研究方法论对比）

| 系统 | 组合方式 | 是否需要调参 | 是否需要模拟器 | 性能 |
|------|---------|-------------|--------------|------|
| **LMetric** | **乘法** | **否** | **否** | **最优** |
| vLLM-v1 | 纯负载均衡 | 否 | 否 | 最差 |
| BAILIAN | 线性组合 | 是 (per-trace) | 否 | 中等 |
| Dynamo | 线性组合 | 是 (per-trace) | 否 | 中等 |
| AIBrix | Filter + 线性 | 是 (threshold) | 否 | 中等偏下 |
| llm-d | Simulation | 是 (per-model/hw) | 是 | 接近 LMetric (TPOT 差) |
| Preble | Filter + 线性 | 是 (threshold) | 否 | 接近 LMetric |
| PolyServe | Simulation SLO | 是 | 是 | 不同目标 (auto-scale) |

## 整体评估

### 真正的新意
1. **乘法替代线性组合的核心洞察**：在调度分数的场景中，乘法在比较时自然消去超参数 → 不需要任何 tuning。这是"Simple is Better"在 LLM serving 领域的一个优雅实例
2. **系统性的指标选择方法论**：不是简单的"试哪个指标 work"，而是通过分析 LLM serving 的 prefill/decode 二分特性，推导出 P-token 和 BS 是最优的指标组合
3. **失效条件的数学推导**：从排队论出发推导乘法可能失效的条件，并设计 runtime detector — 这让"simple method"变得可信（known failure mode, detectable, mitigatable）

### 优点
- **极简且高性能**：2 行伪代码（`min(P-token × BS)`）超越了所有需要复杂调参的方案
- **分析完整**：不仅提出了方法，还解释了为什么现有的三类策略都有问题，并推导了失效条件
- **生产验证**：已在阿里百炼数百 GPU 集群部署，canary release 确认效果
- **开源框架**：Rust indicator factory + trace replayer 为后续调度研究提供了公平对比平台
- **trace 开放**：4 条真实 LLM serving trace 对研究社区开源
- **优雅的背后是深入分析**：不是"偶然发现乘法 work"——作者先用四种 method 各自分析了缺点，再基于对 LLM 特征的深入理解选择了 P-token 和 BS

### 局限
1. **PD-colocation only**: 本文只聚焦 colocation 部署，虽在 §7 讨论了 PD-disaggregation 的扩展，但未实验验证
2. **仅支持前缀匹配缓存**: 没有考虑更复杂的 KV cache 共享（如语义相似的 cache fusion in CacheGen/CacheBlend）
3. **KV$ hotspot 检测器在生产中触发频率未知**: 论文仅在实验条件下复现了一个 hotspot case（thinking workload），生产中的触发频率没有数据
4. **P-token 是 prefill 负载的 proxy，不是精确模型**: 在某些模型/硬件组合中，prefill 时间可能不严格正比于 token 数
5. **router 吞吐**: 虽然用 Rust 实现了高性能 router，但对比的 vLLM Python router 本身就有已知 bug（AIBrix Go 重实现快 6.2×）

### 可复用启发

1. **"乘法消参"的数学洞察**: 当比较分数 `λ·A + (1-λ)·B` 的排序足以做决策时，乘法的排序列与线性组合等价，但消去了 λ。这个技巧可推广到任何"需要比较加权分数"的场景（如数据库查询优化器的 cost model、CDN 请求路由、微服务负载均衡）

2. **"理解 workload 的结构再做简化"**: 不是黑盒调参，而是先分析 LLM serving 的 prefill/decode 二分结构 → 发现两个指标分别覆盖两个阶段 → 乘法天然组合。这种方法论可推广到其他系统优化

3. **"失效条件的数学推导"让简单方法可信**: 不是只展示"it works empirically"，而是精确推导了何时会 fail，并设计了 runtime detector。这对任何提出"simple solution"的系统论文都是好模板

4. **Rust indicator factory 的组件化设计**: 将指标收集、policy 表达、trace replay 分离为独立组件 → 让不同 policy 可以在同一框架下公平对比。这是实验系统论文的基础设施建设思路

5. **"weight statically tuned"在动态负载下是次优的**: 这个观察在 scheduling 领域广泛成立 —— BAILIAN 的 λ=0.7 在不同 trace 的最优值可以差 0.15，足以让 P50 TTFT 差 44%。说明 tuning-dependent 方案在 LLM serving（多租户、workload 动态变化）场景下本质上不可靠

6. **"是简单还是过度简化"的边界**: 论文对 KV$ hotspot 的推导和分析回答了这个经典问题——乘法在 99%+ 的 case 下 work，并且知道了 1% 的边界条件。
