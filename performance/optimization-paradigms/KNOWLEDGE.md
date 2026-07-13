# Optimization Paradigms

偏 research 与方法论：如何系统性地优化串行、并行、并发程序。

这里的 skill 不聚焦某个具体系统（如 Linux、数据库），而是聚焦**程序形态**与**优化范式**。

## 子目录

| 目录 | 主题 | 适合归档的内容 |
|------|------|----------------|
| `serial-optimization/` | 串行优化 | 算法复杂度、缓存友好性、向量化、编译器优化、I/O 与计算重叠、延迟隐藏 |
| `parallel-optimization/` | 并行优化 | 数据并行、任务并行、流水线、负载均衡、通信开销、Amdahl/Gustafson 定律、扩展性分析 |
| `concurrent-optimization/` | 并发优化 | 锁粒度、无锁结构、读写分离、事务内存、协程调度、上下文切换、竞争避免 |
| `parallelism-concurrency-models/` | 并发并行模型 | CSP、Actor、Fork-Join、MapReduce、SPMD、SIMT、流式计算模型对比 |

## 与 `concurrency/`、`parallel/` 的区别

- `concurrency/`、`parallel/`：侧重**概念、模型、机制**（是什么）。
- `optimization-paradigms/*-optimization/`：侧重**怎么优化、优化策略、案例**（怎么做）。

## 写作建议

- 每个 skill 建议包含：问题定义 → 瓶颈模型 → 优化策略 → 典型代码/伪代码 → 效果评估。
- 鼓励使用「定律 + 量化 + 反例」的方式组织内容，避免变成 API 使用说明。
