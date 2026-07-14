# Distributed Consensus

分布式共识协议与复制状态机的算法设计与系统实现。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 本地线性化读共识协议 | roster leases, all-to-all leasing, linearizable reads, optimistic holding, responder set, generalized leadership | Bodega(OSDI'26) |
| 排序共识公平性 | equal opportunity, ε-ordering equality, ∆-ordering separation, SRO, front-running mitigation, sandwich attack | Pompē-SRO(OSDI'26) |
| 通用共识 Fast-Path 框架 | 1-RTT plugin, view change hazard, promise, dual-path, super-quorum, TLA+ verification | Jetpack(OSDI'26) |
| 协议操控竞速 BFT | protocol-rigged racing, cooperative+productive, proposal lane, slowdown detection, non-equivocation as race | Ambulance(OSDI'26) |
| 云存储共享日志耐久层 | LogDrive, durability-sequencing separation, composable quorum, cloud storage SMR, weakTail | LogDrive(OSDI'26) |

---

## 本地线性化读共识协议 (Bodega)

### 核心问题
广域网多 AZ 部署中，读请求需要发到 leader → 跨区域延迟高。现有方案——Leader Leases 只有 leader 能本地读，Quorum Leases 一有 concurrent write 就批量失效，EPaxos 等 leaderless 协议在冲突时退化为 leader-based。需要一种在任何 replica、任何时间都能安全服务本地线性化读的协议。

### 关键洞察

1. **"Roster = generalized leadership"**：将协议中"一个特殊节点（leader）"泛化为"一个特殊子集（responders）"。Write 必须覆盖所有 responder 才能 commit → 任何 responder 本地持有的数据要么已 committed，要么在 in-flight 中将被 commit。

2. **"All-to-all leasing 解锁了新设计点"**：之前 consensus 只有 all-to-one（Leader Ls → leader）和 all-to-some（Quorum Ls → 有限 grantee set）。Bodega 引入 all-to-all roster leases——节点间全对全授租，至少 majority 持有相同 roster 才认为稳定。

3. **"Optimistic holding 比 redirect/retry 更优"**：Responder 遇到 in-flight write 时不应拒绝读，而是挂起到对应 slot 的 pending set——commit 通知 <1 RTT 后回复。比"拒绝→重定向→重试"更快且更省资源。

4. **"Early accept notifications 减半 holding time"**：Follower 回复 Accept 时也广播给该 key 的 responders → m 个通知到达即可判定 commit → 减半 expected hold time。

- 来源：Bodega(OSDI'26)

### 实践启发
- **"All-to-all leasing"可推广到任何需要分布式成员一致元数据的场景**：不仅是 consensus，config management、service discovery、membership 都可以借鉴 roster leases 的思路
- **"Optimistic holding"是 read-heavy workload 下的通用优化**：当预期等待时间 < 拒绝+重试时间时，"挂起等待"总是更优——适用于任何需要强一致性的读操作
- **Roster 的可配置性（per-key-range responder set）使得本地读可以按热点分布精细化**：类似 WPaxos 的 key partitioning 但更灵活——responder set 可以 overlap、可以独立调整

---

## 排序共识公平性 (Equal Opportunity / Pompē-SRO)

### 核心问题
区块链中交易排序直接影响财务收益——front-running 和 sandwich 攻击已在 Ethereum 上分别造成 $89M 和 $174M 损失（32 个月）。Pompē 等 ordered consensus 协议只能约束"时间明确分离"的请求排序，对"时间接近"的请求完全留给网络竞争决定——攻击者利用更快网络和地理 proximity 系统性偏置排序。根本原因：现有协议不区分 relevant features（调用时间、交易费）和 irrelevant features（地理位置、网络延迟）。

### 关键洞察

1. **"将法律/经济学中的 equal opportunity 移植到排序共识"**：Impartiality（相同 relevant features 的请求应有对称的排序概率）+ Consistency（引入新请求不应改变已有排序）→ 首次为区块链公平排序提供了严格的理论框架。

2. **"点分系统 = Impartiality + Consistency 的唯一实现"**：仅根据相关特征打分 + 分数相等时均匀随机打破平局。但实践中调用时间无法精确测量 → 引入 ε-Ordering Equality 和 ∆-Ordering Separation 两个近似条件。

3. **"Secret Random Oracle 的 commit-reveal 模式"**：随机性必须在各方 commit 后才 reveal——否则攻击者会利用它偏置排序。SRO 保证 Uniqueness + Secrecy + Randomness + Validity 四个性质。

4. **"ε vs ∆ trade-off"**：更大的噪声（更小 ε）→ 需要更大的时间间隔 ∆ 才能可靠区分先后 → 公平性和时间准确性之间的本质冲突。

- 来源：Pompē-SRO(OSDI'26)

### 实践启发
- **"区分 relevant vs irrelevant features"是通用公平性框架**：不仅是区块链——任何排序系统（推荐、拍卖、调度）都可以通过定义 relevant features 来形式化公平性要求
- **"受控随机性 → 公平性"的设计模式**：当关键信息无法可靠获取时（如精确调用时间），受控随机性可以替代精确测量
- **SRO 可以用于任何需要"先决策后揭示随机性"的场景**：如 leader election、committee selection、lottery-based scheduling

---

## 通用共识 Fast-Path 框架 (Jetpack)

### 核心问题
经典共识协议（Raft/MultiPaxos）需 2 RTT 提交，Fast Paxos 理论可降至 1 RTT，但所有现有 fast-path 协议（EPaxos/CURP/Tapir）都从零设计，与底层协议紧耦合——无法 retrofitted 到生产系统（etcd、MongoDB、ZooKeeper）。能否做一个通用插件为任何共识协议添加 1-RTT 能力？

### 关键洞察

1. **"双路径并行 + 先到先得"**：Client 同时向 fast path（1 RTT 到所有 replica）和原始路径（2 RTT 到 leader）发送请求。Fast path 成功 → 1 RTT 提交；冲突/失败 → 原始路径接管。两个路径通过 "promise" 机制收敛到同一结果。

2. **"View change hazard"是要害问题**：稳定期 promise 简单，但 leader 重选后新 leader 可能不知道该 promise → 可能提交冲突命令。Jetpack 首次形式化此问题并提出两个结构要求：(1) Fast commit 的值必须对原始路径可见 (2) View change 后新 leader 必须发现先前的 promise。

3. **"两个设计原则实现两个要求"**：(1) Promise 在原始路径 log 中有持久表示 (2) View change 时扫描 fast path 状态并继承。Jetpack 用三个反例（CURP sketch、Xline、Carousel）说明这些原则为何容易被遗漏。

4. **"Fast path 插件而非协议重写"——零侵入**：所有 client 使用原始路径时性能 = 未修改系统。Fast path 使用与否不影响原始路径的特性和优化。

- 来源：Jetpack(OSDI'26)

### 实践启发
- **"识别通用 hazard + 最少结构要求"是好的系统研究范式**：不只做一个 point solution，而是提炼适用于整类的条件
- **"双路径并行 + 安全网"模式可推广**：保持快速路径的同时有可靠慢路径兜底——类似 Kareus 自动回退 sequential、SPADE 采样后 filter
- **TLA+ model-checking 对协议设计的价值**：6 个系统全覆盖验证，确保跨 view change 的安全

---

## 协议操控竞速 BFT (Ambulance)

### 核心问题
生产 BFT 部署面临的核心威胁不是 crash 而是 slowdown（慢节点）——网络配置错误、部分硬件故障、GC 暂停、磁盘 I/O 竞争。Timeout 让 leader 与时钟竞速（太激进误判、太保守空等），Hedging 用时钟偏置竞速但仍需等待，异步方案通用 case 延迟高。需要一种**非阻塞、生产性的** slowdown 检测机制。

### 关键洞察

1. **"Protocol-rigged racing 替代与时钟竞速"**：Replica 之间用协议步骤竞速——leader 做更少步骤（2 步 quadratic）、非 leader 做更多步骤（3 步 linear）→ 正常 leader 自然更快，不需要时钟来区分快慢。满足 cooperative + productive 两个必要条件。

2. **"竞速 = Non-equivocation phase"**：所有 replica 本来就需执行 non-equivocation 来 commit。竞速期间的工作**直接可用于 commit**——如果 leader 输了，replica 的竞速工作不需要推倒重来。

3. **"Cutoff 机制进一步偏置 leader"**：Leader 不需要第一个完成，只需在 cutoff 前完成。Cutoff 最大化 leader 赢面同时保证快速恢复。

4. **"Recovery path 三步"**：Recover（恢复可能已 commit 的 leader proposal）→ Persist（race exclusion + 持久化）→ Random lane select（随机选 lane commit，防止网络对手偏置）。

- 来源：Ambulance(OSDI'26)

### 实践启发
- **"用协议步骤偏置竞速"是通用设计模式**：leader 做更少步骤、非 leader 做更多步骤 → leader 自然更快 → 不需要时钟
- **"将检测机制嵌入已有协议步骤"**：不增加额外的检测逻辑层——检测就是协议本身
- **"Cooperative + Productive"是好的异常检测的充要条件**：可以用于评估任何 proposed 机制
- **竞速不空等的设计哲学与本周其他论文共享**：Kareus（optimistic holding）、Bodega（optimistic holding）、Ambulance（productive racing）——都拒绝阻塞等待

---

## 云存储共享日志耐久层 (LogDrive)

### 核心问题
云对象存储（S3）便宜可靠但只适合大块写入。Confluent 的 K2 pub-sub 服务需要**小写入的元数据存储**：自建分布式 DB（FoundationDB/KRaft/ZooKeeper）运维太复杂，用 DynamoDB 太贵（占 K2 总成本 ~75%）。需要一种在廉价云存储上构建元数据存储的方法。

### 关键洞察

1. **"分离 durability 和 sequencing"**：LogDrive 只保证顺序写入的 weak 语义（不强求每个地址的 linearizability）→实现极其简单，可以 layer 在任何云存储上（仅需数百行代码适配 S3/DynamoDB/S3Express）。
2. **"WeakTail API 是关键抽象"**：不强求 linearizability，只要求 "几乎顺序写入" 下返回最后一个写入位置——这大大降低了在被动云存储上实现共享日志的难度。
3. **"LogDrive 可以通过 quorum 组合（类似 RAID）"**：多个 LogDrive 实例组成 quorum→增强耐久性——类似 RAID 的条带化和镜像。

- 来源：LogDrive(OSDI'26)

### 实践启发
- **"弱语义抽象使实现变得简单"**：不强求每个地址的 linearizability 使得 LogDrive 可以实现在任意云存储上——语义越弱，可部署性越强
- **"分离 concerns 以简化每层"**：durability（LogDrive）+ sequencing（AtomicLog）分离→各自简单→组合起来功能完整
- **"Metadata 成本常被低估"**：75% 的总成本来自元数据层——这不仅仅是性能问题，是经济可行性问题
