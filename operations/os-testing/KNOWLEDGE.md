# System Testing & Debugging

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| CPU 调度器测试 | deterministic replay, coverage-guided fuzzing, semantic/policy bugs, scheduler characterization | kSTEP(OSDI'26) |
| 云服务 API 一致性测试 | model-based testing, predicate abstraction, reference model, differential testing, API conformance | S3 MBT(OSDI'26) |

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
