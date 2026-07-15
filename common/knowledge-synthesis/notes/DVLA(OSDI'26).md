# DVLA(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-zhang-zhengtong.pdf
- **类型**: 论文-运维系统 (Operational Systems)
- **一句话 TL;DR**: VM 生命周期感知调度——分层预测+动态 affinity 分组+债务感知放置+离线迁移整流，解决生产 VM lifetime 分布的时空漂移和长 VM 放置债务，Alibaba Cloud 生产部署节省数千台机器。

## 核心问题

现存 lifetime-aware 调度器（LAVA 等）在生产环境崩溃于两个问题：(1) **静态策略 vs 漂移分布**——VM lifetime 分布在集群间和时间上显著漂移→固定分类失效 (2) **长 VM 放置债务**——将短 VM 和长 VM 混布优化了单机 packing，但将长 VM 散落到多台机器→这些机器长期被占→无法回收→积累 "placement debt"。

## 关键洞察

1. **"Online scheduling + offline rectification 协同"**：dynamic affinity + debt-aware placement 减少债务产生，periodic live migration 分期偿还已积累债务。类似 Quark "消除四种闲置"——不是单一优化而是全系统协同。
2. **"Placement debt = 散落的长 VM 多占的机器数"**：L_debt = 因次优放置而被迫多占用的机器。类似 PowerSight "CR 指标量化时间多样性"——将模糊的低效形式化为可量化的债务指标。
3. **"Hierarchical lifetime prediction 驱动双时间尺度"**：多尺度预测既服务 initial placement 又服务 offline optimization。

- 来源：DVLA(OSDI'26)

## 实践启发
- **"Placement debt 是任何放置优化中的隐藏陷阱"**：优化单机 packing 散落长 VM→看似短期高效实则积累长期低效
- **"Online + offline 协同 > pure online scheduling"**：某些低效无法仅通过更好的在线决策解决——需要周期性离线整流
