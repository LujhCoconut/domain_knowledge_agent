# Program Analysis & Dynamic Optimization

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 推测性乱序执行 (Shell) | speculative execution, dynamic effect capture, syscall tracing, out-of-order, conditional commit | hS(OSDI'26) |
| 自动增量重新执行 (Shell) | bolt-on incrementalization, effect tracing, memoization, dependency inference, non-idempotent safety | Incr(OSDI'26) |

---

## 推测性 Shell 脚本乱序执行

### 核心问题
Shell 脚本无处不在，但现有加速工具依赖手动标注每个命令的并行性和副作用——只有 Coreutils 等受祝福的命令有标注，大量 domain-specific binaries 无法被优化。此外，现有工具严格保序，无法跨越控制流 barrier（`;`, `if`）做并行化。

### 关键洞察

1. **"动态发现 > 静态声明"**：当覆盖所有可能的程序行为不现实时，运行时 syscall tracing 自动捕获文件系统依赖和副作用，替代手工 annotation
2. **推测执行 + 条件提交**：借鉴 CPU 乱序执行——推测性地并行执行脚本区域 → 追踪读写集 → 无冲突就提交，有冲突就回滚
3. **Subprocess 粒度**是合适的执行单元：简单命令、管道或小同步区域，而非单个 OS process
- 来源：hS(OSDI'26)

### 实践启发
- syscall tracing 不仅是安全/调试工具——也可以是性能优化工具
- 推测执行思想可以远远超出 CPU 微架构，在 shell、workflow orchestration、CI/CD pipeline 等场景都有应用前景
- "不要求用户标注"是工具被广泛采用的必要条件

---

## 自动增量重新执行 (Shell)

### 核心问题
软件开发是增量的，但每次修改后执行环境要求**完全重新运行**所有计算阶段——即使是单个标志的微小修改。在大型数据集（数据科学、ML pipeline、探索性计算）上，这样的完整重新执行可能需要数分钟到数小时。make/ninja 需要手动声明依赖，在动态 shell 环境中不可行。

### 关键洞察

1. **"bolt-on incrementalization"**：外挂式增量——首次执行追踪依赖并缓存中间结果 → 后续执行检测修改 → 复用未改变的缓存
2. **动态推断依赖 > 手动声明**：Incr 在首次执行时通过 effect tracing 自动推断命令间的数据流依赖，替代 make 的显式规则
3. **非幂等操作的正确处理**：effect analysis 判断哪些操作必须因修改而重新执行，而非简单地跳过未改变的命令
4. **行为不可区分**：增量执行结果与完整重新执行在 10,000+ 测试用例上完全等价
- 来源：Incr(OSDI'26)

### 实践启发
- "bolt-on"外挂设计是低 adoption barrier 的关键：不修改用户程序、不要求 annotation
- 增量执行的核心是依赖推断的质量——动态 effect tracing 比静态分析更适合动态语言
- 34.2× 的平均加速表明："修改一小部分 → 完全重跑" 的模式在现实中造成了巨大的浪费

### Brown Shell Lab 三部曲

| 论文 | 维度 | 加速 |
|------|------|------|
| **try/semisolates(OSDI'26)** | 安全性：预览 effects 并选择性地 apply/revert | — |
| **hS(OSDI'26)** | 并行性：推测性乱序执行 | 9.3× vs bash |
| **Incr(OSDI'26)** | 增量性：缓存中间结果、复用未改变的部分 | **34.2× avg, 373.3× max** |

三部曲完整覆盖 Shell 执行优化的三个维度，共享同一个核心哲学：**动态 tracing 替代静态 annotation，外挂式工具不侵入用户程序**。
