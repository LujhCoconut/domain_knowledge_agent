---
name: algorithms
description: 算法知识库，涵盖资源调度、负载均衡、共识、分布式算法、最优化、问题求解、图算法、流式与近似算法等。当用户问题涉及算法选择、复杂度分析、算法实现或算法在系统中的实际应用时加载。
---

# Algorithms

个人算法知识库。不追求覆盖所有算法理论，而是聚焦**在系统设计与性能优化中反复遇到、需要权衡取舍**的算法主题。

## 子目录

| 目录 | 主题 | 适合归档的内容 |
|------|------|----------------|
| `resource-scheduling/` | 资源调度算法 | CPU 调度、内存分配、任务队列、批处理调度、集群调度、优先级与抢占策略 |
| `load-balancing/` | 负载均衡算法 | 一致性哈希、轮询、加权最小连接、P2C、EWMA、局部性感知负载均衡 |
| `consensus/` | 共识算法 | Paxos、Raft、PBFT、Viewstamped Replication、Byzantine Fault Tolerance |
| `distributed-algorithms/` | 分布式算法 | 分布式一致性、成员变更、Leader 选举、分布式事务、CRDT、Gossip 协议 |
| `optimization/` | 最优化算法 | 线性规划、整数规划、凸优化、启发式算法、梯度下降、遗传算法、模拟退火 |
| `problem-solving/` | 问题求解算法 | 搜索算法（BFS/DFS/A*）、约束求解、SAT/SMT、规划与调度、动态规划 |
| `graph-algorithms/` | 图算法 | 最短路径、最小生成树、图匹配、社区发现、流网络、图神经网络基础 |
| `streaming-algorithms/` | 流式与近似算法 | 流式统计、Sketch、Count-Min、HyperLogLog、蓄水池抽样、在线算法 |

## 与 `performance/`、`architecture/` 的关系

- `algorithms/` 关注**算法本身**：为什么选这个算法、复杂度、正确性、实现细节、适用条件。
- `performance/` 关注**怎么把它调快**：缓存、并行化、向量化、系统参数调优。
- `architecture/` 关注**把它放到系统里的取舍**：可用性、扩展性、一致性、成本。

一篇讲分布式共识的论文，可能同时归档到 `algorithms/consensus/`、`architecture/distributed-systems/` 和 `performance/system-tuning/`，分别记录算法、架构和性能三个视角。

## 写作建议

- 每个算法 skill 建议包含：问题形式化 → 算法核心思想 → 复杂度与正确性 → 实现要点 → 适用条件 → 典型系统应用 → 常见变体与陷阱。
- 鼓励用伪代码或实际代码片段说明关键步骤。
- 对比分析很重要：什么场景下 A 比 B 好， trade-off 是什么。
