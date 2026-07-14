# UCSan(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-yin.pdf
- **全称**: A Compilation-based Under-Constrained Execution Engine
- **系统名**: UCSan (Under-Constrained Sanitizer)
- **作者**: Mingjun Yin, Zhaorui Li, Ju Chen, Haochen Zeng, Chengyu Song (UC Riverside)
- **类型**: 论文-系统 (program analysis + software testing + compiler)
- **一句话 TL;DR**: 静态分析覆盖全但误报多（如 Linux 内核 use-before-init 分析器 147,643 警告中仅 52 个被确认），动态测试精确但需要**良好的 testing harness 和复杂的环境搭建**。UCSan 是一个**基于编译的 under-constrained 执行引擎**——可以将任意 C/C++ 函数集编译为独立可执行文件，无需手动修改代码，即可在隔离环境中应用动态分析（符号执行、fuzzing 等）。与基于解释器的方法（KLEE）相比，在 Linux 内核分析上快 **15.06×**。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **Under-constrained execution** | 不完全约束执行——提取函数的子集，在无完整程序上下文（无完整初始化、无环境）的情况下执行 |
| **UCSan** | 基于编译的 under-constrained sanitizer——在 LLVM sanitizer 框架上实现，在编译时 instrument 内存访问 |
| **Testing harness problem** | 动态测试的根本限制：如果 bug 不能从 harness 触达，就找不出来——无论投入多少 fuzzing 资源 |
| **Environmental setup problem** | 动态测试的第二个瓶颈：测试内核需要 VM、文件系统需要磁盘镜像、驱动需要真实硬件或仿真器 |
| **KLEE** | 基于解释器的符号执行引擎（KLEE 基于 LLVM IR 解释器） | 对比 baseline |
| **Concolic execution** | 具体+符号混合执行 | UCSan 与 compilation-based concolic engine 结合的场景 |

## 背景与动机

### 动态测试需要"使任意代码子集可独立执行"

- OSS-Fuzz 已发现 36,000+ bugs, syzbot 修复了 6,500+ Linux 内核 bugs
- 但这些工具的**根本限制**不变：如果 bug 不能从 harness 触达就无法发现
- **环境搭建**也是巨大障碍：内核测试→VM、文件系统→磁盘镜像、驱动→真实硬件或仿真器（经常不存在）
- 静态分析虽能覆盖全量代码，但在复杂系统（如 OS 内核）中产生大量误报（147,643 警告→仅 52 个真 bug）

### 为什么现有 under-constrained execution 引擎不够

现有的 under-constrained execution 引擎（如 KLEE）**全部基于解释器**，在高规模代码（如内核函数提取）上性能极差。

## 方案介绍

### UCSan 核心设计

**两个目标**:
1. 将 under-constrained execution 与符号执行**解耦**——UCSan 可作为多种动态分析技术的通用底座（concolic execution, fuzzing, model checking）
2. 基于编译器（LLVM sanitizer 框架）实现，通用、易集成、高性能

**两个核心挑战和解决方案**:

**Challenge 1: 内存初始化**
- 全局/栈变量：已有编译器工具链处理
- **堆对象**：通常运行时动态分配/初始化 → 当跳过正常初始化过程（如内核启动）直接执行任意内部函数时，需要一种方法为代码预期的堆对象分配和初始化
- UCSan 通过编译时 transformations + runtime support 自动处理

**Challenge 2: 外部依赖**
- 从复杂软件系统中提取任意代码集时，代码很可能调用外部依赖
- UCSan 的 instrument 机制自动处理内存访问，使未初始化的指针指向合适的 offset

### 技术实现
- 基于 LLVM sanitizer framework 的 instrumentation pass
- 对所有内存访问 instrument → 自动处理未初始化内存和外部依赖的指针
- 与 compilation-based concolic execution engine 结合进行 under-constrained symbolic execution

## 证据与评估

| 指标 | 结果 |
|------|------|
| vs KLEE (Linux 内核分析) | **最高 15.06× 更快** |
| 背景 | OSS-Fuzz: 10,000+ 安全漏洞 / 36,000+ bugs; syzbot: 6,500+ 内核 bugs |
| 误报案例 | use-before-init 静态检查器: 147,643 警告→仅 52 个被确认/修复 |

## 整体评估

### 真正的新意
1. **首个编译-based 的 under-constrained execution engine**：之前所有此类引擎（KLEE 等）都是解释器-based → UCSan 用编译器优化 native code 替代解释执行 → 大幅性能提升
2. **将 under-constrained execution 从符号执行解耦**：作为通用底座适用于多种动态分析技术（concolic, fuzzing, model checking）

### 可复用启发
- "从提取代码到独立可执行"的编译流程是消除 testing harness 瓶颈的通用方案
- Under-constrained execution 补足了静态分析的高误报和动态测试的高门槛之间的空白
- LLVM sanitizer 框架作为 instrumentation 基础设施的灵活性：不仅是 sanitizer（ASan/UBSan），还可构建执行引擎
