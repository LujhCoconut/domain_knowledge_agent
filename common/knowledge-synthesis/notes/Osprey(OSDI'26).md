# Osprey(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-liu-yicheng.pdf
- **全称**: Osprey: Transparent and Efficient Virtual Memory for Secure Computation
- **作者**: Yicheng Liu (UCLA), Alice Yeh (UC Berkeley), Harry Xu (UCLA), Raluca Ada Popa (UC Berkeley), Sam Kumar (UCLA)
- **类型**: 论文-系统 (secure computation + OS virtual memory)
- **一句话 TL;DR**: 安全计算（SMPC/HE）将数据扩展 **128×**（每 bit 明文→16B 密文）——即便中等数据集也 OOM，此时 OS 开始 paging 导致不可行。现有方案要么需要提前规划重写应用，要么需要复杂的内核 speculative execution 支持。Osprey 利用 **SC 的 obliviousness** 使 speculative paging 变得实际且高效——无需内核修改，每 SC 库仅需 < 200 LOC 更改，对应用完全透明。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **SC** (Secure Computation) | 加密数据上的计算——SMPC (Secure Multi-Party Computation) 和 HE (Homomorphic Encryption) |
| **Obliviousness** | SC 的核心属性：执行路径和数据访问模式独立于输入数据 → 不可区分 |
| **Osprey** | 利用 obliviousness 实现安全计算的透明虚拟内存管理 |
| **Speculative paging** | 推测性地预取/换出页——传统需要复杂的内核支持，Osprey 利用 obliviousness 使其实际可用 |
| **128× expansion** | Garbled circuits 下的数据扩展因子——每 bit 明文 → 16B 密文形式 |
| **Conclave** | 之前的 SC 系统——报告 "实践中仅支持几千条记录" |

## 背景与动机

### 问题
- SC 使隐私保护的数据分析成为可能——Google/Meta 已在广告、临床研究中使用
- 但 SC 的 **memory expansion** 带来致命障碍：garbled circuits 将数据扩展 128×，中等数据集立即 OOM
- 一旦 OOM，OS 开始 paging → 变得 infeasibly slow
- 现有方案都需要 up-front planning 并重写应用——或需要复杂的内核 speculative execution 支持（无法广泛部署）

### 核心洞察
> SC 的核心属性——**obliviousness**（执行不依赖于数据内容）——使 speculative execution 变得简单且安全。

传统 speculative execution 的复杂性来自需要处理"错误的 speculation 需要回滚并恢复状态"。但 SC 的 obliviousness 消除了这个复杂性——因为访问模式独立于数据，speculation choices 不依赖加密输入，因此**不会出现"推测错误需要回滚"的情况**。这使 speculative paging 变得 practical 而不需要复杂的内核支持。

## 方案介绍

### Osprey 设计

1. **运行时透明 paging**：类似传统 OS 虚拟内存，SC 应用无需修改
2. **Obliviousness-powered speculation**：利用 SC 的数据独立访问模式，安全地进行推测性页面预取和换出
3. **每个 SC 库 < 200 LOC 更改**：集成成本极低
4. **无内核修改**：完全在用户态和 SC 库层面实现

## 证据与评估

| 指标 | 结果 |
|------|------|
| 代码更改 | **< 200 LOC** 每 SC 库，应用零修改 |
| 对比 | 之前的 SC-aware 内存管理需要前期规划和框架重写 |
| SC 数据扩展 | **128×**（garbled circuits） |
| SC 实践容量 | Conclave 报告 "几千条记录" |

## 整体评估

### 真正的新颖性
1. **首次识别出 obliviousness 可以简化 speculative execution**：将 SC 的约束（数据独立访问模式）转化为系统优势（安全的 speculation without rollback complexity）
2. **"借用上层语义简化底层系统"**的模式：OS virtual memory 受益于 SC 的 obliviousness——而不是相反（通常 OS 为上层提供抽象）
3. **极简集成**：200 LOC 每库 vs 之前的全面框架重写

### 可复用启发
- "将约束转化为优势"：SC 的 obliviousness 通常被视为性能限制；Osprey 将其转化为 speculative execution 的简化因子
- "借用上层语义优化底层"是跨层系统设计的通用模式，但通常方向是相反的（底层为上层提供优化）——这是一个逆向例子
- 当安全/隐私属性恰好隔离了执行路径与数据内容时，speculation 变得"免费"且安全
