# DINGO / Declarative IO(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-athlur.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 声明式 IO 接口——将维护任务的灵活性（顺序、时间、数据选择）暴露给存储系统，跨任务协调 IO 复用，维护 IO 减少 26-51%，支持 1.7× 更大 HDD。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| IO wall | HDD 容量增长远快于带宽增长 → IO/TB 持续下降 → 某临界点后 IO 供给不足以满足需求 | 核心问题——“IO 墙”阻碍部署更大 HDD |
| Maintenance tasks | 数据可靠性保障任务：scrubbing、GC、capacity balancing、integrity checking | 惊人发现：占总 IO 45-70%，且几乎不可缓存 |
| Declarative IO | 新接口：任务声明 "处理设备 X 的所有 block，7 天内完成" 而非逐条读 | 核心方案——暴露任务的灵活性给存储系统 |
| Declaration | {Data set, Deadline} 对——指定要处理哪些数据，在多长时间内完成 | 声明式接口的基本原语 |
| Inter-task IO reuse | 不同维护任务访问相同 block→协调执行时间制造缓存 hit | 维护任务间 40%+ 数据重叠，目前因时间不对齐而浪费 |
| IO Planner | 接收 declarations→找到重叠→调度执行以满足 deadline | DINGO 的核心调度器 |

## 背景与动机

HDD 容量快速增长（40TB 近期，100TB 2030），但 IOPS/带宽不按比例增长 → **IO wall**。缓存吸收 application IO 已到收益递减点——剩余 IO 越来越难缓存。

**关键发现**：6 个 hyperscaler 的 trace 分析 → **45-70% 的 HDD IO 来自维护任务**（scrubbing、GC、capacity balancing 等）。这些任务：
- 访问大量数据、无单任务内复用 → 缓存无效
- 但跨任务有显著数据重叠 → 时间不对齐导致 cache miss
- **本质上是灵活的**：顺序可调、时间可调、甚至数据选择可调

## 核心方案

### Declarative IO 接口

代替 imperative `read(block_N)`：
```
Declare: "scrub all blocks on device D, deadline 7 days"
→ 存储系统自行调度具体 block 的读取顺序和时间
```

### DINGO 系统

- **IO Planner**：接收 declarations→找重叠→排程→满足所有 deadline
- 核心机制：**跨任务协调 IO 复用**——将访问相同 block 的不同任务调整到接近时间执行
- 类比 SPADE 的 "信号感知调度"——但这里是 "复用感知" 而非 "碳排放感知"

## 评估

- 小规模 HDD 集群：disk reads **-26%**
- 100PB 集群模拟：支持 **1.7×** 更大 HDD（64TB vs 36TB）
- 添加额外维护工作的 IO 惩罚很小——降低了增加维护活动的门槛

## 可复用启发
- **"声明式接口暴露灵活性"是通用模式**：维护任务、后台 compcaction、数据迁移——这些"不需要精确控制每次 I/O 何时发生"的任务都可以从声明式接口受益
- **"跨任务协调代替单任务优化"**：类似 SPADE（跨 job 协调 DAG 调度）和 Quota Marketplace（跨 BU 协调芯片分配）——系统级优化 > 单任务优化
- **"维护 IO 是隐藏的主要成本"**：45-70% 的 IO 用于维护——在做存储系统设计时意外地被忽视了
- 来源：DINGO / Declarative IO(OSDI'26)
