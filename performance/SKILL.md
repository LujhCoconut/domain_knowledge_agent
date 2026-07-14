# Performance Optimization

性能优化方法论与各领域实战经验。

## 子目录

| 目录 | 主题 | 适合归档的内容 |
|------|------|----------------|
| `profiling-methodology/` | 性能分析方法论 | 瓶颈定位流程、火焰图、Amdahl 定律、建模与压测设计 |
| `optimization-paradigms/` | 优化范式（偏 research） | 串行/并行/并发优化的方法论、模型与案例 |
| `concurrency/` | 并发性能 | 锁竞争、协程/线程模型、Actor、CSP、无锁结构 |
| `parallel/` | 并行性能 | 数据并行、任务并行、MPI/OpenMP、分布式训练并行策略 |
| `system-tuning/` | 系统层调优 | CPU、内存、磁盘 I/O、内核参数、NUMA、调度、内核性能常量在线调优、内核代码优化 |
| `database-performance/` | 数据库性能 | 索引、执行计划、连接池、慢查询、缓存策略 |
| `network-performance/` | 网络性能 | TCP 调优、RDMA、延迟带宽、拥塞控制、抓包分析 |
| `gpu-ai-performance/` | GPU / AI 性能 | CUDA、显存、通信原语、推理优化、大模型训练调优 |
| `storage-filesystem/` | 存储与文件系统 | 数据管线、多核 LFS、CXL 跨 SSD 共享、DM 缓存、多组件协调式 FS |

## 新增 skill 建议

- 先归档“可复现”的问题与调优案例，再归档通用理论。
- 每个 case 建议包含：环境、现象、定位过程、根因、优化手段、验证结果。
