# ACOS(FAST'26)

- **来源**: https://www.usenix.org/system/files/fast26-baron-updated.pdf, FAST '26
- **作者**: Benjamin Baron, Aline Bousquet, Eric Metens, Swapnil Pimpale, Nick Puz, Marc de Saint Sauveur, Varsha Muzumdar, Vinay Ari (Apple)
- **一句话 TL;DR**: Apple 的跨地域对象存储系统 ACOS，两代架构演进——1.0 双区域全量副本+LRC（RF=2.40），2.0 五区域 XOR parity+LRC（RF=1.50）——在保证 11 nines 耐久性 + 5 nines 可用性的同时大幅降低存储成本，十年生产部署，EB 级数据。
- **资料类型**: 论文-系统（工业部署经验）

---

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| Stamp | 单个数据中心内的独立存储服务单元（含计算+存储+网络） | ACOS 的基本部署单元 |
| Store | 一组跨地域的 stamp 集合，对外暴露唯一 endpoint | ACOS 1.0 的隔离域 |
| Container | 存储层中的大文件（4-32 GiB），容纳多个 object | 持久化和复制的粒度 |
| Cluster | 一组 container 的集合，按 LRC codec 组织 | 副本/密封/修复的基本单位 |
| LRC (Local Reconstruction Codes) | (12,2,2) 或 (20,2,2)：12/20 data + 2 local parity + 2 global parity | 单 stamp 内的纠删码，容忍 4 个 container 故障（86.15% 概率） |
| XOR-5 | 5 个 region 各存 1 segment，其中 1 个 parity (XOR) | ACOS 2.0 的跨域编码 |
| Sealing | 当 replicated cluster 满后，删除多余副本、生成 LRC parity、变为不可变 | 写入→持久化的转换 |
| ClassVI | Apple 自研的 metadata 系统（类似 BigTable，RocksDB 后端，Raft 一致） | ACOS 2.0 的元数据引擎 |
| Rebalancer | 跨 stamp 移动 sealed containers 的服务 | Stamp 间容量和 IOPS 平衡 |
| TTFB | Time To First Byte | 核心延迟指标 |
| MTTDL | Mean Time To Data Loss | 耐久性模型 |
| Degraded Read | 优先从 local parity 读→超时 500ms 后 fallback 到 global parity | 单 stamp 内容错 |
| Object Segmentation | 将 object 分为 4 个等长 data segment + 1 个 XOR parity | ACOS 2.0 的跨域分布 |

---

## 背景与动机

### Apple 的存储需求

- iCloud（照片/视频/备份），Apple Music/TV（大文件媒体），Apple Maps（地图+3D+分析），内部服务
- 数亿用户，EB 级数据，日均数十亿请求
- 对象大小极端变异：从几十 KB（metadata/thumbnail）到数 GB（视频）
- 多 workload 的访问模式差异大：备份（低频低延迟）、照片（高频高吞吐）、媒体文件（只写不删不常读，靠 CDN）

### ACOS 的设计目标

1. **高可用 + 高耐久**：容忍磁盘/主机/机架/数据中心故障
2. **成本效率**：EB 级数据的每一个复制因子百分点都值巨额资金
3. **可扩展**：透明增加容量和吞吐，无需客户端改造

---

## 两代架构对比

| 维度 | ACOS 1.0 (2013) | ACOS 2.0 (当前) |
|------|----------------|-----------------|
| 架构 | 双 region，active-active | 五 region，统一点 |
| Stamp 内 | (20,2,2) LRC, RF=1.20 | (20,2,2) LRC, RF=1.20 |
| Stamp 间 | 全量对象异步复制, RF=2.00 | 对象分 5 segment，XOR parity, RF=1.25 |
| **总 RF** | **2.40** | **1.50** |
| Metadata | 双 Cassandra | ClassVI (自研 BigTable-like, RocksDB + Raft) |
| 端点 | Per-store，客户端管理多 endpoint | 统一 DNS endpoint，DNS geo-routing |
| 扩缩容 | 需创建新 store，数据迁移靠客户端 | Rebalancer 透明跨 stamp 移动 sealed data |
| TTFB | 较低（同域数据） | 略高（可能跨域读 segment，差 ~50ms） |
| 可用性保证 | 双域同步复制 → 任一域故障完整服务 | XOR-5 → 单域故障可用 parity 重建，两域故障不可用 |

---

## ACOS 1.0 核心设计

### Container 生命周期

1. **Placement**：coordinator 持续创建 replicated cluster（5 副本），跨 disk/host/rack 分布
2. **写入**：client handler → leader replica (Raft 选举 + ZAB 风格的分布式事务日志) → 流式复制到 4 follower → quorum 确认 → metadata 写入
3. **Sealing**：replicated cluster 满 → 删除 3 replica，生成 2 local + 2 global LRC parity → 不可变 sealed cluster
4. **Compaction**：coordinator 按"已删数据量"排序 → 重写 container（跳过已删除对象）→ 重新计算 LRC parity
5. **Repair**：disk/host/rack 故障 → 30 分钟 grace period → LRC 重建丢失 container

### 跨域复制

每个 stamp 异步扫描所有 container → 将对象 push 到另一个 stamp → 可做 stamp 级 failover（全量代理到另一 stamp）。

### 三大局限

1. **高存储成本**：总 RF=2.40 → EB 级数据浪费大
2. **Store 生命周期复杂**：每个 store 是固定容量的孤立域，满后需建新 store → 客户端管理多 endpoint/credential/quota → 停用旧 store 需逐对象迁移
3. **Metadata 系统瓶颈**：Cassandra hotspotting、跨 stamp 一致性弱、LIST 性能差

---

## ACOS 2.0 核心设计

### Cross-Region Segmentation（核心创新）

**PUT**：client handler 收到对象 → 分为 4 个等长 data segment + 1 个 XOR parity → 分别发往 5 个 region 的不同 stamp 存储。

**GET** (正常)：读 4 个 data segment → 拼接返回。

**GET** (降级)：任一 segment 不可用 → 读剩余 4 个 segment → XOR 重建缺失 segment（p90 计算开销 0.3ms）。

**GET** (降级 + failover)：需要从更远的 region 读 → 额外 50ms（percentile > p60）。

**Range GET**：仅需读覆盖请求范围的 segment，除非该 segment 不可用→需读所有 segment 的对应范围来 XOR 重建。

### ClassVI Metadata 系统

- 自研，BigTable 模型，RocksDB 引擎，Raft 一致
- 行级强一致读写；单 replica 不一致读（local region，个位数 ms P99.9）用于优化 TTFB
- 跨 5 个 region 部署完整副本

### 多租户可扩展设计

- **统一 endpoint**：单一 DNS 记录 → 按客户端地理位置路由到最近 region 的 load balancer
- **Stamp weight**：PUT 时根据 stamp 可用容量加权选择目标 stamp
- **Rebalancer 服务**：file-level copy（sealed container 直接复制→避免事务日志 I/O + EC 重算的 CPU）→ 在 stamp 间均衡容量和 IOPS
- **双层 rate limiter**：deployment-level（切分前） + stamp-level（切分后）

### 延迟优化（使 cross-region 延迟可接受）

1. **DNS geo-routing**：请求路由到最近 DC；安全机制在 region 接近容量时溢出到其他 region；为延迟敏感流量预留专用 endpoint
2. **Metadata prefetch**：GET 请求同时发出 consistent + inconsistent 读 → inconsistent 先返回 → 立即触发 segment 读取 → consistent 返回后比对 → 一致则开始流式返回 → 不一致（0.001%）则丢弃重读。**将 metadata 延迟隐藏在 segment 磁盘 I/O 中。**
3. **Segment regional preference**：优先读网络 RTT 最小的 4 个 segment → 通常包括 parity + XOR 重建 → 小 CPU 代价换大网络延迟节省（cross-continent 差几十 ms）
4. **Load Balancer Bypass**：inter-stamp 通信绕过负载均衡器 → P50 -22%, P90 -32%, P95 -26%

---

## 生产数据

### 延迟（优化后）

| 指标 | ACOS 1.0 | ACOS 2.0 |
|------|----------|----------|
| GET TTFB | 相近（metadata prefetch 补偿 cross-region） | 略高 |
| GET 全对象 (1 MiB) | 基准 | +50ms（跨域网络差） |
| PUT 全对象 (1 MiB) | 基准 | 相近（并行 segment 写入） |

### 耐久性 & 可用性

| 配置 | MTTDL (年) | 年降级时长 | 年不可用时 | RF |
|------|-----------|-----------|----------|-----|
| (12,2,2) LRC + 2x replication (1.0) | 4.51×10²³ | 631s | 0.0032s | 2.67 |
| (20,2,2) LRC + XOR-5 (2.0) | 1.31×10²¹ | 1,578s | 0.0316s | **1.50** |
| (20,2,2) LRC + XOR-6 | 8.77×10²⁰ | 1,893s | 0.0473s | 1.44 |

**关键 trade-off**：RF 从 2.67→1.50（-44%），MTTDL 从 10²³→10²¹（仍远超 11 nines），年不可用从 0.003s→0.032s（仍远超 5 nines SLO）。

### 数据迁移

- EB 级数据从 1.0 到 2.0 历经数年，5 阶段迁移（客户端配置→对象迁移→校验→请求代理→DNS 切换）
- 全程零停机、客户端透明

---

## 整体评估

### 真正的新意

1. **"从 2-way 全副本到 N-way XOR parity + segment 分布——跨域复制范式的成本革命"**：ACOS 将跨地域冗余从全副本（RF=2）改为 XOR parity（RF=N/(N-1)=1.25），配合更多 region（双→五）——总 RF 从 2.40 降到 1.50。不是新算法，而是**多 region 架构 + XOR 编码的工程化组合决策**。

2. **"Metadata prefetch——用不一致读的乐观主义隐藏跨域 metadata 延迟"**：同时发 consistent + inconsistent 读→不一致先返回→立即触发 segment 获取→consistent 返回后验证。将 metadata 的 P99.9 延迟隐藏在 segment 磁盘 I/O 中——而 99.999% 的情况下两者一致。这是"speculative execution on metadata"的优雅应用。

3. **"两层编码的局部性设计——local LRC 容忍 stamps 内 failure burst，regional XOR 容忍数据中心级故障"**：local LRC 独立处理频繁的盘/主机/机架故障（不触发跨域数据移动），regional XOR 仅当整个 stamp 不可用时才被调用——分离了 frequency 和 severity 两个维度。

### 优点

- EB 级、十年生产经验的工业论文——耐久性/可用性模型有真实参数支撑
- 每一代设计的局限都明确列出，且直接驱动了下一代设计的决策
- 迁移策略（5 阶段、零停机）是实操价值极高的参考
- 延迟优化部分（prefetch、regional preference、LB bypass）是 cross-region 系统设计的宝贵经验

### 局限

- 未公开具体对象数量和绝对延迟数字（仅提供了 CDF 形状和相对比较）
- 未讨论多 region 场景下的 PUT 延迟——并行写 5 个 segment 的 tail 效应是否需要处理
- XOR parity 在 >1 个 region 故障时完全不可用——但文中论证了概率极小
- Compaction 和 repair 期间的性能影响未量化
- 仅限于 HDD（论文暗示下一代会用更大容量盘→IOPS/TB 继续下降）

### 适用条件

- 有跨大陆数据中心部署能力的大规模云厂商
- EB 级存储容量——每一百分点 RF 降幅都有巨大经济效益
- 多种 workload 混合（媒体/备份/分析），对延迟要求不一
- 可接受 cross-region 网络延迟（~50ms 跨北美大陆）

### 可复用启发

1. **"N-way XOR 替代全副本——多 region 让 Reed-Solomon 变得成本可接受"**：单 region 内 XOR 无法容忍多故障→但多 region（N=5）使 XOR parity 能容忍单 region 故障→RF 从 2.00 降到 1.25。不是编码算法创新，而是"region 数量增长 → 可用简单编码达到更低 RF"的架构决策。

2. **"两层故障分离——frequency vs severity"**：local LRC 处理高频低严重度故障（盘/主机/机架），regional XOR 处理低频高严重度故障（数据中心宕机）。每一层优化各自最擅长处理的故障模式——双层架构中的劳逸分工。

3. **"Metadata 乐观预取——speculation 不止于 CPU"**：同时发一致+不一致读→用不一致读的提前返回隐藏延迟→验证后流式返回。0.001% 的不一致率使这个 gambit 几乎是纯收益。类似于 libDSE 的 speculative durable execution——"乐观假设+fallback 验证"是分布式系统的通用高性能模式。

4. **"Sealed container 直接复制→迁移零 I/O 放大"**：ACOS 2.0 的 rebalancer 不重新解析对象、不重新计算 EC→直接做文件级 copy of sealed containers。这是"利用不可变性的奢侈"——类似 RubikFS 的"write-once 允许昂贵排序"。不变性在系统架构中的价值被系统性低估。

5. **"Segment regional preference——CPU 换网络"**：优先读最近 4 segment → 几乎总是包括 parity → 用 XOR 重建代替跨大陆读一个 data segment。小 CPU 代价换大网络延迟节省——数据放置策略中"物理距离 > 逻辑角色"的优先级反转。

### 讨论问题

- 当更大容量 HDD 使 IOPS/TB 持续下降时，compaction 和 repair 是否会成为可用性瓶颈？
- ClassVI 的 inconsistent read 在什么情况下会出现 >0.001% 的不一致率（如频繁 rebalance 期间）→ metadata prefetch 的 fallback 成本会急剧上升？
- ACOS 的 XOR-5 假设 5 region 独立故障——但如果 shared infrastructure（如网络 backbone、电力、冷却）引入跨域关联故障，模型是否仍然成立？
