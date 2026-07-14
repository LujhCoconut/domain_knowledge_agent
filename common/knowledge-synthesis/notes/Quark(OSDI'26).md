# Quark(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-chai.pdf
- **类型**: 论文-运维系统 (Operational Systems)
- **一句话 TL;DR**: 蚂蚁集团将 serverless 范式集成到 colocated Spark batch analytics——细粒度资源分配+异构感知调度+快速实例供给，消除四种闲置（slot/gap/start/stop），CPU 利用 +37.37%，长尾作业 15%→2%，节省 >10 万核。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| Co-location | 高低优先级工作负载混布在同一物理节点 | 基础策略——在线服务仅用 22% CPU → harvest 额外 26.8% |
| Effective utilization | 实际有用计算占总 CPU 时间的比例 | 核心发现——批处理仅 67% 有效率 |
| Slot idle | Spark 粗粒度 executor slot 管理→slot 空等 | 闲置类型 1 |
| Gap idle | 硬件异构+干扰→执行速度不均→快等慢 | 闲置类型 2 |
| Start/Stop idle | 启动/销毁分析实例的高延迟 | 闲置类型 3&4——类似 AEGIS/SDCHUNTER 的 "恢复和诊断解耦" |
| Quark | 将 serverless 范式（细粒度+弹性+快速）注入 batch analytics 的框架 | 核心方案 |
| Long-tail jobs | 少量作业占据不成比例的总完成时间 | 从 15%→2% |

## 核心问题

云厂商通过 overcommitment+colocation 提高 CPU 利用率——蚂蚁集团在线服务仅用 22% CPU→harvest 额外 26.8%。**但批处理工作负载的有效率仅 67%**——33% 的 CPU 周期被浪费在四种闲置上。

## 关键洞察

1. **"Serverless 范式解决 batch 低效"**：Spark 的粗粒度 slot 模型 + 慢启动 + 无动态伸缩→与 serverless 的细粒度快速弹性形成对比。Quark 将 serverless 的关键特性（细粒度资源分配、按需快速供给、异构感知）注入 batch analytics。
2. **"四种闲置各有针对性解法"**：没有一种单一的万能优化——slot idle 需要细粒度分配，gap idle 需要异构感知调度，start/stop idle 需要快速实例供给。

- 来源：Quark(OSDI'26)

### 实践启发
- **"有效利用率不是总利用率"**：高 CPU 利用率 ≠ 高效——67% 有效率意味着三分之一的 CPU 在做无用的 "pretending to be busy"。类似 PowerSight "Design Power 是虚假的上限"
- **"Serverless 不仅仅是 FaaS——其范式可以改善传统 batch"**：细粒度弹性是可以注入现有系统的特性
