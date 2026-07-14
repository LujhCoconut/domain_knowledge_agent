# Quota Marketplace(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-sivan.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: Google 部署的大规模 ML 训练芯片市场机制——动态定价 + 自动竞价 + 跨池出清，在异构工作负载价值下保证 Pareto 效率和 max-min 公平性。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| QM (Quota Marketplace) | 基于市场的 ML 训练芯片分配系统，每 ~1 分钟出清一次 | Google 已部署的跨 BU 资源分配方案 |
| Static pools / Dynamic pools | 静态池 = 季度手工分配固定芯片数；动态池 = QM 实时市场定价分配 | 从传统方式到市场机制的根本转变 |
| Credits | 与具体芯片类型、位置无关的抽象购买力代币 | 核心抽象——**不是零和的**（可以 mint），decouple 了物理资源和分配权力 |
| Market Weights (Wk) | Google 级管理员为每个 BU 分配的权重 | 确定 BU 间相对优先级——类似国际贸易中的汇率 |
| Income (Ck) | 池内管理员分配 credit 的速率 | 类似央行发币——发太多会导致通胀 |
| Automated bidder | 自动为团队的 job queue 生成竞价的系统 | 关键设计——用户无需手动参与每次拍卖 |
| Reference price (pr*) | 共享供给 Z^r 的出清价格 | 满足 ∑ zk(pr*) ≤ Z^r 的最低价格 |
| Cost-blending curve | prk = pr* · zrk/(srk + zrk)，池内部价格 = 参考价格 × 依赖共享供给的比例 | 拥有自有芯片的池获得折扣——内部价低于外部价 |
| Pareto efficiency | 不存在其他分配让某人更好而无人更差 | QM 在市场均衡下自动保证 |
| Max-min fairness (weighted) | 最大化最小（加权）效用 | QM 通过 market weights + credits 保证 |
| Chip-hour mechanism (Karma) | 基于历史使用量确定优先级的分配 | 在异构价值下失效——每个请求被视为同等价值 |
| Limit orders / Income-leverage | 用户可设置的竞价约束 | 保护团队不会超过预算 |

## 背景与动机

ML 训练芯片需求 8 年增长 100M 倍。Google 的传统方案是 **static pools**——按季度/半年度做人力分配决策，芯片固定划分到各 BU 的池中。问题：
1. **需求高度动态**（demo 爆发、会议冲刺、exploratory research）vs 人力分配每季度一次——极度不敏捷
2. **供给高度波动**：新硬件每天上线、serving 流量突发 clawback 芯片——静态分配无法适应
3. **不同工作负载价值异构**：demand deferrable 程度不同、业务优先级不同——Karma 等 chip-hour 机制假设所有请求价值相同
4. **Siloing 导致闲置**：池间隔离使得 A 池的空闲芯片不能被 B 池使用

## 问题定义

**如何设计一个资源分配机制，在动态（时变）需求 + 异构工作负载价值下，同时保证 (1) Pareto 效率 (2) (加权) max-min 公平性 (3) 供给/需求变化的分钟级响应？**

核心理论贡献：证明 chip-hour 机制（Karma）在 bi-valued instances（每个 agent 的价值只有 HIGH/LOW 两档）下**也失效**，而 QM 即使在这种情况下也保证 Pareto 效率和近似 max-min 公平性。

## 方案介绍

### 核心概念

```
             BU Admin                   Pool Admin              User/Team
         分配 Market Weights Wk    →   分配 Credit Income Ck   →   自动化 Bidding
              (跨池优先级)             (池内相对优先级)            (job queue → bid)
```

### 市场出清（每 ~1 分钟）

三个嵌套方程：

**1. 成本混合曲线**（池内部定价）：
```
prk = pr* · zrk / (srk + zrk)
```
自有芯片 srk 越多 → 内部价越低（折扣效应）

**2. 池内供需平衡**：
```
Σ min(dir, bri / prk) = srk + zrk
```
每个 team 的实际消耗 = min(需求, 预算/价格)

**3. 全局出清**：
```
Σ zrk(pr*) ≤ Z^r
```
找到最低的 pr* 使总购买不超过共享供给

算法：嵌套二分搜索（外层 pr*，内层 prk + zrk），近乎线性时间可实现。

### Credits 的关键属性

| 属性 | 含义 |
|------|------|
| **非零和** | Mint 新 credit 不需要从别人收回——提高某团队优先级只需增加其 income |
| **资源类型/位置无关** | 一维分配问题——分配 committee 只需决定 "谁有多少购买力" |
| **自然通胀机制** | 池管理员 mint 过多 credit 但 Wk 不变 → 通胀贬值 → 自纠正 |
| **价格双重功能** | (a) 经济激励 (b) 资源拥塞的透明信号——dashboard 展示实时价格和历史 |

### 防市场操纵设计

- **Automated bidder**：用户不需要手动参与每次竞价——降低认知负担
- **Limit orders**：job-level 最高支付价
- **Income-leverage**：team-level 防止过度消费的倍数上限
- **Volatility mitigation**：价格波动大时的保护机制

## 证据与评估

- **部署规模**：Google 全公司所有 BU，**数十万 ML 加速器**，占 Google ML fleet 的 double-digit percentage
- **数千日活用户**，已消费数十亿 accelerator hours
- **跨池视角消除 siloing**：公司优先级导向的占用率显著提升（vs 机会性的随机占用）
- **敏捷性**：从季度人力协商 → 每分钟自动出清
- **Buffer reduction**：生产团队不需要保留大量缓冲（可快速 clawback）→ 释放的 "bonus" 容量有时与总 committed 容量相当

## 整体评估

### 真正的新意
1. **将市场机制部署到 Google 规模的 ML 训练资源分配**：之前的工作（Karma）停留在学术原型或在有限场景中使用
2. **理论证明 chip-hour 机制在异构价值下失效 + 市场机制在相同条件下保证效率+公平**：不仅是经验性的，有理论保证
3. **Credits 的非零和特性 + 与位置/类型无关**：这是一个被低估的设计创新——将多维资源分配问题降维到一维

### 优点
- **已在 Google 全公司部署**——不是原型或模拟
- **理论保证 + 实践经验**的双重可信度
- **自动化竞价降低用户负担**——大部分用户依赖默认设置
- **价格作为拥塞信号**——透明、可操作的 market signal

### 局限与假设
- **仅适用于 ML 训练**（batch、可抢占）——不适用于 serving（需要保证 latency SLO）
- **市场权重 Wk 仍由人工设定**——BU 间相对优先级的顶层分配仍是 human-driven
- **需要一定规模的用户和需求多样性**——小规模场景市场可能不够 "厚"
- **自动化 bidder 依赖于用户正确设置优先级队列**——垃圾进垃圾出

### 适用条件
- 大规模、多租户共享稀缺资源
- 工作负载可延迟/可抢占（batch 特征）
- 需求价值和紧急性有异构性
- 供给波动频繁（新硬件上线、clawback）

### 可复用启发
- **"非零和 credits + 市场出清"是比"零和 chip-hours"更优的资源分配抽象**：解耦了分配权力和物理资源，避免了 "收回谁的芯片" 的零和博弈困境
- **"成本混合曲线"处理自有资源 vs 共享资源的定价**：池拥有自有芯片享受内部折扣，但从市场购买随着依赖加大边际成本上升——类似能源市场的 blending 机制
- **"自动化竞价"是市场机制 user-adoption 的关键**：用户调整优先级队列即可，无需理解定价算法——否则市场机制的认知负担会阻碍采用
- **价格作为拥塞信号**：不仅是分配机制，也是 guidance——团队看到 H100 价格高会自动考虑用稍旧的芯片或转移到低负载 cell
- **与 SPADE 形成"两翼"**：SPADE 按外部信号（碳、电价）调度 DAG 任务，QM 按内部市场信号（供需）分配芯片——两者都用了"价格"概念，但应用在不同层面
- 来源：Quota Marketplace(OSDI'26)

### 讨论问题
- Credits + 市场机制能否推广到其他稀缺资源（网络带宽、存储 IOPS）？
- 自动化 bidder 在极端价格波动下（如新 LLM 发布后 GPU 需求暴涨）是否仍足够好？
- 与 PowerSight + SPADE 能否组合：PowerSight 预测功率 → SPADE 调度 DAG 作业 → QM 分配 GPU → 形成从能源到芯片的端到端分配？
