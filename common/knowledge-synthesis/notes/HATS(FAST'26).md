# HATS(FAST'26)

- **来源**: https://www.usenix.org/system/files/fast26-ren.pdf, FAST '26
- **作者**: Yuanming Ren, Siyuan Sheng, Zhang Cao (CUHK), Yongkun Li (USTC), Patrick P. C. Lee (CUHK)
- **一句话 TL;DR**: 面向 Cassandra 的**整体自动化任务协同调度框架**——粗粒度 epoch-based 读分发(全局负载视图) + 细粒度读协调(统一评分=容量-预期负载) + 压缩速率控制(按 key range 读写负载+SSTable 数)，P99 延迟 -58.6%，吞吐 +2.41× vs C3/DEPART。
- **资料类型**: 论文-系统（分布式 KV 存储+LSM-tree 调度）

---

## 重要术语解释

| 术语 | 解释 | 作用 |
|------|------|------|
| Distribution Layer | 客户端请求路由层（一致哈希+复制+协调器） | 前台读负载均衡 |
| Storage Layer | 每节点 LSM-tree（MemTable+SSTable+Compaction） | 后台压缩干扰源 |
| Replica Decoupling | 将不同 replica 的 KV 对存到独立 LSM-tree | 压缩任务隔离的基础 |
| Current State (C) | M×R 矩阵：每节点每 replica 的读请求数+平均延迟 | 全局读负载输入 |
| Expected State (E) | 调整后的 M×R 矩阵：期望的读分布 | 粗粒度调度结果 |
| Unified Score | `L/ti,j - Qi+j`（容量 - 预期负载） | 细粒度副本选择 |
| Gossip + Raft | Gossip 分发状态 + Raft 选举 scheduler node | 去中心化+容错调度 |
| Compaction Rate Control | 基于 key range 的读写负载 + SSTable count 调整压缩速率 | 减少压缩-读干扰 |

---

## 背景与动机

### LSM-tree 分布式 KV 的核心矛盾

- **压缩必需但干扰严重**：Cassandra 集群中，enable compaction → 读吞吐从 26.3→7.3 KOPS（-72%）
- **压缩不足也伤读**：compaction disabled 期间读吞吐从 29.8→40.7 KOPS 提升（因为压缩减少了跨层查找），但仍有 page cache thrashing
- **负载均衡不足**：即使请求分布均匀（max difference 18.9%），最高延迟节点仍比最低延迟节点高 **4.24×**
- **小时间尺度抖动剧烈**：1秒窗口下 90.8% 窗口延迟偏离全局平均的 0.5-2.0× 范围

### 现有方案的不足

| 方案 | 问题 |
|------|------|
| C3/DEPART 等 replica 均衡 | 仅关注 distribution layer →忽略 storage layer 的压缩干扰 |
| 简单 rate-limiting | 压缩速率降→SSTable 堆积→读需跨更多层→长期读性能降 |
| 资源驱动负载均衡 | 当前资源使用 ≠ 未来请求延迟的准确预测 [YouTube study] |

---

## 方案设计

### 1. Coarse-grained Read Task Assignment（粗粒度，epoch 级）

**状态监控**：Gossip 消息嵌入读负载（average latency + read count per key range）+ 版本号。

**Scheduler Node**：Raft 选举 leader seed node，每 epoch 调整 C→E。

**调整算法**：节点按 `∑Ci-j,j > L/Ti` 分为 high-load/low-load → greedily 从 high-load → low-load 转移请求 → O(MR²/4)。

**客户端路由**：按 Ei,j / ∑Ei,j 概率选择 coordinator→期望收敛。

### 2. Fine-grained Read Task Coordination（细粒度，请求级）

**统一评分**：`Unified Score = L/ti,j - Qi+j`
- `L/ti,j` = 节点 Ni+j 在当前延迟下 epoch 内能服务的请求数（容量）
- `Qi+j` = Expected State 中分配给 Ni+j 的请求数（预期负载）
- 差值 = 还能处理多少额外请求

Coordinator 选择 unified score 最高的 replica→大时间尺度自收敛到 expected state，小时间尺度偏好压缩最完善的节点。

### 3. Compaction Task Scheduling（压缩速率控制）

**按 key range 差异化控制**：
- **高读负载 key range**：允许更高压缩速率（更快减少 SSTable 层数→加速读）
- **高写负载 key range**：限制压缩速率（减少与读的瞬时资源争用）
- **SSTable 数量多的 level**：提高压缩优先级（减少跨层查找开销）

**Replica Decoupling**：不同 replica 存到独立 LSM-tree → 单一 key range 的压缩仅影响该 replica 的 LSM-tree → 其他 replica 不受干扰。

---

## 评估数据

| 指标 | HATS vs C3 | vs DEPART |
|------|-----------|-----------|
| P99 延迟 (YCSB read-heavy) | **-58.6%** | **-59.9%** |
| 吞吐 (YCSB read-heavy) | **+2.41×** | **+2.90×** |
| P99 Get (Facebook workloads) | **-78.9%** | **-68.3%** |
| 吞吐 (Facebook workloads) | **+2.42×** | **+2.27×** |
| Gossip overhead | ~15.2% (M=100, R=3) | — |

---

## 可复用启发

1. **"粗粒度 epoch-based + 细粒度 request-level = 双时间尺度调度的协同"**：epoch 级解决可预测的负载倾斜（skewness/straggler），request 级处理小时间尺度抖动（瞬时压缩干扰）。双尺度 > 单一尺度。

2. **"Unified Score = 容量 - 预期负载"**：不是选最快 replica→选最有余量处理额外请求的 replica——避免"选最快→大家涌向最快→最快变最慢"的振荡。

3. **"Gossip + Raft = 去中心化存储 KV 的轻量协调"**：Gossip 承载状态分发（复杂度 O(M²) 但已有），Raft 仅用于 leader 选举（2-3 seed nodes）→不引入集中式瓶颈。

4. **"Replica decoupling → 压缩隔离 → 压缩影响仅限局部"**：每个 replica 独立 LSM-tree→某 key range 的压缩不影响其他 replica 的读。是调度策略可行的架构前提。

---

**已 commit & push**
