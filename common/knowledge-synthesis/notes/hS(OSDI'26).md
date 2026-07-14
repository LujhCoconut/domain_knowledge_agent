# hS(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-liargkovas.pdf
- **全称**: hS: Speculative Script Reordering at Subprocess Granularity
- **作者**: Georgios Liargkovas* (Brown→Columbia), Di Jin* (Brown), Tianyu (Ezri) Zhu (Stevens), Dan Liu (Stevens), A. Bolun Thompson (UCLA), Anirudh Narsipur, Seong-Heon Jung, Siddhartha Prasad (Brown), Diomidis Spinellis (AUEB & TU Delft), Michael Greenberg (Stevens), Konstantinos Kallas (UCLA), Nikos Vasilakis (Brown)
- **类型**: 论文-系统 (程序分析 + 运行时优化)
- **一句话 TL;DR**: 现有 shell 脚本优化工具（PaSh/POSH）要求**手动标注**每个命令的并行性和副作用——但现实中有无数未标注的 arbitrary binaries。hS 通过**动态 syscall tracing 捕获每个 subprocess 的文件系统依赖和副作用**，推测性地乱序执行脚本区域，在检测到冲突时回滚，无需任何标注或开发者参与。vs bash **9.3×** 加速，vs PaSh **7×** 加速。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **hS** | 推测性 shell 脚本乱序执行系统 |
| **Subprocess granularity** | 以简单命令、管道或小同步区域为粒度的执行单元（非单个 Unix process） |
| **Dynamic effect capture** | 通过 syscall tracing 在运行时自动捕获每个 subprocess 的文件系统读/写/依赖 |
| **Speculative commit** | 推测性执行→检查冲突→无冲突则提交，有冲突则回滚 |
| **PaSh / POSH** | 现有工具：需要 crowdsourced 或 baked-in 的 command annotations → 仅覆盖 Coreutils 等受祝福的命令集 |
| **Out-of-order shell execution** | 类似 CPU 乱序执行的思想：重新排列 shell 命令执行顺序，动态追踪依赖保证语义不变 |

## 背景与动机

### 问题
- Shell 脚本作为粘合代码无处不在（top 10 编程语言，增长速度超 C/Python），用于生物信息学、数据分析、CI/CD
- 现有加速工具（PaSh、POSH）有两个根本局限：
  1. **依赖手动标注**：需要每个 command 的 annotation 描述其并行性/输入顺序/副作用 → 只有 Coreutils 等有标注，大量 domain-specific binaries 没有
  2. **严格保序**：仅做数据并行（不能跨越 `;` 和 `if` 等控制流 barrier）→ 错过了大量并行机会
- "有些脚本编译并运行自己的命令——指望那些命令被标注是不合理的"

### 核心洞察
不需要 annotation！运行时用 syscall tracing 动态观察每个 subprocess 的文件系统 effects → 推测性地乱序执行 → 无冲突就提交。

## 方案介绍

### 两个关键机制

**1. Dynamic effect capture via syscall tracing**
- 每个 subprocess 执行时，hS 通过系统调用追踪自动记录：
  - 文件系统 reads（依赖）
  - 文件系统 writes（副作用）
  - 网络访问（标记为 unsafe → blocking）
- 无需事先知道命令的行为

**2. Speculative out-of-order execution + conditional commit**
- 在脚本中识别可乱序的区域
- 推测性地并行执行 → 追踪每个 region 的读写集
- 无冲突（写集不重叠、不依赖对方的输出）→ commit
- 有冲突 → 回滚并按原始顺序重新执行

### 关键设计决策
- 执行单元是 **subprocess 粒度**（simple commands/pipelines/sync regions），而非单个 OS process
- 支持跨越控制流 barrier（`;`, `if`），比 PaSh/POSH 更激进
- 透明的：不修改脚本、不要求 annotation

## 证据与评估

| 指标 | 结果 |
|------|------|
| vs bash | **最高 9.3×** 加速 |
| vs PaSh | **最高 7×** 加速 |
| 开发者参与 | **零**（无需 annotation） |
| 覆盖范围 | 广泛的实际脚本（含 bioinformatics、analytics、CI/CD） |

## 整体评估

### 真正的新意
1. **首次将推测性乱序执行引入 shell**：传统 shell 工具严格保序，hS 借鉴 CPU 乱序执行的思路——推测执行→动态追踪依赖→条件提交
2. **用 syscall tracing 替代手工 annotation**：将程序分析从"事前声明"变为"运行时动态发现"——这是解决 arbitrary binary 覆盖问题的根本方案

### 可复用启发
- "动态发现 > 静态声明"：当覆盖所有可能的程序行为不现实时，运行时观测是更好的策略
- 推测执行 + 条件提交的模式不仅适用于 CPU 微架构——在 shell、workflow orchestration、CI/CD pipeline 等场景都有应用前景
- syscall tracing 不仅是安全/调试工具，也可以是性能优化工具
