# OpGuard(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-zhou-ziming.pdf
- **类型**: 论文-运维/调试
- **一句话 TL;DR**: OpGuard 以 **bitwise alignment** 作为 LLM 训练的调试原语——在生产规模下实现跨异构软件栈的逐位对齐比对，将调试时间从数天降至数分钟，诊断了 20+ 生产问题。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| Bitwise alignment | 两个执行产生逐位一致的 tensor 输出 | 作为正确性 oracle——第一个 mismatching point = 错误的第一可见证据 |
| Semantic-stable operator boundary | 跨异构软件栈（不同框架/版本/编译选项）的一致算子边界 | OpGuard 插桩位置——在这些边界处做 fingerprinting |
| Schedule-tolerant mapper | 容忍不同的执行调度（kernel fusion、recomputation 等），仍能匹配对应的算子 | 使 bitwise alignment 在非确定环境中仍然可用 |
| Longest prefix match | 两个执行产生逐位相同 tensor 的最长前缀 | 第一个 mismatching point = pivot for debugging |
| Benign nondeterminism | 不影响正确性的非确定性（如 AllReduce 中的规约顺序、FlashAttention 的分块策略） | OpGuard 控制这些以消除误报 |
| Composite signal | Loss、gradient norm 等聚合指标 | 传统调试依赖这些——高度模糊、延迟大 |

## 背景与动机

LLM 训练在数万 GPU 上运行数周，软件栈快速迭代（框架、编译器、CUDA kernel、分布式 runtime）。Bug 和硬件 glitch 的症状很微妙——loss spike、gradient norm drift——但这些都是**聚合信号**：百万次操作后的复合指标，错误容易被稀释。

**核心痛点**：当 loss curve 出现异常时，开发者无法区分 "无害的数值噪声" vs "严重 bug 的早期信号"。

**ByteDance 生产案例**：千卡 VLM 训练的 embedding backward kernel 有微小的 race condition——仅影响少数稀有 token pattern。Loss 在 3000+ 步后才 diverged——工程师花了**五天** debug 无果。

## 核心方案

### Bitwise alignment 作为正确性 oracle

```
Reference Run  → [FP₀] [FP₁] ... [FP_n]
Buggy Run      → [FP₀] [FP₁] ... [MISMATCH at Op_k]
                                    ↑ first evidence of error
```

### 三个关键技术

| 挑战 | 解决 |
|------|------|
| 跨越异构栈 | 自动发现 semantic-stable operator boundaries |
| 容忍调度差异 | Schedule-tolerant mapper |
| 控制良性非确定性 | 区分 benign vs malicious non-determinism |

## 与 ByteDance 三道 SDC/调试论文

| 论文 | 角色 |
|------|------|
| **AEGIS** | **在线检测** SDC |
| **SDCHUNTER** | **诊断定位**缺陷 GPU |
| **OpGuard** | **通用调试**——kernel bug、race condition、SDC 全覆盖 |

## 可复用启发
- **"Bitwise alignment 是最强的正确性 oracle"**：如果两个 run 在百万次操作后仍 bitwise 一致 → 没有 bug 能躲过去
- **"第一个 diverging point = pivot for debugging"**：最长 bitwise-identical prefix，第一个 mismatch 就是 debug 起点
- 来源：OpGuard(OSDI'26)
