# Bodega(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-hu-guanzhou.pdf
- **类型**: 论文-协议
- **一句话 TL;DR**: Bodega 是首个通过 **roster leases**（all-to-all 租约）在**任何节点、任何时间**提供本地线性化读的共识协议——读延迟降低 5.6×～13.1×，写性能与 MultiPaxos 持平。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| Linearizable read | 线性化读：client 观察到的结果满足实时串行顺序，仿佛在与单机交互 | 最严格的一致性级别，metadata store/coordination service 的刚需 |
| Roster | 集群元数据的广义形式——除 leader 外还指定哪些 replica 是哪些 key 的 **responder** | Bodega 核心抽象：将 leadership 泛化为任意 subset 作为本地读服务节点 |
| Responder | 被 roster 指定为某 key 服务本地读的 replica | 非 leader 节点也可以安全地本地回复读请求 |
| Roster Leases | All-to-all 租约：至少 majority 节点向所有 responder 授予租约 | 取代 Leader Leases（all-to-one）和 Quorum Leases（受限），实现稳定的 roster 共识 |
| Optimistic holding | Responder 遇到未 commit 的 write 时不拒绝读，而是将读挂起到对应 slot | 减少重定向——commit 通知到达后立即回复（通常 <1 RTT） |
| Early accept notifications | Follower 回复 Accept 时也广播通知给该 key 的 responders | 减半 holding time——一旦收到 m 个通知应答方即可确定 commit |
| Safety threshold | thresh 列表的第 m 小值——responder 必须 commit 到此 slot 才能安全本地读 | 防止落后节点在 roster 切换时返回 stale data |
| Stable condition | `|renewBy| ≥ m ∧ committed all slots up to thresh` | 本地读的前置条件——两个条件同时满足才可安全本地读 |

## 背景与动机

共识协议是分布式系统的基础（etcd、Spanner、Chubby、ZooKeeper），而**线性化读**是最强一致性级别的刚需。在广域网多 AZ 部署中，将读请求发送到最近的 replica 可以大幅降低延迟——但问题在于如何保证该 replica 的数据是最新的（self-contained，不依赖外部 oracle）。

**现有方案的不足**：
- **Leader Leases**：只有 leader 能本地读，其他节点必须 redirect
- **Quorum Leases**：quiescent 时可本地读，但一有 concurrent write 就批量失效
- **Leaderless（EPaxos 等）**：冲突时退化为 leader-based，本地读根本不可行
- **Megastore**：需要外部 coordinator，write 时主动 revoke 所有 lease（2 RTT to all）

**核心矛盾**：要使非 leader 节点安全地本地读，必须确保 "write 不会在不通知该节点的情况下 commit"——这需要对 responder set 的一致共识和 write quorum 约束。

## 问题定义

**如何设计一个共识协议，在没有外部 oracle 的前提下，使得任意 replica 子集可以在任意时间（即使有 concurrent write）安全地服务本地线性化读，同时保持写性能和容错性？**

## 方案介绍

### 核心洞察：从 Leadership 到 Roster

```
Classic:     Leader 是唯一特殊节点
Leader Ls:   Leader + stable leadership (all-to-one leases)
Quorum Ls:   Leader + 可配置 grantee set (部分 all-to-some)
Bodega:      Leader + 任意 Responder set (all-to-all leases)
```

**Roster** 将 "leadership" 泛化——不仅指定 leader，还按 key range 指定哪些节点是 responder。Writes 必须到达 key 的所有 active responders 才能 commit（额外约束）。

### 三步骤设计

**1. 正常操作**（假设 roster 稳定）

| 操作 | 流程 |
|------|------|
| **Write** | 同 MultiPaxos，但 commit 条件加上 "收到所有 responder 的 AcceptReply" |
| **Read (Leader)** | 直接本地回复（同 Leader Leases） |
| **Read (Non-leader Responder)** | 查本地日志最高 committed slot → 若 committed 直接回复，若 in-flight → **optimistic holding** |
| **Read (Non-responder)** | 拒绝 + redirect 到最近的 responder 或 leader |

**2. Optimistic Holding**

Responder 遇到 in-flight write 时不拒绝——把读挂起到对应 slot 的 pending set。Commit 通知到达时释放所有 pending reads。**Expected hold time < 1 RTT**（正常情况下）。

**3. All-to-All Roster Leases**（关键创新）

每个节点同时充当 lease grantor 和 grantee：
- 广播 `<bal, ros>` → 并行对所有 peer 发起 `initiate_leases()`
- Stable condition：`|renewBy| ≥ m` **且** 已 commit 到 thresh 列表的第 m 小值
- Roster change 在 **2 轮消息** 内完成（Revoke + Guard）
- 非故障情况下 leasing 全在 off-critical-path（后台）

### 与其他协议的定性比较

| 协议 | Write延迟 | Read延迟(quiescent) | Read延迟(有write干扰) | 退化期长度 |
|------|-----------|---------------------|------------------------|------------|
| Leader Ls | l + m | l | l | - |
| EPaxos | c + M | c + M | c + M + m | - |
| Quorum Ls | l + N | c | c + l | 2N |
| **Bodega** | **l + N** | **c** | **c ~ c + m/2** | **m/2** |

- l = client→leader RTT, c = client→nearest RTT, m = majority, N = all-nodes

Bodega 在 write 延迟上与 Quorum Leases 相同（都是 l+N），但在读延迟和退化期上有显著优势。

## 证据与评估

- **实现**：Summerset (25.6K LoC async Rust)，protocol-generic replicated KV store
- **对比**：MultiPaxos, Leader Leases, EPaxos, PQR, Quorum Leases, etcd, ZooKeeper
- **测试**：5-site WAN 集群（AWS 多区域）

### 关键结果

1. **读加速**：比 Quorum Leases/EPaxos/PQR 快 **5.6×～13.1×**（average client read）
2. **与 etcd/ZooKeeper 的 sequential-consistency 性能持平**——但提供更强的线性化保证
3. **写性能**：与 MultiPaxos 持平（额外 responder 覆盖的开销 marginal）
4. **Proactive roster change**：2 轮消息完成
5. **YCSB 全变体测试**：Bodega 在所有 workload 上匹配或超越 etcd/ZooKeeper 的 sequential consistency 部署

## 整体评估

### 真正的新意
1. **Roster Leases 是全新的协议设计点**：之前只有 all-to-one（Leader Ls）和 all-to-some（Quorum Ls），all-to-all robe Bodega 首次实现
2. **"Leader→Roster"的泛化**：从单一特殊节点到任意 subset 的 responder 指定——这是对 Paxos family 的实质性扩展
3. **Optimistic holding + early accept notifications**：将 write 干扰期间的 read 退化从 "redirect to leader" 优化为 "hold ~m/2 时间"

### 优点
- **Non-intrusive**：对 classic consensus 的扩展仅修改 commit 条件——写性能 marginal impact
- **Self-contained**：不需要外部 coordination/membership oracle
- **容错性完整**：容忍任意 minority 故障
- **可配置**：responder set 可按 key range 灵活指定

### 局限与假设
- **Write 需要到达所有 responders**：如果 responder set 选了远端节点 → 写延迟可能增加（但通常 responder set 也选近端）
- **Clock drift 假设**：依赖 bounded clock drift（同 Leader Leases/Quorum Leases）
- **Roster policy 不在本文范围**：如何最优选择 responder set 留给 future work

### 适用条件
- 广域网多 AZ 部署的共识系统
- 读多写少或读密集型 workload（metadata store、coordination service）
- 需要线性化读保证的场景

### 可复用启发
- **"All-to-all leasing 解锁了新设计点"**：之前 lease 被限制在 all-to-one（leader）或 all-to-some（quorum）模式——全对全租约是 consensus protocol 设计空间中未被探索的区域
- **"Optimistic holding 是比 redirect/retry 更优的降级策略"**：预期 commit < 1 RTT 的情况下，"等待一时"比"立即拒绝+重试"更快且更省资源
- **"Roster = generalized leadership"的思维**：将 "一个特殊节点" 泛化为 "一个特殊子集"——leader、responder、participant 都是 rooster 的特例
- 来源：Bodega(OSDI'26)
