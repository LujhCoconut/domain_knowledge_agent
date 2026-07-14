# Pompē-SRO / Equal Opportunity(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-zhang-yunhao.pdf
- **类型**: 论文-协议
- **一句话 TL;DR**: 将法律中的 "equal opportunity" 概念引入排序共识——通过 Secret Random Oracle 注入受控随机性，约束 Byzantine 节点对交易排序的偏置，有效缓解 front-running 和 sandwich 攻击。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| Ordered consensus | 扩展 SMR——不仅要求 replica 对 ledger 达成一致，还要求排序满足正确性条件 | 本文研究的协议类别 |
| Ordering linearizability | 若最低正确节点的 indicator(c2) > 最高正确节点的 indicator(c1)，则 c1 先于 c2 | Pompē 的保证——但无法约束"接近到达"的请求排序 |
| Equal opportunity | 法律概念：具有相同相关特征的候选人应有相等机会被选中 | 本文的核心公平性框架——区分 relevant vs irrelevant features |
| Relevant features | 应影响排序的特征（调用时间、交易费） | 排序应仅依赖这些 |
| Irrelevant features / Protected classes | 不应影响排序的特征（地理位置、网络速度、客户端身份） | 现有系统被这些特征偏置 |
| Impartiality | 交换两个具有相同 relevant features 的 invocation 不会改变 preference profile 的概率 | 公平性第一支柱 |
| Consistency | 引入新 invocation 不应改变已有 invocation 的相对排序 | 公平性第二支柱——等价于点分系统 |
| ε-Ordering Equality | 对于同时调用的请求，所有排列的概率偏离均匀分布不超过 ε | Impartiality 的近似版本 |
| ∆-Ordering Separation | 间隔 ≥ ∆ 时间的两个请求，先调用的必然排在前面 | Consistency 的近似版本 |
| Secret Random Oracle (SRO) | 容错的无偏随机源——随机值在各方 commit 后才 reveal | 实现排序公平的核心抽象 |
| TEE-based SRO | 使用可信执行环境在本地生成和 reveal 随机值 | 无网络通信开销的 SRO 实现 |
| TVRF-based SRO | Threshold Verifiable Random Function——多方协作生成可验证随机值 | 密码学 SRO 实现——不依赖硬件信任 |
| Pompē-SRO | 扩展 Pompē——注入 SRO 生成的噪声到 fault-tolerant timestamps | 本文的新协议 |
| Sandwich attack | Attacker 在 victim 交易前后插入两笔交易的三笔并发排序攻击 | Ethereum 上 32 个月提取了 $174M |

## 背景与动机

区块链中交易**排序直接影响财务收益**——与传统 SMR（仅要求所有正确 replica 一致处理）不同。Pompē 的 ordering linearizability 只能约束"时间明确分离"的请求排序，对"时间接近"的请求完全留给网络竞争决定。

**真实攻击**：
- **Front-running**：攻击者利用更快的网络抢在 victim 的大买单之前下单 → Ethereum 32 个月 $89M
- **Sandwich attack**：攻击者在 victim 前后各插入一笔交易 → Ethereum 32 个月 $174M
- **地理偏置**：欧洲节点比澳洲节点更多 → 欧洲客户交易更可能排在前面

**根本原因**：现有协议不区分 relevant features（时间、费用）和 irrelevant features（地理位置、网络延迟）。

## 问题定义

**如何形式化和强制执行 "equal opportunity"——即具有相同相关特征的交易应有相等的机会获得任何排序位置，不受不相关特征（网络速度、地理位置）影响？**

## 方案介绍

### 理论框架：Equal Opportunity

从法律/经济学引入两个支柱：

1. **Impartiality**：交换两个相同 relevant features 的 invocation → preference profile 概率不变
2. **Consistency**：引入新 invocation 不改变已有 invocation 的相对排序

→ 两者共同等价于**点分系统**（point system）：用仅依赖 relevant features 的分数排序，分数相等时均匀随机打破平局。

### 两个 Correctness Conditions（实践中的近似）

实际系统中 invocation time 无法精确测量（受网络延迟影响）：

| Condition | 含义 | 理想值 |
|-----------|------|--------|
| **ε-Ordering Equality** | 同时调用的 n 个请求，任意排列概率偏离均匀分布 ≤ ε(n) | ε = 0 |
| **∆-Ordering Separation** | 间隔 ≥ ∆ 的请求保证按时间排序 | ∆ = 0 |

**Trade-off**：减小 ε（更公平）→ 需要更大的 ∆（更难区分真实时间差）

### Secret Random Oracle (SRO)

核心挑战：随机性必须**在各方 commit 后才 reveal**——否则攻击者可利用它偏置排序。

SRO 接口：`Reveal(k, sigs) → random` | `Generate(k) → proof` | `Verify(k, proof, r) → bool`

保证：
- **Uniqueness**：所有有效 Reveal(k) 返回相同值
- **Secrecy**：在 n-f 签名到达前，随机值在计算上不可区分于均匀分布
- **Randomness**：输出为均匀随机
- **Validity**：Generate 的 proof 可被 Verify

**两种实现**：
| 实现 | 随机生成方式 | 通信开销 | 信任假设 |
|------|-------------|----------|----------|
| TEE-based | TEE 本地生成 + 远程 attestation | 无额外通信 | 信任 TEE 硬件 |
| TVRF-based | 多方 Generate → Combine 门限签名 | 需要 O(n) 消息 | 密码学假设 |

### Pompē-SRO 协议

在 Pompē 的 fault-tolerant timestamps 中注入 SRO 噪声。同步期间（GST 后）同时保证 ε-Ordering Equality 和 ∆-Ordering Separation。

## 证据与评估

- **实现**：Pompē-SRO，集成 TEE-based 和 TVRF-based SRO
- **测试**：12 城市 geo-distributed 部署

### 关键结果

1. **Front-running 缓解**：添加 [0, 5∆net] 噪声（如 ∆net=400ms），ε < 5%（法律认为可接受的阈值）
2. **吞吐**：与 Pompē 持平
3. **延迟成本**：median 增 1.12×，P99 增 1.42×
4. **Sandwich 攻击**：6 种排列概率接近均匀 → 攻击者期望利润大幅降低
5. **Noise range [0, 5∆net] 是实践中的 sweet spot**：ε 可接受 + ∆ 不太大

## 整体评估

### 真正的新意
1. **将法律/经济学中的 equal opportunity 概念首次引入排序共识**：不仅是一个新的 correctness condition，而是提供了完整的建模框架（impartiality + consistency → point systems）
2. **SRO 作为新的分布式系统抽象**：类似 VRF 但有 "commit-before-reveal" 的协调特性——这是对现有随机性原语的有价值补充
3. **ε vs ∆ 的 trade-off 理论刻画**：定量化了"公平性"和"时间准确性"之间的冲突

### 优点
- **理论框架完整**：从 legal principle → economic model → correctness condition → protocol 的完整链条
- **两种 SRO 实现**：覆盖不同的部署假设（有 TEE / 仅有密码学）
- **真实攻击数据驱动**：Ethereum 轨迹分析提供了令人信服的动机

### 局限与假设
- **仅适用于 partially synchronous model**（需要 GST 后的同步期）
- **ε 和 ∆ 需要手动配置**：最佳参数取决于 workload 和攻击模式
- **增加延迟**：对延迟敏感的 DeFi 应用可能需要权衡
- **不能完全防止 front-running**：只能降低攻击者的成功概率/期望利润

### 适用条件
- 区块链排序共识（特别是 DeFi 场景）
- 有 Byzantine 节点且网络优势可被利用的场景
- 对公平性有法律/监管要求的金融系统

### 可复用启发
- **"区分 relevant vs irrelevant features"是通用公平性框架**：不仅是区块链——任何排序/排名系统（推荐系统、拍卖、调度）都可以通过定义自己领域的 relevant features 来应用 equal opportunity
- **"受控随机性 → 公平性"的原则**：当关键信息（如精确调用时间）在开放系统中无法可靠获取时，受控随机性可以弥补
- **"SRO 的 commit-reveal 协调模式"可推广**：任何需要"先做出决策再注入不可预测随机性"的场景
- 来源：Pompē-SRO / Equal Opportunity(OSDI'26)
