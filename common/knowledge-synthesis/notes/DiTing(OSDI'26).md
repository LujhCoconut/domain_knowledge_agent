# DiTing(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-ren.pdf
- **类型**: 论文-运维系统
- **一句话 TL;DR**: Alibaba 统一可观测性框架——整合 logs/metrics/traces 的存储和处理，通过 harvest 未充分利用的云资源实现 cost-effective 处理，数据摄入亚秒、CapEx 比传统方案低 up to 65×。

## 核心问题

Logs、metrics、traces 三种 telemetry 在云环境中被存储在**隔离系统**中（Dapper/LogStore/Prometheus）。SRE 需要多个系统、不同查询语言、手工脚本关联数据→高延迟、冗余数据移动、低运维效率。统一方案尝试过但失败：data-lake 方案统一接口但数据仍分散→data transfer overhead；in-memory NewSQL 方案 (Kraken/Monarch/Scuba) TCO 太高；ClickHouse 方案 CPU+内存很快成为瓶颈→扩展 CapEx +20%。

**核心挑战**：在 CapEx 与处理性能之间找到平衡点。

## 关键洞察

1. **"Harvest 云中未充分利用的计算资源"**：作为云厂商，服务器 fleet 经常 underutilized→大量资源可供收获。DiTing 用 harvested CPU/内存做 cost-effective telemetry 处理，而集中式存储负责可靠持久化和故障切换。
2. **"Unified storage 实现 trinity of observability"**：logs/metrics/traces 不同格式但共享通用模式（timestamp、tags、values）→统一存储模式使跨 telemetry 查询无需手动关联。
3. **"分离 compute/interface/persistence 三层"**：Compute layer（收获的 transient 资源做处理）、Interface layer（统一 API/Frontend）、Persistence layer（集中式存储保证可靠性）。类似 Svalinn "分离吞吐控制与延迟控制" 和 ASI Heterogeneity "defrag+spot GPU"——用闲置资源降低 CapEx。

- 来源：DiTing(OSDI'26)
