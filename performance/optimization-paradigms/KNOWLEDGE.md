# Optimization Paradigms

偏 research 与方法论：如何系统性地优化串行、并行、并发程序。

这里的 skill 不聚焦某个具体系统（如 Linux、数据库），而是聚焦**程序形态**与**优化范式**。

## 子目录

| 目录 | 主题 | 适合归档的内容 |
|------|------|----------------|
| `serial-optimization/` | 串行优化 | 算法复杂度、缓存友好性、向量化、编译器优化、I/O 与计算重叠、延迟隐藏 |
| `parallel-optimization/` | 并行优化 | 数据并行、任务并行、流水线、负载均衡、通信开销、Amdahl/Gustafson 定律、扩展性分析 |
| `concurrent-optimization/` | 并发优化 | 锁粒度、无锁结构、读写分离、事务内存、协程调度、上下文切换、竞争避免 |
| `parallelism-concurrency-models/` | 并发并行模型 | CSP、Actor、Fork-Join、MapReduce、SPMD、SIMT、流式计算模型对比 |

## 与 `concurrency/`、`parallel/` 的区别

- `concurrency/`、`parallel/`：侧重**概念、模型、机制**（是什么）。
- `optimization-paradigms/*-optimization/`：侧重**怎么优化、优化策略、案例**（怎么做）。

## 写作建议

- 每个 skill 建议包含：问题定义 → 瓶颈模型 → 优化策略 → 典型代码/伪代码 → 效果评估。
- 鼓励使用「定律 + 量化 + 反例」的方式组织内容，避免变成 API 使用说明。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| Superoptimization 范式 SQL 重写规则发现 | brute-force enumeration, SMT verification, query plan template, conditional equivalence, constraint-based rewriting, UNSAT trick | WeTune(SIGMOD'22) |

---

## Superoptimization 范式 SQL 重写规则发现 (WeTune)

### 核心问题
数据库查询重写规则全部由专家手工编写→积累缓慢→ORM生成的"反直觉"SQL模式(54%真实性能问题查询)无法被现有优化器覆盖。需要一种自动发现新规则的方法论，既能保证等价性(formal correctness)、又能产生通用规则(generic over tables/columns)。

### 关键洞察

1. **"编译器 superoptimization 方法论可迁移到 SQL 领域"**：穷举所有候选 query plan templates(size≤4→3113个)→枚举模板对+约束组合→SMT验证等价性→真实查询验证实用性。关键差异：SQL规则需要是generic的→引入符号化模板+约束集合。

2. **"Constraint-based conditional equivalence: C⇒q_src≡q_dest"**：规则不是无条件的等价性→而是"当某些schema属性(外键/唯一约束/NOT NULL)满足时"等价→编码了"外键→join消除""唯一约束→distinct消除"等schema-aware优化。

3. **"UNSAT证明技巧：证明negation UNSAT远快于证明tautology"**：将等价性验证从"证明C⇒q_src≡q_dest对所有interpretation和tuple成立"转为"证明其否定UNSAT"→solver找到contradiction即停→73/232已知正确规则无timeout。

4. **"三阶段筛选架构：枚举(宽进)→形式化验证(严出)→真实负载(精筛)"**：3113 templates→1106 promising & non-reducible rules→43 useful rules→优化247条真实查询。36小时×120核一次性计算→规则永久使用。

- 来源：WeTune(SIGMOD'22)

### 实践启发
- **"大规模离线搜索+形式化验证=自动知识发现的可复用范式"**：类似编译器superoptimization和Drs.NAS的NAS→离线cost换在线零cost。任何需要"自动发现高质量规则/模式"的领域都可应用
- **"条件等价性>无条件等价性"**：传统重写是A≡B(无条件)→WeTune范式是C⇒A≡B(条件等价)→更多优化机会。可推广到任何conditional optimization domain
- **"保守的timeout=false策略是correctness-critical systems的正确选择"**：宁可漏报不可误报→牺牲recall换precision。适用于任何自动生成的程序变换规则系统
