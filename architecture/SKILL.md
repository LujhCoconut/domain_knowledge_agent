# Architecture & Computer Architecture

软件架构设计与计算机体系结构，涵盖分布式系统、云原生和 CPU/GPU 微架构、存储层次、互连、近存/存内计算等硬件架构。ISCA、MICRO、HPCA 等体系结构会议的论文归档于此。

## 子目录

| 目录 | 主题 | 适合归档的内容 |
|------|------|----------------|
| `distributed-systems/` | 分布式系统 | 共识、一致性、CAP、分布式事务、RPC、服务发现 |
| `microservices/` | 微服务架构 | 服务拆分、治理、API 设计、DDD、事件驱动 |
| `data-intensive-systems/` | 数据密集型系统 | 批流处理、消息队列、数据湖、存储选型、ETL |
| `reliability-engineering/` | 可靠性工程 | 容错、降级、限流、熔断、多活、灾备 |
| `cloud-native/` | 云原生架构 | Serverless、Service Mesh、不可变基础设施、FinOps、弹性内存管理 |
| `microarchitecture/` | CPU/GPU 微架构 | 流水线、分支预测、乱序执行、缓存、TLB、虚拟化、安全硬件 | 
| `memory-storage-hierarchy/` | 内存层次 | CXL、解聚内存、缓存一致性、内存池化 |
| `accelerators/` | 加速器架构 | GPU、TPU、NPU、FPGA、领域专用加速器（DSA） |

## 新增 skill 建议

- 软件架构 skill：业务背景、约束条件、方案对比、最终决策、演进路径。
- 硬件架构 skill：微架构机制原理、设计权衡（性能/功耗/面积）、评估方法论（模拟/仿真/原型）、工业趋势。
- 可结合 `operations` 和 `performance` 中的技能，形成“设计 → 运维 → 优化”闭环。
