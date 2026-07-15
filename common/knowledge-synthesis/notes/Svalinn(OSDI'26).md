# Svalinn(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-pardeshi.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 多资源瓶颈过载控制——分离吞吐控制 (credit-based admission) 和延迟控制 (per-resource AQM)，解决 single-queue fallacy（仅看最瓶颈资源导致其他资源闲置）。内存带宽用 m_semaphore 自适应限流。Goodput 提升 up to 6.51×。

## 核心问题

现代数据中心服务器有多个潜在瓶颈（CPU、内存带宽、锁、网络带宽、存储 IOPS）。单个应用产生的请求有异构资源需求（数据依赖型：cache server 小值=CPU 密集、大值=内存带宽密集、热点数据=锁密集）。现有过载控制器将应用视为 monolithic→仅对最瓶颈资源反应→其他资源闲置→**single-queue fallacy**：只根据 aggregate latency/requests-in-flight 信号决定准入，这隐式假设所有请求都被同一个最拥塞资源约束。导致的 underutilization 可达 **83% 总吞吐损失**。

资源隔离技术（按应用粒度而非请求粒度）、优先级技术（需先验知识）均无法解决。

## 关键洞察

1. **"分离吞吐控制和延迟控制——不同资源独立管理"**：吞吐控制 = credit-based admission，只要 utility function 改善就增加准入。延迟控制 = 分布式 per-resource Active Queue Management (AQM)。两者解耦使每个资源可以被独立针对性地管理。
2. **"m_semaphore——管理隐式内存带宽消费的 API"**：内存带宽不像 CPU/锁那样有显式软件队列→无法直接应用 AQM。m_semaphore 自适应限制并发内存带宽密集型线程数→用最少 CPU 核实现高内存带宽利用。开发者用 try_wait() 条件式地 guards 内存密集型代码段。
3. **"超越 single-queue fallacy——不需要 per-request 先验知识"**：不需要提前知道每个请求需要什么资源。AQM 在资源被实际访问时根据其状态作出延迟控制决策。

- 来源：Svalinn(OSDI'26)
