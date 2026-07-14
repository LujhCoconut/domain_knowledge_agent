# Aletheia(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-ferreira.pdf
- **全称**: Aletheia: Automated Detection of Data Integrity Violations in Microservices
- **作者**: Mafalda Sofia Ferreira, João Ferreira Loff, João Garcia, Rodrigo Rodrigues (INESC-ID, IST, Universidade de Lisboa)
- **类型**: 论文-系统 (static analysis + microservice correctness)
- **一句话 TL;DR**: 微服务将数据拆到异构系统后，跨服务的数据依赖由**应用代码手动维护**——没有数据库级的 foreign key 等约束。Aletheia 用 **ER 模型 + 关系代数**形式化定义三种跨服务数据完整性违规类型，再用 **SSA 静态分析 + 抽象调用图**自动检测。在 7 个开源应用中发现 **46 个之前未报告的完整性违规**，可扩展到 500 个微服务规模。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **Aletheia** | 微服务数据完整性违规的自动化静态检测工具 |
| **ER Model** (Entity-Relationship) | 抽象数据模型的经典形式化——描述实体之间的逻辑关系 |
| **Relational algebra** | 关系代数——用于精确定义跨服务数据的 relation 何时被破坏 |
| **SSA** (Static Single Assignment) | 编译器 IR 形式——每个变量仅被赋值一次，适合追踪数据流 |
| **Abstract call graph** | 微服务间 RPC/HTTP 调用的抽象图——用于追踪跨服务的请求-数据流链 |
| **Data integrity violation** | 跨服务数据之间的逻辑关系被应用代码破坏——没有数据库级的 foreign key 保护，完全依赖应用代码的正确性 |
| **Three canonical violation types** | Aletheia 形式化定义的三种基本违规模式——覆盖了跨服务场景下不同方式的完整性破坏 |

## 背景与动机

### 问题
- 微服务将单体数据库拆分为每个服务独立的异构存储系统
- **跨服务数据的逻辑关系**（如"订单"必须关联一个有效的"用户"）仍然存在，但：
  - 数据库级的 foreign key / constraint **不再可用**（因为数据分布在不同数据库中）
  - 这些关系完全由**应用代码手动维护**
- 随着微服务规模和复杂度的增长，这种手动维护在实践中几乎不可能完全正确

### 为什么现有工具不够
- 数据库 constraint enforcement：无法跨服务/跨数据库工作
- 运行时 monitoring：只能检测已经发生的违规（事后），且覆盖率有限
- 人工 code review：无法扩展到大规模微服务部署

### Aletheia 的定位
**静态分析**在部署前自动检测违规——用 ER 模型捕获跨服务数据的逻辑关系，再用关系代数精确定义"违规"的条件，最后通过 SSA 静态分析 + 抽象调用图自动检测。

## 方案介绍

### 三阶段方法

**1. 形式化违规模型**
- 基于 ER 模型定义跨服务实体之间的逻辑关系（如 User-Order, Product-Review）
- 用关系代数精确定义三种基本违规类型：
  1. Referential integrity violation：引用了一个不存在的实体
  2. Cardinality violation：违反了关系基数约束
  3. (第三类) — 论文中第三种形式化违规模式

**2. SSA 静态分析 + 抽象调用图**
- 使用 SSA 形式追踪每个微服务内部的数据流
- 构建跨服务的抽象调用图——建模 RPC/HTTP 调用链
- 沿调用图传播数据依赖 → 检测上述违规类型的模式

**3. 违规报告**
- 自动生成 bug report——哪个服务、哪个操作、违反了哪类完整性约束

## 证据与评估

| 指标 | 结果 |
|------|------|
| 分析的应用 | **7** 个开源微服务应用 |
| 发现的之前未报告违规 | **46** |
| 可扩展性 | 可处理最多 **500** 个微服务的调用图 |
| 方法 | 静态分析——部署前检测，非运行时 |

## 整体评估

### 真正的新意
1. **首次将 ER 模型 + 关系代数用于微服务的跨服务数据完整性分析**：将经典的数据库约束概念跨服务形式化——这是从 mono-DB 到 distributed-DB 的理论推广
2. **SSA + 抽象调用图的组合**：在编译器领域成熟的 SSA 应用于分布式系统的静态分析——跨领域组合
3. **定义了三类违规的形式化语义**：不是"找 bug"，而是"找特定形式化定义的违规"

### 可复用启发
- "经典形式化可以跨领域移植"：ER 模型 50 岁了，但在微服务场景下有全新的应用
- 微服务的数据完整性是**被严重低估的问题**：46 个违规在 7 个开源应用中表明这不是边缘现象
- SSA 不仅是编译器优化技术——它在跨服务分布式数据流分析中也有效
