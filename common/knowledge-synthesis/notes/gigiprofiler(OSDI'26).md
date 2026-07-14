# gigiprofiler(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-hu-yigong.pdf
- **全称**: Diagnosing Performance Issues in Application-Defined Resources
- **系统名**: gigiprofiler
- **作者**: Yigong Hu, You-Liang Huang (Boston Univ.), Haodong Zheng (UW & EPFL), Yicheng Liu (UW & UCLA), Dedong Xie, Baris Kasikci (UW)
- **类型**: 论文-系统 (performance diagnosis + program analysis)
- **一句话 TL;DR**: 应用级资源（buffer pool、查询缓存、任务队列）的性能问题无法被系统级指标（CPU util、内存）观测到——存在严重 visibility gap。gigiprofiler 用 **LLM 语义推断 + 静态分析验证** 的混合方法自动识别应用定义资源及其使用事件，在运行时追踪瓶颈并将问题归因到具体请求和代码路径。15 个真实性能问题全部检测诊断，另发现 2 个 MariaDB 的前所未知问题（已获开发者确认）。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **Application-defined resource** | 应用内部管理的逻辑资源——buffer pool、查询缓存、任务队列、WAL 等——不通过系统级接口暴露 |
| **LLM semantic inference** | 用 LLM 从代码中识别"这可能是一个资源"的语义线索（变量命名、注释、使用模式） |
| **Static analysis validation** | 用静态分析验证 LLM 的候选识别是否真正对应资源管理代码 |
| **Resource bottleneck attribution** | 将检测到的瓶颈归因到具体请求及触发瓶颈的代码路径 |

## 背景与动机

### 问题
- 开发者 57% 的工作时间用于解决性能问题 [survey]
- 应用定义资源（MySQL buffer pool、query cache 等）的性能问题是**最难诊断**的——因为它们不被系统级指标覆盖
- 典型场景 (Figure 1): MySQL 的一个 problematic query 不断将临时表加载到 buffer pool → 填满 → 触发 costly eviction → 但 CPU util 和内存使用看起来完全正常

### 为什么现有工具不行
- 系统级 profiler (perf, flamegraph) 只能看到 CPU 热点——看不到"buffer pool 正在被错误使用"
- 应用级 profiler 需要手动 instrument——需要深入了解应用内部逻辑
- 通用 profiler 无法理解"这些 CPU cycles 花在 buffer pool eviction 上"和"这个 eviction 为什么发生了"之间的因果关系

## 方案介绍

### 三阶段混合方法

**1. LLM-based resource identification**
- 用 LLM 扫描代码 → 识别候选的应用定义资源（基于变量命名、注释、使用模式的语义线索）
- 例：识别 `buf_pool` 是一个 buffer pool 资源，`get_free()` / `scan_and_free()` 是其管理操作

**2. Static analysis validation**
- 用静态分析验证 LLM 的候选识别：追踪这些变量的数据流、确认它们确实对应资源管理代码
- 过滤掉 LLM 的误报

**3. Runtime tracking + bottleneck attribution**
- 在运行时追踪每个请求如何与被识别出的资源交互
- 从聚合的使用事件中检测瓶颈 → 将瓶颈归因到触发它的特定请求
- 将运行时证据链接回源代码路径

## 证据与评估

| 指标 | 数据 |
|------|------|
| 评估的已知性能问题 | **15**（5 个广泛部署的应用） |
| 全部检测和诊断 | **15/15** |
| 新发现的问题 | **2** (MariaDB，开发者已确认) |
| 应用覆盖 | MySQL, MariaDB, Redis, Nginx, PostgreSQL |

## 可复用启发

- **LLM + 静态分析是互补组合**：LLM 擅长从代码中"理解语义"但不可靠→静态分析验证其正确性——这套"语义推断→形式化验证"模式可推广到其他程序分析场景
- **应用定义资源的 visibility gap** 是被严重低估的问题：很多"CPU busy but no throughput"的生产事故根因都在这里
- "请求→资源交互→瓶颈"的三层归因模型是通用的性能诊断架构
