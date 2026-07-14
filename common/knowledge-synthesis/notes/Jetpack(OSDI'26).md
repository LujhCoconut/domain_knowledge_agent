# Jetpack(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-tang.pdf
- **类型**: 论文-协议/系统
- **一句话 TL;DR**: Jetpack 是一个**通用 fast-path 插件框架**——以最小修改为已有共识协议添加 1-RTT 提交延迟，识别出"view change hazard"并提出两个结构要求和两个设计原则来保证跨协议的正确性。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| 1-RTT fast path | Client 直接将命令复制到所有 replica，绕过 leader 串行化，1 轮往返提交 | Jetpack 的目标——为任何共识协议添加此能力 |
| View change hazard | Leader 重选后，旧 leader 在稳定期做出的 promise 可能被新 leader 违反 | Jetpack 识别的核心正确性问题 |
| Promise | 原始路径承诺不提交与 fast path 已提交命令冲突的任何命令 | Jetpack 的安全机制——两个路径收敛到同一结果 |
| Fast Commit | Fast path 成功（所有 replica 回复 promise ack）→ client 1-RTT 提交 | 无冲突情况下的正常路径 |
| Fast Commit Fail | 某个 replica 已持有冲突命令 → fast path 放弃，由原始路径 2-RTT 提交 | 冲突或失败时的降级路径 |
| Two structural requirements | (1) Fast path 提交的值必须被原始路径知晓 (2) View change 后新 leader 必须能发现先前的 fast commit | Jetpack 对底层协议的要求 |
| Two design principles | (1) Promise 必须在 log 中有持久表示 (2) View change 必须扫描 fast path 状态 | 满足结构要求的实现方法 |
| Super-quorum (~3/4) | Fast Paxos 理论——绕过 leader 需要 ~3/4 的 quorum 而非简单多数 | Fast path 的理论基础 |
| Adaptive strategy | 高负载时自动降级部分 client 到原始路径 | 缓解 fast path 的吞吐开销 |

## 背景与动机

经典共识协议（Raft、MultiPaxos）需要 **2 RTT** 提交：client→leader→followers→client。Fast Paxos 理论可将延迟降至 1 RTT（client→all replicas→client，用 ~3/4 super-quorum）。**但是**：所有 fast-path 协议（EPaxos、CURP、Tapir、SwiftPaxos）都是**从零设计的**——fast path 与底层协议紧耦合，无法 retrofitted 到已有系统。而生产系统中成熟协议（Raft、etcd、MongoDB、ZooKeeper）不可能轻易替换。

**Jetpack 的核心问题**：能否做一个通用 fast-path 插件，以最小修改为任何共识协议添加 1-RTT 能力？

## 方案介绍

### 核心思想：双路径并行

```
Client → Fast Path (1 RTT) → 如果所有 replica ack → commit!
       → Original Path (2 RTT) → 正常流程（处理冲突/失败）
       先到先得，两个路径收敛到同一结果
```

**安全机制**：原始路径做出 **promise**——当 fast path 提交 cmd 时，原始路径承诺不提交任何冲突命令，最终提交同一个 cmd。

### View Change Hazard（核心发现）

稳定期 promise 简单（只需当前 leader 确认）。但 leader 重选后：
- 新 leader 可能不知道该 promise
- 可能提交一个与 fast path 已决定的值冲突的命令
- → **安全违规**

Jetpack 将此问题形式化为两个要求和两个原则：

| 分类 | 内容 |
|------|------|
| **要求 1** | Fast path 提交的值必须对原始路径可见 |
| **要求 2** | View change 后新 leader 必须能发现先前的 fast path 承诺 |
| **原则 1** | Promise 在原始路径的 log 中有持久表示 |
| **原则 2** | View change 时新 leader 扫描 fast path 状态并继承 promise |

**三个反例**（说明这些要求为何容易遗漏）：
- CURP 附录中的 Raft fast-path sketch
- 基于该 sketch 的部署系统 Xline
- Carousel

### 设计目标

| 目标 | 实现 |
|------|------|
| **透明** | Client 可动态选择任一 path |
| **零开销** | 所有 client 用原始路径 → 性能与未修改系统完全相同 |
| **不破坏特性** | Copilot+Jetpack 仍保留 slowdown tolerance |

## 证据与评估

- **6 个共识系统**：Raft、Mencius、Copilot、MongoDB、etcd、ZooKeeper
- **全部 TLA+ model-checked**（无 safety violation）
- **10 个 AWS 数据中心** geo-replicated 测试

### 关键结果

1. **1-RTT 延迟**：平均 commit 延迟降低 **up to 60%**
2. **对原始路径零影响**：所有 client 用原始路径时性能 = 未修改系统
3. **Adaptive strategy**：高负载时帮助达到与原系统相同的最大吞吐
4. **Mencius（多 leader）**额外开销更高——但这是理论界限而非设计缺陷

## 整体评估

### 真正的新意
1. **"View change hazard"是此前未被明确识别和形式化的通用问题**：之前每个 fast-path 协议各自处理（或不处理），Jetpack 首次提炼出两个结构要求和两个设计原则
2. **"Fast path 作为插件而非协议重写"**：类比 Kareus 的 partitioned overlap 和 SPADE 的 relative importance filter——都是在现有系统上叠加一层优化，而非推翻重来
3. **跨 6 个异构系统 + TLA+ 验证**：有效性证据充分

### 优点
- **普适性**：Raft/Mencius/Copilot/MongoDB/etcd/ZooKeeper 六大系统全适用
- **非侵入性**：对原始路径零影响
- **理论完整**：TLA+ model-checked

### 局限
- **Fast path 降低吞吐**（fundamental trade-off）——需要 super-quorum → 更多消息 → 带宽开销
- 多 leader 协议（Mencius）overhead 更高
- 不支持 BFT 和 interactive transactions

### 可复用启发
- **"识别并形式化通用 hazard + 最少的结构要求"是系统研究的好范式**：不只做一个 point solution，而是提炼出适用于整个类别的条件
- **"双路径并行 + 先到先得"的降级策略**：类似 Kareus 的"自动回退 sequential"、SPADE 的"采样后 filter"——保持快速路径的同时有可靠的慢路径作为安全网
- 来源：Jetpack(OSDI'26)
