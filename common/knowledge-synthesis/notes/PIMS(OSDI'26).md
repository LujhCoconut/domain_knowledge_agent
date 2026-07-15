# PIMS(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-leonhardi.pdf
- **类型**: 论文-运维系统 (Operational Systems)
- **一句话 TL;DR**: Meta 五年生产维护系统——对齐故障域 + 均匀放置 + maintenance contract，将 capacity buffer 降 15%，支持可预测的 fleet-wide 部署 SLO（OS 45 天、firmware 90 天）。

## 核心问题

Meta 数百万服务器、数万服务、数十亿用户。维护有三种容量损失：(a) 计划维护 → 服务器不可用 (b) 故障域意外故障 (c) 故障域的共享组件物理维护。需要 capacity buffer（预留服务器池）填补损失——buffer 太大浪费资源，太小维护不可预测。

## 关键洞察

1. **"对齐维护与故障域"**：一次维护一个故障域→三种事件共享同一个 buffer→最小化 buffer 大小。类似 TrainMover "general standby"——一池多用。
2. **"Maintenance contract"**：参与方（硬件/软件团队+capacity 规划+调度器）之间的显式约定→可预测的维护进度。类似 DVLA "placement debt"——将操作约束形式化为显式合约。
3. **"均匀放置硬件 across fault domains"**：防止某故障域过载→避免维护时产生不成比例的容量损失。

- 来源：PIMS(OSDI'26)
