# DGC(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-lyu.pdf
- **全称**: Shaving the Peaks: Taming Tail Latency for Managed Workloads via Disaggregated Garbage Collection
- **系统名**: DGC (Disaggregated GC)
- **作者**: Hongtao Lyu, Yuhan Li, Mingyu Wu (SJTU IPADS)
- **类型**: 论文-系统 (language runtime + disaggregation + latency)
- **一句话 TL;DR**: Concurrent GC 的标记线程在多租户 CPU-受限环境中与 mutator 竞争 CPU → 应用可用 CPU 降至 60% → 平均延迟上升超过一个数量级。DGC 将并发 GC 最昂贵的标记阶段解耦并从原始运行时中分离为**独立服务**——通过 RDMA-based software paging + global orchestrator（跨多运行时时间复用、错峰调度标记 burst）。P99 延迟最高降低 **64.4%**，峰值 goodput 提升 **24.0%**。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **DGC** (Disaggregated GC) | 将 GC 标记阶段从原始运行时中解耦为独立服务 |
| **Concurrent GC** | 并发垃圾回收——GC 线程与 mutator 线程并发执行（vs Stop-the-World） |
| **Shenandoah** | OpenJDK HotSpot 中的代表性并发收集器 |
| **RDMA-based software paging** | 通过 RDMA 高速将标记数据页传输到远程引擎——实现"远程执行但性能接近本地" |
| **Global GC orchestrator** | 服务多语言运行时的中央调度器——错峰调度各运行时的 GC burst 以避免重叠 |
| **Mutator** | 应用线程（在 GC 文献中叫 mutator——因为它在修改对象图） |

## 背景与动机

### 问题
- Concurrent GC 旨在减少 Stop-the-World 暂停（为延迟敏感应用设计）
- 但在**多租户 CPU-受限环境**中，GC 标记线程必须与 mutator 直接竞争 CPU
- 在 SPECjbb2015 基准测试中，当 GC 标记活跃时：应用可用 CPU 份额降至正常的 60% → 平均延迟上升超过**一个数量级**
- 周期性 GC 任务在"峰值"时刻造成严重的 CPU 竞争和尾延迟尖刺
- GC 不活跃时 CPU 立刻空闲——利用率曲线像一个"高峰谷"模式

### 核心洞察
将 GC 标记阶段并不仅是一个 within-runtime optimization—它是一个 **在资源受限环境中加剧的尾延迟问题**。如果将标记负载提取到**独立资源池**中并对其进行资源平滑调度，就可以消除竞争。

## 方案介绍

### DGC 设计

**1. 标记阶段解耦**
- 将并发 GC 最昂贵的**标记阶段**（CPU 密集型）从原始运行时中分离
- 标记引擎作为独立服务运行，与被服务的语言运行时通过 RDMA 通信

**2. RDMA-based software paging**
- 标记引擎访问被服务运行时堆中的对象图
- 不是将所有数据全量复制到远程引擎 → 通过 RDMA 进行按需页交换
- 实现"远程执行，接近本地性能"

**3. Global GC orchestrator**
- 服务于多个语言运行时
- 各运行时独立触发 GC → 如果同时触发，标记 burst 峰值叠加
- Orchestrator 错峰调度各运行时的 GC → 平滑总体标记负载 → 提高整体资源利用率

### 实现
- 基于 OpenJDK HotSpot Java 虚拟机
- 集成 Shenandoah 并发收集器

## 证据与评估

| 指标 | 结果 |
|------|------|
| P99 延迟降低 | 最高 **64.4%**（中等负载下） |
| 峰值 goodput 提升 | 最高 **24.0%** |
| 远程标记 vs 本地标记 | "性能接近本地执行" |
| 工作负载 | 代表性延迟敏感应用 |

## 整体评估

### 真正的新意
1. **将 GC 标记作为独立服务解耦**：传统方法优化 GC 在运行时内部的 low-level 实现——DGC 将整个标记阶段移到**外部资源池**
2. **Global orchestrator 实现跨运行时 GC 错峰调度**：将各运行时随机的 GC burst 转化为协调的、平滑的总负载——提高了多租户的整体 CPU 利用率
3. **RDMA-based paging 消除"远程执行"的性能代价**：传统假设认为"远程=慢"，DGC 通过 RDMA 按需页访问证明了接近本地性能是可行的

### 可复用启发
- "Shaving the peaks" 是资源受限系统中通用的优化策略——不仅是 GC，还包括日志刷新、索引构建、压缩等周期性任务
- 将"周期性资源消耗"转变为"外部服务 + 全局调度"是处理多租户环境中峰值问题的通用范式
- RDMA 不仅仅用于数据传输——它还可以用于实现"远程执行但本地性能感知"的系统架构
