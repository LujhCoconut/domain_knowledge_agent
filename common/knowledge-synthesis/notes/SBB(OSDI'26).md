# SBB(OSDI'26)

- **来源**: OSDI '26, osdi26-hu-kang.pdf
- **全称**: SBB: Eliminating Centralized Bottlenecks in Userspace Network Runtime
- **作者**: Kang Hu, Shuqi Dong, Chuandong Li, Ran Yi, Zonghao Zhang, Yiming Yao (PKU), Bo An (Zhongguancun Lab), Jie Zhang, Xiaolin Wang, Yingwei Luo (PKU & ZGC Lab), Zhenlin Wang (Michigan Tech), Diyu Zhou (PKU)
- **类型**: 论文-系统 (networking + OS)
- **一句话 TL;DR**: 现有用户态网络 runtime 依赖**集中式组件**（centralized timer/monitor/dispatcher）进行请求抢占、CPU 分配和负载均衡——这些组件随 worker core 数增长成为瓶颈。SBB 提出**完全去中心化**的架构：用 User Interrupt 替代集中式 timer 实现无中心抢占，用 two-level 策略（enhanced task stealing + flow migration）替代集中式 dispatcher 实现负载均衡。48 核上比集中式方案吞吐提升 **1.7-5.2×**，同时满足相同 tail latency 目标。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **C-timer** | 集中式 timer core — 负责所有 worker 的请求抢占 | 瓶颈 #1: 随 worker 数增长线性退化 |
| **C-monitor** | 集中式 monitor core — 负责 CPU allocation among services | 瓶颈 #2 |
| **C-dispatcher** | 集中式 dispatcher core — 负责跨 worker 的请求负载均衡 | 瓶颈 #3 |
| **SBB** | 完全去中心化的架构 — 无集中 timer/monitor/dispatcher | 核心方案 |
| **User Interrupt** | 新兴的硬件特性 — 允许用户态直接向其他 core 发送中断 | SBB 用于实现无中心抢占 |
| **Two-level load balancing** | 临时不均衡: enhanced task stealing; 持续不均衡: flow migration | SBB 的去中心化负载均衡策略 |
| **Flow migration** | 将请求流从一个 worker 迁移到另一个 | SBB 处理持续不均衡的手段 |
| **Join-Shortest-Queue (JSQ)** | 理论最优的队列选择策略 | 传统集中式方案 — 不可扩展 |

## 背景与动机

### 问题
用户态网络 runtime 需要三种调度能力:
1. **请求抢占**: 及时抢占长请求以保障尾延迟
2. **CPU 分配**: 在 service 之间高效分配 CPU 避免空闲浪费
3. **请求负载均衡**: 跨 worker core 均衡请求分布

### 集中式设计的瓶颈

| 集中式组件 | 功能 | 瓶颈 |
|-----------|------|------|
| C-timer | 周期性中断所有 worker 检查是否需要抢占 | 1个core负责N个worker → N↑ 时无法跟上 |
| C-monitor | 全局监控 CPU 利用率并调整分配 | single point of contention |
| C-dispatcher | 接收所有请求并按 JSQ 分发 | 理论最优但在 N↑ 时成为瓶颈 |

### 关键测量
- 传统观念认为集中式实体可以通过增加核心数量来扩展
- SBB 的测量挑战了这一观念：核心数增加不能解决根本瓶颈，因为:
  - C-timer 的抢占检查开销随 worker 数线性增长
  - C-dispatcher 的全局队列竞争变为主要瓶颈
  - 请求抢占和 CPU 分配也受影响

## 方案介绍

### 完全去中心化架构

**SBB 消除了三个集中式组件**:

1. **无 C-timer → User Interrupt**:
   - 利用新兴的 User Interrupt 硬件特性
   - Worker core 可以直接向需要抢占的 core 发送用户中断
   - 不再需要集中式 timer core 的周期性检查

2. **无 C-monitor → 分布式 CPU 分配**:
   - 每个 core 自行根据负载决定 CPU 使用
   - 去中心化的 service-level CPU allocation

3. **无 C-dispatcher → Two-level 负载均衡**:
   - **Level 1: Enhanced task stealing** — 处理临时不均衡
   - **Level 2: Flow migration** — 处理持续不均衡，将请求流从一个 worker 迁移到另一个
   - 结合两者的混合策略

### 集成 DPDK
- 基于 DPDK 实现以利用其广泛的部署基础
- 保持与现有 DPDK 应用的兼容性

## 证据与评估

### 关键结果

| 指标 | 结果 |
|------|------|
| 48 核上 vs 集中式方案 | **1.7-5.2×** 更高吞吐 |
| Tail latency | 满足相同 tail latency 目标 |
| 可扩展性 | 随 core 数增长，SBB 的吞吐持续提升（集中式方案提前饱和） |

## 整体评估

### 真正的新意
1. **识别集中式组件是用户态网络 runtime 的根本可扩展性瓶颈**: 以前未被系统化论证
2. **User Interrupt 作为去中心化抢占的第一个实际应用**: 利用新兴硬件特性替代集中式 timer
3. **Two-level 负载均衡作为 JSQ 的可扩展替代方案**: task stealing (临时) + flow migration (持续) — 不需要集中式 dispatcher

### 可复用启发
1. **"集中式实体的扩展极限"不只是理论上的 — 在实践中很早就能达到**: 传统答案 ("增加更多核心") 不能突破根本架构瓶颈
2. **User Interrupt 是去中心化系统设计的一个新原语**: 适用于任何需要 core-to-core signaling 的场景
3. **Two-level 负载均衡是处理不同时间尺度不均衡的通用策略**: 临时 → task stealing (快速+局部); 持续 → flow migration (全局+正确)
