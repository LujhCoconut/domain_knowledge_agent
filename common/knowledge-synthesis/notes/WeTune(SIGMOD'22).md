# WeTune(SIGMOD'22)

- **来源**: 2022 ACM SIGMOD International Conference on Management of Data
- **作者**: Zhaoguo Wang, Zhou Zhou, Yicun Yang, Haoran Ding, Gansen Hu (SJTU IPADS), Ding Ding, Jinyang Li (NYU), Chuzhe Tang, Haibo Chen (SJTU IPADS)
- **URL**: https://ipads.se.sjtu.edu.cn/_media/publications/wetune_final.pdf
- **一句话 TL;DR**: 借鉴编译器 superoptimization 思想，通过暴力枚举 query plan template + SMT-based 等价性验证，自动发现数据库查询重写规则，在 20 个 GitHub 热门开源 Web 应用中成功优化 247 条现有数据库无法优化的查询。
- **资料类型**: 论文-系统（SIGMOD'22）

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| Query Rewrite Rule | 将源查询模板转换为等价目标模板的规则 `<q_src, q_dest, C>` | 核心输出——数据库优化器使用这些规则做查询重写 |
| Query Plan Template | 由符号化算子组成的逻辑查询计划树，表名/属性/谓词均为符号 | 规则的输入/输出——通用而非绑定具体表 |
| Constraint Set (C) | 描述模板符号间关系的谓词集合（如 RelEq、AttrsEq、SubAttrs、Unique 等）| 条件——C 满足时 q_src 等价于 q_dest |
| Superoptimization | 编译器技术——穷举搜索所有可能的等价指令序列，找到最优组合 | 方法论来源 |
| SMT-based Verifier | 利用 SMT solver 证明 FOL 公式 UNSAT 来验证规则正确性 | 核心验证器——转为 UNSAT 问题避免穷举推理 |
| SPES | 现有查询等价性验证器（支持 Aggregate/UNION 但不支持完整性约束）| 辅助验证器——补充 built-in verifier 能力 |
| Promising Rule | 目标模板中每种算子数量不多于源模板的规则 | 初筛 heuristic——不增加算子数 |

## 背景与动机

### 查询重写的现状

查询重写是数据库性能的核心——将原始 SQL 转换为等价但更高效的形式。现有重写规则由专家手工编写，积累缓慢（几十年来仅有有限规则集）。ORM（如 Rails ActiveRecord、Hibernate）加剧了问题——它生成的 SQL 往往不符合手工编写的"典型"模式 → 现有规则无法匹配。

### 实证研究：手工重写的需求

WeTune 研究了 50 个 GitHub issue（Discourse、GitLab、Spree、Redmine 等热门 Web 应用）——全部是关于查询性能的开发者修复。**SQL Server 2019 最新版无法自动重写 27/50（54%）**——但开发者手动重写后的等价查询只花 0.3s（vs 原来的 37s）。

### 为何不能纯人工

- SQL 语义复杂（NULL、outer join、subquery、aggregation 交互）
- 等价性证明困难（需要同时考虑 schema 完整性约束）
- 人脑很难枚举所有可能的等价变换

## 问题定义

**要解决什么**: 自动发现新的数据库查询重写规则——给定搜索空间（算子类型和模板大小），自动枚举、验证、筛选出数据库当前不具备但对真实查询有效的新规则。

**现有工作为什么不够**:
- 手工编写: 慢、漏（54% 真实查询无法覆盖）
- Learned query optimization (Neo/RL-based): 依赖 cost model 而非等价性，可能引入错误
- SPES 等验证器: 只能验证已有规则，不能发现新规则
- Equality saturation (如 EGG): 适用于程序优化但未适配 SQL 的完整性约束和外键语义

## 方案介绍

### 方案概述

WeTune = Rule Enumerator（枚举器）+ Rule Verifier（验证器）+ Rule Selector（筛选器）

```
所有可能的 plan templates (size ≤ 4)
    │
    ▼
Rule Enumerator ──→ 3113 distinct templates
    │                枚举所有模板对 + 约束组合
    ▼
Rule Verifier ────→ 1106 promising & non-reducible rules
    │                SMT-based: 证明 ¬(C ⇒ q_src ≡ q_dest) UNSAT
    ▼
Rule Selector ────→ 43 useful rules
    │                在真实 queries 上测试性能
    ▼
247 queries optimized on 20 real-world apps
```

### 关键模块

#### 1. Rule Enumerator — 暴力枚举规则空间

**规则表示**: `<q_src, q_dest, C>`
- `q_src` / `q_dest`: 符号化逻辑查询计划模板（算子: Sel/Proj/InSub/IJoin/LJoin/Dedup + 符号化的表/属性/谓词）
- `C`: 约束集合，如 `RelEq(t1, t2)` / `AttrsEq(c0, c1)` / `SubAttrs(c, r)` / `Unique(r, c)` / `NotNull(r, c)` / `RefAttrs(r1, c1, r2, c2)`

**枚举过程**:
1. 枚举所有 query plan template（size bounded, ≤4 operators）→ **3113 个 distinct templates**
2. 对每对模板 `(q_src, q_dest)` 枚举所有可能约束组合
3. 关键优化—"interesting constraints": 只枚举"有意义的"约束组合（relate tables and their attributes between pairs of queries）而非所有可能的约束 → 极大缩小搜索空间

**Promising rule 初筛**: 目标模板每种算子数量 ≤ 源模板 → 减少算子数 = 可能减少执行成本

#### 2. Rule Verifier — SMT-based 等价性证明

**核心 insight: 将等价性证明转为 UNSAT 问题**

- 传统: 证明 `C ⇒ ∀t.q_src(t) = q_dest(t)` 是 tautology → SMT solver 需穷举所有 interpretation 和所有 tuple → 极慢
- WeTune: 证明 `¬(C ⇒ ∀t.q_src(t) = q_dest(t))` UNSAT → solver 找到 contradiction 即停 → 对正确规则通常很快

**实证**:
- 232 条已知正确的 Calcite 规则: 73 条成功验证（其余因不支持的操作符）
- 100 条故意制造的错误规则: 仅 4 条被成功判定为错误 → 96 条 timeout → WeTune **保守地将 timeout 视为不正确**

**SPES 集成**: 当 built-in verifier 不支持某操作符（Aggregation/UNION）时作为补充验证器。SPES 的局限是需要将符号化模板 concretize（assign names → 构造 schema），且不支持完整性约束和外键。

**两种 verifier 的能力对比**:

| Feature | SPES | Built-in |
|---------|------|----------|
| Aggregation | ✓ | ✗ |
| UNION | ✓ | ✗ |
| NULL | ✓ | ✓ |
| Integrity Constraint | ✗ | ✓ |
| Different # of input tables | ✗ | ✓ |
| Complex Predicate | ✓ | ✗ |

**数据**: 43 条 useful rules 中，35 条由 built-in verifier 发现，8 条通过 SPES 发现

#### 3. Rule Selector — 在真实查询上评估

- 对每条 promising rule 生成 probing query（最小 concrete query 匹配该规则）
- 测量 rewritten vs original query 的执行成本
- 用规则重写 Workload 2（收集自 20 个热门 GitHub Web 应用的查询）→ 测试规则的真实效果
- 消除冗余规则（可由其他 rule composition 表达的规则）

## 证据与评估

### 测试环境

- **搜索**: 120 CPU cores, 36 小时 → 3113 templates → 1106 promising & non-reducible rules
- **验证**: SMT solver (Z3), ~50ms per rule on average, 383 solver invocations per rule
- **性能评估**: MS SQL Server 2019, 所有 query 在同一 client machine 上运行

### 发现规则示例

| # | 源模板 | 目标模板 | 效果 |
|---|--------|----------|------|
| 1 | Sel+Proj(r) | Proj+Sel(r) | 先选后投 → 先投后选（谓词下推） |
| 2 | Dedup+Proj(r) | Proj(r) | 投影到无重复列 → 消除去重 |
| 4 | InSub(InSub(r0,r1),r1) | InSub(r0,r1) | 消除冗余 IN 子查询（两个相同子查询 AND 连接） |
| 15 | InSub(r, Proj(r')) | r | 子查询消除（半连接优化） |
| 16 | Proj(IJoin(r, r')) | Proj(r) | 内连接投影消除冗余 |

### 对真实应用的优化效果

| 应用 | 优化查询数 |
|------|-----------|
| GitLab | 最多的命中 |
| Discourse | — |
| Spree | — |
| 其他 17 个应用 | — |
| **总计** | **247 queries** |

这些查询是**现有数据库（MySQL/PostgreSQL/MS SQL Server 最新版）无法优化的**——即 WeTune 发现的是新的、有价值的重写规则。

**性能提升**: 部分查询从 37s → 0.3s（引用自 motivation 中的 GitLab 案例）→ orders of magnitude

### Rule discovery stats

- Templates enumerated: 3113 (size ≤ 4 operators)
- Potential rules generated: ∼10^6 pairs
- After "interesting constraints" pruning + promising heuristic + redundancy elimination: **1106 rules**
- After real-query evaluation (usefulness test): **43 useful rules**
- Total time: **36 hours on 120 cores**

## 整体评估

### 真正的新意

1. **Superoptimization 思想首次应用于 SQL 查询重写**: 编译器 peephole optimizer 穷举搜索代码序列 → WeTune 穷举搜索 query plan templates。核心迁移难点是 SQL 的"generic rule"概念——规则不能绑定具体表名/列名 → 需要引入符号 + 约束集合。

2. **Constraint enumeration + "interesting constraints" heuristic**: 暴力枚举所有模板对不难，但枚举所有约束组合是组合爆炸的。WeTune 的 "interesting constraints"（仅枚举能关联模板间表和属性的约束）是使搜索可行的关键 insight。

3. **UNSAT 转化技巧**: 将等价性证明从"证明 tautology"转为"证明 negation 是 UNSAT" → SMT solver 对后者通常快得多。验证了 73/232 条已知规则无 timeout。

4. **保守 timeout = false 策略**: timeout 时保守视为不正确 → 牺牲 recall（漏掉正确规则）换 precision（避免错误规则引入数据库）——这是正确的工程选择，因为错误的重写规则可能导致数据错误。

### 优点

- 方法优雅: 编译器 superoptimization + SMT verification → 数据库查询重写
- 实验扎实: 50 个真实 GitHub issue 的实证研究 + 20 个 Web 应用的查询
- 工程完整: 同时支持 built-in verifier 和 SPES，互补覆盖更多 SQL 特性
- 输出是可解释的规则（不像 learned optimizer 的黑盒重写）

### 缺点

- 搜索空间限制: size ≤ 4 operators → 更复杂的规则无法发现
- SMT timeout 的召回损失: 保守策略意味着可能漏掉正确的复杂规则
- 只支持特定的 SQL 子集: 不支持 window function、CTE、lateral join 等
- 性能测试基于 MS SQL Server 的 cost estimate → 实际执行时间可能因优化器而异
- Aggregation + UNION 支持依赖 SPES → SPES 不支持完整性约束 → 这两类优化的交集无法被任何 verifier 覆盖

### 局限与假设

- 规则是 `q_src → q_dest` 方向性: 只考虑了源模板算子数 ≥ 目标模板算子数的方向（简单的"减少算子 = 更快"heuristic）→ 可能漏掉增加算子但实质更高效的规则（如索引利用）
- 假设改写后 query 的 cost estimate 能反映实际性能 → 在 MS SQL Server 上验证
- 规则局限于 WeTune 支持的算子集（Sel/Proj/InSub/IJoin/LJoin/Dedup/Agg）

### 适用条件

- 频繁使用 ORM 生成 SQL 的 Web 应用（Ruby on Rails / Django / Hibernate）
- 查询具有"反直觉"模式——人工优化器规则未覆盖
- 需要新规则但缺乏数据库内核开发专家的团队
- 离线批量发现规则 → 部署到生产数据库优化器

### 可复用启发

1. **"Superoptimization 是可迁移的方法论"**: 编译器学的方法 → 数据库查询重写。任何需要"自动发现等价变换规则"的领域都可能适用——API 调用组合优化、数据流图重写、ML 计算图优化（类似 TASO 当年在 DL compiler 中的工作）
2. **"约束集合作为等价性的条件——通用的 symbolic rewriting 范式"**: 不是 `q_src ≡ q_dest`（无条件的），而是 `C ⇒ q_src ≡ q_dest`——只有当某些 schema 属性满足时才等价。这让规则可以编码"外键 → join 消除""唯一约束 → distinct 消除"等 schema-aware 的优化
3. **"UNSAT 比 tautology 更好证明"的 SMT 工程技巧**: 不仅适用于查询等价性——任何 "证明 A ⇒ B" 的问题都可以尝试 "证明 ¬(A ⇒ B) UNSAT" → solver 更容易找到 contradiction
4. **"保守 timeout = false"是安全关键系统的正确工程选择**: 宁可漏报（false negative）不可误报（false positive）→ 适用于任何 correctness-critical 的自动生成系统
5. **"枚举所有 + 验证 + 筛选"的三阶段架构具有通用性**: 类似 FastServe 的"枚举 + verify + select useful"——先宽进（穷举）→ 严验证（SMT）→ 真应用（real-world query testing）。可推广到任何"自动发现新知识"的领域

### 与类似工作的关系

- **TASO (SOSP'19)**: DL 计算图的重写规则自动发现 → WeTune 在 SQL domain 的对应
- **SPES (VLDB'20)**: 查询等价性验证器 → WeTune 集成为验证后端
- **Learned Query Optimizer (Neo/Bao)**: 优化执行计划选择 → WeTune 优化重写规则（互补而非竞争）
