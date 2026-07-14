# Espresso(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-yi.pdf
- **全称**: Espresso: Constructing Cost-Efficient CXL JBOF via Inter-SSD Computing Resource Sharing
- **作者**: Shushu Yi, Yuda An, Li Peng, Xiurui Pan (PKU), Qiao Li (MBZUAI), Jieming Yin (NJUPT), Guangyan Zhang (Tsinghua), 等 — 北京大学 + 多校联合
- **类型**: 论文-系统 (storage architecture + CXL + hardware-software co-design)
- **一句话 TL;DR**: 企业级 SSD 集成了大量计算资源（ARM 处理器 + 板载 DRAM）来处理 I/O 突发——但这些资源在 JBOF 部署中由于 I/O burst 的偶发性而**严重低利用率**，同时显著增加了 SSD 成本。Espresso 通过 CXL 互联实现 **SSD 间计算资源共享**：将 SSD 架构解耦为功能独立的组件，实现细粒度的 SSD 内部资源管理，再通过去中心化方案在 SSD 间协调这些资源。**在可忽略的性能退化下降低 19% 成本**。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **JBOF** (Just a Bunch Of Flash) | 多个 SSD 以高吞吐互连部署在存储节点中——类似于 JBOD 但使用 Flash |
| **SSD computing resources** | 现代企业级 SSD 集成的 ARM CPU + 板载 DRAM（元数据/FTP 映射表等）——用于处理 I/O 请求 |
| **Espresso** | 通过 CXL 互连实现跨 SSD 计算资源共享的 cost-efficient JBOF 设计 |
| **CXL** | Compute Express Link——高速互联，使 JBOF 中的 SSD 可以直接共享计算资源 |
| **Inter-SSD resource sharing** | 一个 SSD 的空闲 CPU/DRAM 资源被另一个忙碌的 SSD 通过 CXL 调用——类似 "远程计算卸载" |
| **SSD disaggregation** | 将 SSD 架构分解为功能独立的组件——允许精细化的资源分配和管理 |
| **Decentralized resource management** | 去中心化的跨 SSD 资源协调——无集中式瓶颈 |

## 背景与动机

### 问题
- 云存储和 LLM I/O 场景需求极高的 I/O 吞吐
- 企业级 SSD 为了处理 I/O 突发集成了大量计算资源（ARM CPU + 板载 DRAM）
- 但这些资源在 JBOF 部署中由于 I/O burst 的**偶发性**而严重低利用率——不同租户的 I/O 突发发生在不同时间
- 这造成了**成本-利用率困境**：BOM 成本高以满足 burst performance 需求，但资源在大部分时间闲置

### 为什么现有方案不够
- 传统 JBOF：每个 SSD 是 black box——当 SSD A 空闲时无法利用其 CPU/DRAM 辅助忙碌的 SSD B
- 虚拟化方案：将整个 SSD 作为虚拟 SSD 导出给 hypervisor → 数据复制和回传开销大 → 不能做到 "computation near data"

### Espresso 的答案
通过 CXL 互连在保持数据原地的同时共享 SSD 间的计算资源。Espresso 不需要将数据复制到远端 SSD——只需将计算任务从忙碌 SSD 卸载到空闲 SSD 的 CPU/DRAM。

## 方案介绍

### 三步设计

**1. SSD 架构解耦**
- 将 SSD 内部分解为**功能独立的组件**（Compute、DRAM、Flash）
- 使这些组件可以由远端 SSD 访问——CXL 提供低延迟互连

**2. 去中心化资源管理**
- 无集中式调度器——各 SSD 自主决定何时请求远端计算资源
- 类似于 P2P 负载均衡：忙碌 SSD 发起请求，空闲 SSD 提供资源

**3. 计算卸载 + 无数据迁移**
- 忙碌的 SSD A 将其元数据处理任务卸载到空闲 SSD B
- 数据保留在 A 的 flash 上，B 通过 CXL 直接读取然后处理
- 避免了将数据复制到 SSD B 的开销——保持 computation-near-data 原则

## 证据与评估

| 指标 | 结果 |
|------|------|
| 成本降低 | **19.0%** |
| 性能退化 | **可忽略不计** |
| 对比 | 传统 JBOF 和虚拟化 JBOF（Figure 1 a,b） |

## 整体评估

### 真正的新意
1. **首次将跨 SSD 计算资源共享引入 JBOF 设计**：之前的工作聚焦于 SSD 内部优化或主机端资源管理，跨 SSD 的资源共享是一个 new design space
2. **CXL 作为 SSD 间的"计算互联"而非仅仅是"存储互联"**：通常 CXL 被用于内存 pooling（capacity），Espresso 将其用于 **compute resource pooling**
3. **去中心化方案避免了集中式资源管理器的瓶颈**——与 JBOF 的 scale-out 本质一致

### 可复用启发
- "compute resource pooling over CXL" 不仅适用于 SSD——任何嵌入式计算资源池（SmartNIC、DPU、storage controller）都可以共享
- 计算卸载不应该要求数据移动——CXL 的 shared memory 语义使 "data stays, compute moves" 成为可能
- "分散式 I/O = 分散式资源管理"——集中式资源管理器在 JBOF 中无法匹配分布式 I/O 模式
