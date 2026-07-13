# Ote(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-zhang-wen.pdf
- **全称**: Extracting Database Access-Control Policies From Web Applications
- **系统名**: Ote
- **作者**: Wen Zhang* (Google, was UC Berkeley), Dev Bali, Jamison Kerney (UC Berkeley), Aurojit Panda (NYU), Scott Shenker (UC Berkeley & ICSI)
- **开源**: https://github.com/ote-project/artifact-eval
- **类型**: 论文-系统 (security + program analysis)
- **一句话 TL;DR**: 通过 **concolic execution 自动提取** Web 应用代码中隐含的数据库访问控制策略 —— 对 Ruby on Rails 应用，从分散的 access checks 和 query filters 中重建显式 policy。应用于 3 个真实应用，发现手写 policy 中的多个错误。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **Policy extraction** | 从应用代码中提取隐含的访问控制策略（"谁可以访问什么数据"） | 核心任务 |
| **Concolic execution** | 混合 concrete + symbolic 执行，用符号变量驱动路径探索 | Ote 的执行路径枚举引擎 |
| **Transcript** | concolic 执行产生的一条记录：{条件 → SQL query} | policy 的基本构建块 |
| **LLM-based relevance judge** | 用 LLM 判断代码分支是否与数据访问相关 | 剪枝手段：减少 irrelevant branch 的探索 |
| **Implicit policy** | 散布在多个函数 + filter predicates 中的隐含策略 | 当前 web 开发的常态 |
| **BlockAid** | 同组之前的工作 (OSDI '22)：一旦有了 explicit policy，如何在 DB 层面强制执行 | Ote 的上游 —— 解决了"先有 policy 再 enforce"的一半 |

## 背景与动机

### 问题
- 现实中 web 应用的访问控制策略**从未显式声明** — 散布在 `if current_user.can?` checks + `WHERE user_id = ?` query filters 中
- 这种 implicit policy 导致三个问题：
  1. **易出错**: access check 遗漏或 filter misspecification → sensitive data exposure
  2. **不可审计**: 除了应用的原始开发者，没有人能理解 policy 是什么
  3. **随时间遗忘**: 开发团队轮换后，连团队自己也不知道 policy 是什么

### Ote 的核心定位
- **不要求重写应用**（区别于 research frameworks 如 Jacqueline, Ur/Web）
- **提取 → 人工审查 → 可选 enforce**（通过 BlockAid [OSDI'22]，同组的以前工作）
- 旨在解决**已有 legacy 应用**的 policy 可见性问题

### 可扩展性关键
Web backend 代码分支多 → exhaustive path exploration 不可行。但经验观察发现：**query 触发的逻辑仅依赖一小部分简单操作** → Ote 的 concolic execution 只追踪这些操作，大幅减少 path space。

### 我的分析
这是 OSDI '26 的第四篇安全方向论文（USEC→Mohabi→Ichnaea→Ote），也是唯一关于**web application security**的。Ote 和 USEC 有共同主线：两者都认为"显式声明 policy 太难，开发者不会做"，但 USEC 的答案是用 resource-centric 降低声明成本，Ote 的答案是用程序分析**自动提取**policy。与 BlockAid (OSDI'22) 组成完整的 auto-extract + enforce 链条。

## 方案介绍

### 三步 Pipeline

**Step 1: Concolic 执行 (§4)**
- 用 concolic execution 探索应用代码的执行路径
- 只追踪与 query 触发相关的简单操作（非全程序符号化）
- 输出 transcript: `{条件1, 条件2, ... → SQL query}`

**Step 2: 剪枝 (§4.6) — LLM relevance judge**
- 用 LLM 判断代码分支是否与数据访问相关
- 忽略不相关的分支 → 将探索时间从"可能数天"减少到"数小时"

**Step 3: 合并简化 → Policy (§5)**
- 合并多个 transcript 中相似的 query pattern
- 简化条件表达式 → 生成人类可读的显式 policy
- 例: `IF user.role == 'instructor' AND course.id == params[:course_id] THEN SELECT * FROM grades WHERE course_id = ?`

### 与 BlockAid 的关系
```
Ote (OSDI'26)              BlockAid (OSDI'22)
   │                            │
extract policy ──→ review ──→ enforce at DB layer
```

## 证据与评估

### 测试对象
- **3 个真实 Ruby on Rails 应用**（含 2 个生产部署的应用）
- 对比：Ote 提取的 policy vs 手工编写的 policy

### 关键结果

| 发现 | 说明 |
|------|------|
| 提取的 policy 与手工 policy 一致 | 验证了正确性 |
| 发现手工 policy 中的**多个错误** | Ote 的自动化提取比人工更可靠 |
| LLM relevance judge 有效 | 剪枝后探索时间从"数天"→"数小时" |
| 可扩展到 3 个真实应用 | 代码规模适中（Rails app） |

## 整体评估

### 真正的新意
1. **首个从 legacy web 应用自动提取 DB access-control policy 的工具**: 前人要么要求用框架重写应用，要么只能 enforce 但不能 extract
2. **LLM 辅助的 concolic 路径剪枝**: 用 LLM 的语义理解能力来消除与数据访问无关的分支 — 这是 LLM + symbolic execution 的结合案例
3. **Ote + BlockAid = 完整的"审计 + 强制执行"链条**

### 优点
- **解决现实痛点**: policy 的"隐形"是每个长期维护的 web 应用都面临的问题
- **不需要应用重写**: 针对 Ruby on Rails 的 legacy 应用
- **发现人工错误**: 证明了自动提取比人类手工编写 policy 更可靠
- **与 BlockAid 的完整闭环**: 先提取 → 审查 → 强制执行

### 局限
- **仅 Ruby on Rails**: 语言/框架特定
- **仅对 SQL query 触发路径**: 不捕获 ORM 外部的数据访问（如 raw file I/O, cache reads）
- **LLM relevance judge 的可靠性**: LLM 可能错误判断 branch 相关性 → 遗漏 policy 覆盖
- **应用规模**: 3 个应用仍是 small-scale evaluation

### 可复用启发

1. **"自动提取 > 手工编写"的 policy 方法论**: 在 security "policy must be explicit" 的世界观中加入 "extract it, don't write it" → 降低 adoption barrier
2. **LLM 作为 symbolic execution 的剪枝 heuristics**: 这是一个新兴的模式 —— LLM 的语义理解弥补了符号执行的路径爆炸
3. **"只追踪相关操作"的 partial concolic execution**: 不做整个程序的符号化，只追踪 query 触发相关的操作 → 大幅减少状态空间
