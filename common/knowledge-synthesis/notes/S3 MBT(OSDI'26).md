# S3 Model-Based Testing(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-jaber.pdf
- **类型**: 论文-运维系统 (Operational Systems)
- **一句话 TL;DR**: AWS S3 用可执行参考模型 + 谓词抽象 + 系统化输入生成做 API 一致性验证，阻止 300+ 回归，指导 S3 Express One Zone 开发。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| API sameness / conformance | API 行为在代码重构、重实现、新存储类之间保持一致 | 核心目标——S3 20 年演进，多实现共存 |
| Executable reference model | 用代码编写的 API 行为规范——可以执行而非文档 | 作为 de facto specification——开发和工具可直接使用 |
| Predicate abstraction | 将具体请求参数和状态 lift 到抽象谓词——极大缩小 state space | 关键使能——GetObject 有 21 个参数，10^25 种组合 |
| Model-Based Testing (MBT) | 用 model 作为 oracle 驱动输入生成的测试范式 | 本文的核心方法论 |
| Differential testing | 对比 model 和 SUT（System Under Test）的输出→发现差异 | 回归检测机制 |

## 背景

Amazon S3 20 年历史，500 万亿对象，200M+ 请求/秒。API 多次重实现（不同代码库/语言/硬件）。核心挑战：**API 行为必须一致**，即使底层完全重写。

GetObject 例子：21 个输入参数，36 个输出参数，桶配置（加密/版本/访问策略）影响行为。仅 GetObject 的不同参数组合 ≥ 10^25。

## 方案

1. **可执行参考模型**：用代码写规范→可被开发者和工具直接使用→在 CI/CD 中运行
2. **谓词抽象**：将具体参数/状态 lift 到抽象空间→将 10^25 状态缩减到可管理
3. **系统化输入生成**：从 model 状态知识生成输入→驱动到深层边界路径
4. **差分测试**：model vs SUT→差异 = 潜在回归

## 关键结果

- **阻止 300+ 回归**在到达生产前
- **指导 S3 Express One Zone 开发**：model 在实现前就有→作为设计参考
- CI/CD 集成：在单元测试和集成测试之后运行

## 可复用启发
- **"可执行模型 > 文档规范"**：API 有多个有效响应时（如不同分页顺序），两个正确实现在相同输入下可能输出不同→只有封装所有允许行为的模型才能做 oracle
- **"谓词抽象是测试大型状态空间的实用方法"**：不需要测试所有具体参数组合→lift 到抽象谓词→覆盖所有语义类别
- **"Regression prevention 的数量是衡量质量的好 metric"**：300+ 阻止的回归比任何覆盖率数字更有说服力
- 来源：S3 Model-Based Testing(OSDI'26)
