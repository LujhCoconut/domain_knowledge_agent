# Distributed Consensus

分布式共识协议与复制状态机的算法设计与系统实现。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 本地线性化读共识协议 | roster leases, all-to-all leasing, linearizable reads, optimistic holding, responder set, generalized leadership | Bodega(OSDI'26) |
| 排序共识公平性 | equal opportunity, ε-ordering equality, ∆-ordering separation, SRO, front-running mitigation, sandwich attack | Pompē-SRO(OSDI'26) |

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
