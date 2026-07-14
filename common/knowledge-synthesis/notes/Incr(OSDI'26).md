# Incr(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-xie-yizheng.pdf
- **全称**: Incr: Faster Re-execution via Bolt-on Incrementalization
- **作者**: Yizheng Xie*, Evangelos Lamprou*, Jerry Xia*, Nikos Vasilakis (Brown University) — 与 try/semisolates、hS 同组
- **类型**: 论文-系统 (程序分析 + dynamical optimization + shell)
- **一句话 TL;DR**: 软件开发是增量的，但执行不是——每次修改后完整重新运行所有阶段。Incr 通过**自动增量化**加速 shell 程序的重新执行：分析并追踪依赖关系，缓存关键中间结果，在后续重新执行时检测修改并复用未改变的部分。平均加速 **34.2×**，最大 **373.3×**，无需 annotation、无需代码修改，在 10,000+ 测试用例上行为等价。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **Incr** | Bolt-on Incrementalization — "外挂式"增量执行系统 |
| **Bolt-on** | "螺栓式"——挂在无修改的执行环境上，不需改变 shell 或用户程序 |
| **Incrementalization** | 将完整执行转换为增量执行：仅重新计算因修改而受影响的部分 |
| **Effect analysis** | 分析命令的文件系统副作用（读/写/依赖），支持正确增量执行，**包括非幂等操作** |
| **Memoization & Reuse** | 缓存第一次执行的中间结果 → 后续执行时检测修改 → 复用未改变的缓存 |
| **Observation probes** | 运行时探头：追踪文件系统 effects 和依赖以进行增量化决策 |
| **Eager streaming** | 尽可能早地流式输出缓存结果，减少等待延迟 |
| **Storage compaction** | 压缩缓存存储以减少磁盘/内存开销 |

## 背景与动机

### 问题
- 软件开发的循环"修改→测试→调试"频繁触发**完整重新执行**——即使是微小修改
- 在大型数据集上运行的数据科学/ML/探索性计算 pipeline 每次重新执行需要数分钟到数小时
- 现有的增量构建系统（如 make）要求**显式依赖声明**——在动态脚本环境中不切实际
- "即使是微小的修改也可能导致漫长的等待周期"

### 为什么现有方案不够
- make/ninja: 要求手动声明文件级依赖和构建目标——shell 脚本不适用
- 缓存（如 ccache）：只能缓存单个命令的输出——不理解 shell pipeline 的依赖链
- 完全重跑：浪费时间但保证正确性

## 方案介绍

### 两阶段执行

**Phase 1: Analysis (第一次执行)**
1. **Isolated Effect Tracing**: 追踪每个命令的文件系统读/写/依赖
2. **Dependency Inference**: 推断命令间的数据依赖关系（输出→输入链）
3. **Observation Probes**: 在关键中间点插入探头，记录中间结果

**Phase 2: Incrementalization (后续执行)**
1. 检测自上次执行以来哪些部分发生了修改（新增/删除/原地修改）
2. **Memoization & Reuse**: 从缓存中复用受影响最小的中间结果
3. **Effect analysis** 确保非幂等操作的正确重新执行
4. **Eager streaming**: 在分析完依赖后尽快流式输出缓存结果

### 关键特性

- **支持完整的 POSIX 和 Bash 语义**：包括命令参数、标志、数据流、控制流、环境变量、外部文件的修改
- **行为不可区分**：在 10,000+ 测试用例上增量执行结果与完整重新执行**完全等价**
- **非幂等操作安全**：通过 effect analysis 确保非幂等操作在修改后的正确性
- **外挂式（bolt-on）**：不需要修改用户的 shell 程序、不需要 annotation
- **可关闭**：开发完成后可以禁用（零 overhead），准备部署时不影响性能

## 证据与评估

| 指标 | 结果 |
|------|------|
| 平均加速 | **34.2×** |
| 最大加速 | **373.3×** |
| 测试用例 | **10,000+**（全部行为等价） |
| 开发者参与 | **零**（无需 annotation） |
| 应用场景 | 数据科学、ML pipeline、探索性计算、LLM 交互脚本 |

## 整体评估

### 真正的新意
1. **首次将自动增量化引入 shell 环境**：make-like 的增量构建在 shell 中从不可用（因为需要手动声明依赖），Incr 通过动态追踪自动推断依赖
2. **"Bolt-on"设计哲学**：与同一实验室的 try（transparent preview）和 hS（speculative parallelism）共享——**不修改用户的程序，不要求 annotation**
3. **处理非幂等操作**：不是简单地跳过"未改变的命令"——Incr 的 effect analysis 能判断一个操作是否应该因修改而重新执行

### Brown Shell Lab 三部曲

| 论文 | 功能 | 加速 |
|------|------|------|
| **try/semisolates** | 预览 filesystem effects，选择性地 apply/revert | —（安全） |
| **hS** | 推测性乱序并行执行 | 9.3× vs bash |
| **Incr** | 增量重新执行（缓存+复用未改变的结果） | **34.2× avg, 373.3× max** |

三部曲完整覆盖 Shell 执行优化的三个维度：安全性（try）、并行性（hS）、增量性（Incr）。

### 可复用启发
- "bolt-on"设计：外挂式工具不需要修改目标系统——这是低 adoption barrier 的关键
- 动态推断依赖 > 手动声明依赖：make 的显式依赖模型不适合动态、探索性的开发场景
- 非幂等操作的 effect analysis 是增量执行的正确性关键
