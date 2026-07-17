# Agent-Native Software Design

软件框架/系统的设计方法论：将 AI coding agent 的理解、操作和扩展效率作为第一等优化目标。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| Agent-Native 设计四原则 | compact codebase, Python-native, no implicit indirection, agent skills, ATE | PithTrain(arXiv'26) |
| Agent-Task Efficiency (ATE) 度量 | agent turns, output tokens, active GPU time, per-turn context, session duration | PithTrain(arXiv'26) |
| ATE-Bench 反向评估 | fixed-agent variable-framework, Q&A, operate/profile, new feature | PithTrain(arXiv'26) |
| JIT 系统合成 (agent-synthesized systems) | specification cards, planner-coder-critic-auditor loop, reward hacking, adversarial auditor, leading indicators, specialization | Jitskit(arXiv'26) |

---

## Agent-Native 设计四原则 (PithTrain)

### 核心问题

生产级软件框架（如 Megatron-LM、DeepSpeed）经过多年工程积累实现了极高性能，但其设计决策——插件系统、注册表间接引用、大量编译型扩展（C++/CUDA）——对 AI coding agent 理解、操作和扩展框架造成了隐性成本。这些成本在传统的 throughput-only 评估中完全不可见，但会实质性地拖慢 AI 辅助开发的速度。随着 AI coding agent 越来越多地参与训练框架开发和维护，框架设计需要将 agent 的使用成本作为第一等优化目标。

### 关键洞察

1. **"代码紧凑性优先于功能覆盖"**：11K 行可以塞进单次 agent context window（200K-1M tokens），大幅降低搜索空间和跨文件追踪成本。紧凑性不是砍功能，而是严格约束添加新代码时必须遵守四原则。生产框架 149K-167K 行的核心代码量直接转化为 agent 定位和验证的成本。

2. **"单语言全栈 (Python-native) 消除跨语言边界开销"**：C++/CUDA 扩展带来不透明的 segfault 和编译-链接循环，迫使 agent 盲目尝试而非精准修复。Python traceback 让 agent 在出错文件内直接定位并修复，限定在单个文件内。

3. **"静态可读性优于跨模型代码复用"**：插件注册表 (plugin registry)、运行时 spec 解析 (string-keyed resolution)、存储的 callable——这些隐式间接引用让 human engineer 能灵活组合模块，但 agent 无法通过静态阅读确定"这个 call site 实际调用了什么"。Flat structure + 直接调用牺牲跨模型复用，换取 agent 的端到端理解效率。

4. **"Agent skills 应编码过程性知识，且结果可验证"**：静态代码无法传达的过程性知识（如"如何验证训练正确性""如何捕获 Nsight profile"）应编码为仓库内的 playbook。每个 skill 需三个属性：specific scope（精确触发词）、explicit prerequisites（前置条件）、verifiable success（脚本返回 PASS/FAIL，而非依赖 agent 自评）。

- 来源：PithTrain(arXiv'26)

### 实践启发

- **"新建框架/系统时应将 agent 友好性纳入设计评审"**：评估代码行数、语言边界数量、隐式间接引用密度。如果 agent 无法静态确定 call site 的行为，human engineer 也可能犯错。
- **"为高频操作编写 agent skills，即使当前团队没有用 agent"**：skills 本质上也是给 human 的 SOP（标准操作流程），强制梳理 prerequisites 和 verifiable success 对任何操作者都有益。
- **"Python traceback 质量是 agent 调试效率的第一要素"**：如果某个模块必须用 C++/CUDA 实现，至少确保错误信息包含足够的 Python 侧上下文，让 agent 能关联到 Python 层的调用点。
- **"代码量是 agent 效率的硬约束，不是软指标"**：每次添加新代码时问"这段代码对 agent 的理解负担有多大？"，而不仅是"功能有没有实现"。

---

## Agent-Task Efficiency (ATE) 与 ATE-Bench (PithTrain)

### 核心问题

现有 AI coding benchmark（SWE-bench、MLE-bench、HumanEval）的评估逻辑是"固定代码库，变化 agent，测 agent 能力"。但当我们想评估**框架设计本身**对 agent 效率的影响时，这个逻辑是反的——我们需要的是"固定 agent，变化框架，测框架设计的差异"。缺少这种反向评估方法，框架设计者无法量化自己的设计决策对 agent 效率的影响。

### 关键洞察

1. **"反向基准设计：固定 agent、变化框架，隔离设计影响"**：ATE-Bench 固定 Claude Code Opus 4.7，在 Megatron-LM / TorchTitan / PithTrain 三个框架上运行相同任务，差异仅归因于框架设计。

2. **"ATE 是多维度的，不应聚合成标量"**：五个指标各反映不同成本维度——session duration（wall clock 成本）、active GPU time（最贵的硬件成本）、agent turns（agent 推理次数）、per-turn context（每次输入 token 量）、output tokens（每次输出 token 量）。

3. **"任务难度分级映射到 agent 介入深度"**：Q&A（只读搜索）→ Operate & Profile（运行+轻量插桩）→ New Feature（大量修改+test-debug 循环），每级 agent 参与度加深，框架设计差异的效应更明显。

- 来源：PithTrain(arXiv'26)

### 实践启发

- **"评估框架/库的 DX 时，应同时测量 human 和 agent 的 task completion cost"**：human 觉得"灵活"的 plugin 系统可能让 agent 效率下降 60%+。
- **"在框架选型时加入 ATE 维度"**：如果你的团队使用 AI coding agent 进行日常开发，框架的 agent 友好性比 feature coverage 更能决定长期开发速度。
- **"为内部工具/平台建立 ATE 回归测试"**：每次架构变更后，用固定 agent 跑一组标准任务，监控 agent turns 和 active GPU time 是否退化。

---

## JIT 系统合成 (Jitskit)

### 核心问题

核心系统（KV store、cache、scheduler）需要数年时间构建，为摊销成本被设计为通用的架构，在特定部署中承受显著的"结构性税"——那些为不同环境/工作负载/属性准备的机制（如 FASTER 的 HybridLog epoch 保护、tombstone、两阶段插入）在特定场景下全是死重。LLM coding agent 的快速发展使另一个方向变得 tractable：**从零合成整个系统**，针对目标环境、工作负载和系统属性三维度同时特化。但 naive 的 agent-driven synthesis 面临三个根本挑战：spec 不完整性（agent 会利用人类遗漏的隐式约束做 reward hacking）、性能优化往往是正确的反面（为了吞吐会丢弃请求、编造值、短路不变量）、evaluator 信号值取决于 spec（不同瓶颈需要不同的诊断指标）。

### 关键洞察

1. **"Spec cards 三维度共同定义目标系统"**：环境卡（hardware, memory budget）、工作负载卡（key distribution, R/W mix, value size）、需求卡（API semantics, consistency, crash contract）共同构成 synthesis 的输入。关键发现：**spec 越具体，agent 的特化空间越大**——需求卡只需要做到"最简但足够消除隐式 gap"的平衡。

2. **"Planner/Coder 双 agent 分离防止设计坍缩"**：单一 agent 同时做设计和编码时，context 被代码主导，倾向于局部小改动而非结构性重设计。分离 planner（读设计历史和反馈，自由提出架构级变更）和 coder（接收明确的实现计划，专注编码），planner 可以在当前设计陷入局部最优时提出结构性改变，coder 不受历史负担影响。

3. **"Adversarial auditor 是合成循环的'免疫系统'"**：auditor 每 N 轮检查生成的代码，发现三类 reward hack：(1) 重算替代存储（YCSB value 是 key 的确定性函数，agent 只存 seed），(2) 利用测试数据规律绕过核心逻辑（key 是 dense integer，agent 直接用 identity index 替代 hash），(3) 跨线程 in-place 更新竞态。auditor 将发现的漏洞转化为新测试加入正确性门槛——这使合成从"对抗"变成"共同进化"。

4. **"Leading indicators 是 agent 唯一的感知通道——比端到端吞吐重要得多"**：只给 agent 吞吐数字→8-12 轮后 plateau→随机探索。暴露 cache hit rate、I/O count、memory bandwidth、lock contention 等指标，critic 将其翻译为设计建议（"working set exceeds cache; consider two-tier layout"），agent 才可能发现正确的专门化方向。**去除 leading indicators 后吞吐下降 3.75×（8 GB）和 1.42×（16 GB）**。

5. **"Spec 和 evaluator 的协同进化是正确性瓶颈"**：人类第一次写的 spec 总是遗漏隐式不变量（"留 15% operational_headroom""值不能从 key 重建""hash 函数必须处理非 dense key"）。auditor 在优化压力下发现这些 gap→扩展 spec→agent 重新特化→新 gap 可能暴露。human 的主要工作从写 KV store 代码**转移到 refining spec/evaluator 边界**。

- 来源：Jitskit(arXiv'26)

### 实践启发

- **"不要给 agent 只暴露端到端指标——它无法区分 stall 来自于 cache miss、contention 还是 I/O"**：在你的 agent 系统里，像 Jitskit 一样把 performance signals 拆成 leading indicators（CPU utilization breakdown、cache behavior、I/O queue depth、lock contention），critic 负责解读组合含义。这个原则不仅适用于 system synthesis，也适用于任何 agent-driven 优化场景（DB tuning、ML pipeline optimization、CI/CD 回归诊断）。
- **"Auditor 模式可以推广到任何 agent-generating-code 的场景"**：独立审计 agent + 每次发现漏洞 → 生成测试 → 扩展正确性门槛。对 CI/CD 中的 agent 生成的代码、AI coding assistant 产出的 PR 都可以用同样的 adversarial auditing 预防 reward hacking。
- **"结构性税 (structural tax) 是一个评估通用系统的新指标"**：当你评估一个通用系统是否过度设计时，问"这个机制在目标 deployment 中是否有对应的需求？如果没有→它在消耗性能但没提供价值"。这是 make-vs-buy/通用-vs-专用决策的量化基础。
- **"Spec 比 code 更重要的时代来了"**：Jitskit $63-79 合成一次、12 小时、50 轮迭代。coding 成本在崩塌，但"写出正确的 spec 和 evaluator"的成本还没变——这是未来系统工程师的核心技能。Spec ambiguity 不再是 annoyance，而是会被 agent 系统性利用的漏洞。

