# Architecture Design

架构设计模式、原则与落地经验。

## 子目录

| 目录 | 主题 | 适合归档的内容 |
|------|------|----------------|
| `distributed-systems/` | 分布式系统 | 共识、一致性、CAP、分布式事务、RPC、服务发现 |
| `microservices/` | 微服务架构 | 服务拆分、治理、API 设计、DDD、事件驱动 |
| `data-intensive-systems/` | 数据密集型系统 | 批流处理、消息队列、数据湖、存储选型、ETL |
| `reliability-engineering/` | 可靠性工程 | 容错、降级、限流、熔断、多活、灾备 |
| `cloud-native/` | 云原生架构 | Serverless、Service Mesh、不可变基础设施、FinOps、弹性内存管理 |
| `cloud-orchestration/` | 云编排与 Agentic Workflow | 声明式 workflow 规范、跨层优化、profile-guided serving、自适应运行时 |

## 新增 skill 建议

- 每个架构 skill 建议包含：业务背景、约束条件、方案对比、最终决策、演进路径。
- 可结合 `operations` 和 `performance` 中的技能，形成“设计 → 运维 → 优化”闭环。
