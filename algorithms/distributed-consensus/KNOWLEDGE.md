# Distributed Consensus

分布式共识协议与复制状态机的算法设计与系统实现。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 本地线性化读共识协议 | roster leases, all-to-all leasing, linearizable reads, optimistic holding, responder set, generalized leadership | Bodega(OSDI'26) |

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
