# Program Analysis & Dynamic Optimization

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 推测性乱序执行 (Shell) | speculative execution, dynamic effect capture, syscall tracing, out-of-order, conditional commit | hS(OSDI'26) |

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
