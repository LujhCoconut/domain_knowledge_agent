# Agent-Native Software Design

软件框架/系统的设计方法论：将 AI coding agent 的理解、操作和扩展效率作为第一等优化目标。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| Agent-Native 设计四原则 | compact codebase, Python-native, no implicit indirection, agent skills, ATE | PithTrain(arXiv'26) |
| Agent-Task Efficiency (ATE) 度量 | agent turns, output tokens, active GPU time, per-turn context, session duration | PithTrain(arXiv'26) |
| ATE-Bench 反向评估 | fixed-agent variable-framework, Q&A, operate/profile, new feature | PithTrain(arXiv'26) |

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
