# System Testing & Debugging

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| CPU 调度器测试 | deterministic replay, coverage-guided fuzzing, semantic/policy bugs, scheduler characterization | kSTEP(OSDI'26) |
| 云服务 API 一致性测试 | model-based testing, predicate abstraction, reference model, differential testing, API conformance | S3 MBT(OSDI'26) |
| 合成可执行测试环境 | diffusion model, trace-to-workload synthesis, state-aware conditioning, execution-driven alignment, resource contention | Mimesys(OSDI'26) |
| LLM+规格生成式文件系统 | formal specification, LLM code generation, Hoare logic, rely-guarantee, spec-driven evolution, hallucination mitigation | SysSpec(FAST'26) |

---

## CPU 调度器确定性测试

### 核心问题
Linux 调度器极其复杂但测试严重不足：开发者依赖长期运行负载而非系统性 corner case 测试。对 232 个真实调度器 bug 的表征揭示 73% 是静默的（无 panic）、75% 是语义错误、45% 存活超过一年。

### 关键洞察

1. **"静默 bugs 是多数"**：仅 27% 自我报告（panic/warning），大多数调度器错误表现为无 trace 的 subtle 行为偏差
2. **确定性 + 隔离 = 可调试性**：单独隔离 CPU 不够（噪声还在），单独确定性不够（OS 复杂度不可控）→ 两者组合产生 noise-free traces
3. **Coverage-guided fuzzer 在 OS 内核调度器上可行**：传统认为是禁区（太慢、太复杂）
4. **"先表征问题域，再设计工具"的研究范式**：232 bug study → 12 findings → 工具设计
- 来源：kSTEP(OSDI'26)

### 实践启发
- 表征研究本身有独立价值：定量了解"bug 到底长什么样"是工具设计的前提
- 静默 bugs（silent semantic faults）是内核子系统中被最严重低估的问题
- Coverage-guided fuzzing 与确定性重放的组合是测试复杂状态系统（尤其是 OS 内核）的通用模式

---

## 云服务 API 一致性测试 (S3 Model-Based Testing)

### 核心问题
Amazon S3 已运行 20 年，500 万亿对象，200M+ 请求/秒。其 API 在二十年中被多次重实现（不同代码库、语言、硬件）——如 S3 Express One Zone 是全新实现的存储类。但**客户代码依赖于 API 的每一个可观察行为**（不仅 success response，还有每种 error response 的精确语义）。如何确保一个拥有 96 个 API、单 GetObject 就有 21 个参数和 ≥10^25 种参数-状态组合的服务，在每次代码变更后行为保持一致？

### 关键洞察

1. **"可执行参考模型 > 文档规范"**：API 有多个有效响应时（如不同分页顺序、errors 的不同报告顺序），两个正确实现在相同具体输入下可能输出不同。只有封装**所有允许行为**的可执行模型才能作为测试 oracle。S3 Express One Zone 开发者用 model 在实现前就验证了一致性。
2. **"谓词抽象将 10^25 缩减到可管理"**：将具体参数和状态 lift 到抽象谓词（如 "object 是否由 multi-part upload 创建"），在抽象空间系统中探索——覆盖所有语义类别而非所有具体组合。
3. **"模型状态知识驱动输入生成"**：不同于随机 fuzzing，MBT 利用 model 的状态知识，有意将 model 驱动到深层边界 pre-state→生成针对性输入→覆盖 non-obvious paths。

- 来源：S3 Model-Based Testing(OSDI'26)

### 实践启发
- **"可执行规范"对长生命周期 API 是不可替代的**：当 API 有多个共存实现时，只有可执行模型能作为 authoritative oracle——文档无法覆盖所有 corner case
- **"谓词抽象是状态空间爆炸的通用解法"**：不仅适用于 API 测试——任何大状态空间的系统测试都可以用抽象谓词替代具体参数枚举
- **"300+ 阻止的回归"是测试方法质量的 hard metric**：比代码覆盖率更直接

---

## 合成可执行测试环境 (Mimesys)

### 核心问题
测试应用在真实资源争抢下的行为需要生产 workload——但因隐私/产权/IP 保护无法获取。现有替代方案：(1) 简单 resource stressor（如 stress-ng）无法捕获时间动态和多资源交互 (2) benchmark suite 覆盖有限且难以推广 (3) per-application profiling 太昂贵无法规模化。能否**从资源使用 trace 反向合成可执行 workload**？

### 关键洞察

1. **"Diffusion model 学习 trace→stressor composition 的逆映射"**：不是合成 trace（已有方式可以做），而是合成能生成这些 trace 的可执行 workload。这是从 trace 到程序的 infer——比 trace 生成难得多。扩散模型在这里特别合适——其去噪过程本质上就是逐步细化 stressor 组合。
2. **"State-aware conditioning 捕获时间动态"**：生成以目标 trace + 先前系统状态为条件→捕获跨时间步的依赖关系。不是生成单个点的资源使用，而是生成符合系统状态转移的序列——类似 Kairox "Temporal Activation Momentum" 但应用于 trace 合成。
3. **"Execution-driven alignment——用反馈替代 ground-truth labels"**：没有 "正确 stressor 组合" 的标注数据→直接执行生成的 workload→测量实际 trace→与目标 trace 比较→反馈修正模型。类似 RLHF 但应用于 workload synthesis。

- 来源：Mimesys(OSDI'26)

### 实践启发
- **"Diffusion for inverse mapping"是比正向生成更难但更实用的方向**：trace→workload mapping 不需真实应用的代码/数据→保护隐私同时提供可执行测试环境
- **"Execution feedback as training signal"**：当没有 ground-truth 标签时，直接执行并测量可以替代标注。类似 AEGIS "cSensor-cVerifier——执行重放验证 SDC" 的思路：执行本身就是最好的验证

---

## LLM+规格生成式文件系统 (SysSpec)

### 核心问题
FS 开发陷入恶性循环：Ext4 自 inception 以来 3157 commits 中 **82.4%** 是 bug fix/maintenance，仅 5.1% 是新功能。1 个新功能(如 fast commits→9 commits)触发 ~80 个后续 bug fix。LLM 生成 FS 的三大障碍：(1) NL prompt 无法精确表达并发正确性/磁盘布局/不变量；(2) LLM context window 有限→模块化生成→接口兼容+跨模块变更复杂；(3) LLM 幻觉→"生成即祈祷"对系统软件不可接受。

### 关键洞察

1. **"用形式化方法风格的多维规格取代自然语言 Prompt"**：Hoare-logic pre/post-conditions + invariants (Functionality) + Rely-guarantee interfaces (Modularity) + explicit locking protocol (Concurrency)→精确且机器可理解。类比系统软件从"写代码"到"写 TLA+"的路径。

2. **"两阶段生成——先逻辑后并发"**：SpecCompiler 先生成功能正确但无并发的版本→再加入细粒度锁。LLM 同时处理 functional logic + fine-grained locking 会被淹没→逐步细化类似人类开发者 workflow。

3. **"SpecValidator = 验证-反馈-重试闭环→自主纠错"**：不是一次性 gate→生成代码→对照 spec 验证→不匹配→反馈→重试→循环直到通过。类似代码审查的迭代过程。

4. **"Spec patch (DAG-structured) = 保证 invariant preservation 的演进"**：不直接改 C 代码→改 specification→toolchain 重新生成。DAG 结构确保新特性不破坏已有 invariants→类比形式化验证中的 refinement proof。

- 来源：SysSpec(FAST'26)

### 实践启发
- **"Specification as source of truth——代码是从 spec 生成的衍生物"**：不再 manual coding→spec 是唯一权威来源→所有变更从 spec 开始。这是"single source of truth"在系统软件中的极致应用
- **"验证+反馈 loop = 对抗 LLM 幻觉的系统性方案"**：不寄望于一次生成正确→依靠 spec 和自动验证形成持续纠错闭环。类似编译器优化中"生成→验证→修正"的 superoptimization 思路
- **"先逻辑后并发 = 复杂度分离的通用策略"**：不仅适用于 LLM 代码生成→人类开发者也应从正确串行版本出发再引入并发
