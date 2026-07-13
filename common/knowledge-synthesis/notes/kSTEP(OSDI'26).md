# kSTEP(OSDI'26)

- **来源**: OSDI '26, osdi26-cao.pdf
- **全称**: kSTEP: Characterization and Deterministic Testing of Linux CPU Scheduler Bugs
- **作者**: Tingjia Cao, Shawn (Wanxiang) Zhong, Caeden Whitaker (UW-Madison), Ke Han (Purdue), Andrea C. Arpaci-Dusseau, Remzi H. Arpaci-Dusseau (UW-Madison)
- **开源**: https://github.com/kstep-dev/kstep
- **类型**: 论文-系统 (OS testing + fuzzing)
- **一句话 TL;DR**: 对 232 个 Linux 调度器 bug-fix commit 的系统性表征研究 + **kSTEP** 确定性测试框架。232 个 bug 中 73% 是"静默"的（无 panic/warning），75% 是 subtle semantic faults，45% 存在超过一年。kSTEP 提供细粒度的调度事件控制 + 确定性重放 + coverage-guided fuzzer，成功复现 7 个已知 bug + 发现 **4 个新 bug**。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **Functional bug** | 调度器做出了一个"错误"的决策（违反功能正确性） | 第一类 bug |
| **Policy bug** | 调度器做了"功能上有效但违反策略意图"的决策（公平性下降、负载不均衡） | 第二类 bug — 更难检测，无 obvious signal |
| **kSTEP** | Kernel Scheduler Test and Evaluation Platform | 确定性测试框架 |
| **Coverage-guided fuzzer** | 基于调度器代码覆盖作为反馈信号的自动模糊测试 | kSTEP 的自发现 bug 功能 |
| **Isolated CPU + deterministic replay** | 在隔离的 CPU 上以确定性顺序执行调度事件 | kSTEP 的核心机制 |
| **Noise-free traces** | 消除 OS 噪声的调度行为 trace | 使 subtle policy bugs 可观察 |
| **Silent bugs** | 不引起 panic 或 warning 的 bug | 73% 的调度器 bug |

## 背景与动机

### 问题
Linux CPU 调度器极其复杂（state/logic heuristics 累积多年），然而测试实践严重不足：
- 开发者依赖**长期运行的负载**（而非系统性 corner case 测试）来捕捉回归
- 对历史上真实的调度器 bug **缺乏定量理解**——什么类型？有多难触发？有多难观察？

### 232 个 Bug 的系统性表征 (§3)

**发现 1: 调度器 bug 重要但不显眼**
- 15% 导致致命故障（panic/OOPS）
- 73% 是静默的（无 panic、无 warning）→ 根本不被触发者察觉
- 75% 的根因是 subtle state/logic errors（不是简单的 null deref 或 race condition）

**发现 2: 调度器 bug 极难发现**
- 仅 27% 会 self-report（panic/warning）
- 根因分布在大量功能需求和累积的 heuristics 中 → 需要深厚的领域知识
- 28% 的触发需要特定的内核事件或 CPU 属性组合

**发现 3: 当前实践于事无补**
- 45% 的 bug 存活 > 1 年才被发现和修复
- 大部分 policy bug 仍靠人工 code review 发现
- 仅 22% 的用户提交修复附带开发者验证
- 即使修复后也几乎不加 test/warning/tracepoint

**这个表征研究本身就是一个重要贡献：首次系统化量化了调度器 bugs 的"静默性"和"长生命周期"。**

## 方案介绍

### kSTEP: 确定性调度器测试框架 (§4-5)

**两个关键能力**:

**1. 细粒度的事件控制**
- 给测试者精确控制调度器调用事件的能力（何时唤醒、何时迁移、何时抢占）
- 在隔离的 CPU 上运行 → 消除其他 workload 的干涉

**2. 确定性重放**
- 同样的输入事件序列 → 完全相同的调度行为
- 产生 noise-free, repeatable traces → 暴露 subtle policy 偏差
- "如果负载均衡在某次运行中偏差了 5%，下一次运行偏差了 3% → 根本无 debug" → kSTEP 消除了这种不确定性

**3. Coverage-Guided Fuzzer**
- 基于调度器代码覆盖率作为反馈
- 自动探索 trigger 组合空间
- 已发现 **4 个新 bug**

## 证据与评估

### 关键结果

| 指标 | 结果 |
|------|------|
| 表征研究 | 232 bug-fix commits 系统性分类 (2020-今) |
| 已知 bug 复现 | **7 个** 真实生产 bug 被 kSTEP 确定性复现 |
| 新 bug 发现 | **4 个** 通过 kSTEP fuzzer 的新 bug |
| 表征发现 | 73% silent, 75% semantic, 45% live >1yr, 仅 27% self-report |

## 整体评估

### 真正的新意
1. **首次对生产调度器 bugs 进行大规模系统表征**：232 个 commits，12 个关键发现，填补了"调度器到底坏在什么地方"的知识空白
2. **kSTEP 的"确定性+隔离"组合**：单独隔离 CPU 不够（噪声还在）；单独确定性不够（OS 复杂性不可控）→ 两者组合产生 noise-free traces
3. **coverage-guided fuzzing 在 OS 内核调度器上的首次应用**：传统观点认为内核调度器不可 fuzz（太慢、太复杂、太难观察结果）→ kSTEP 证明不正确

### 优点
- **完整的贡献链条**: characterization → tool design → evaluation (复现已知 + 发现新)
- **开源**: 完整的框架公开可用
- **解决了一个长期忽视的问题**: 调度器 testing 严重依赖 manual review + long-running workloads，没有系统性工具
- **表征研究本身有独立价值**: 12 findings 不仅 motivate 了 kSTEP，对所有内核子系统测试也有通用意义

### 局限
- **仅 Linux CFS**: 不涵盖 EEVDF、sched_ext 或其他调度器
- **仅隔离 CPU 场景**: 在某些场景下，CPU 间交互可能在隔离设置中表现不同
- **Coverage-guided fuzzer 只测试触发条件**：无法验证 policy correctness（policy 要求 higher-level semantic oracle，不是"代码是否 crash"）

### 可复用启发

1. **"先表征问题域，再设计工具"的研究范式**：232 bug study → 12 findings → 工具设计——这比"盲做最好看"的方法产出更 relevant 的工具
2. **"Silent bugs are the majority"** 适用于许多复杂内核子系统——不仅是 scheduler，内存管理、文件系统同样可能"错误但不崩溃"
3. **Coverage-guided fuzzing 与确定性重放的组合** 是测试复杂 stateful systems 的通用模式：fuzzer 探索触发空间 → deterministic replay 确保可复现
