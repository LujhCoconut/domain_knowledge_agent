# Resource Scheduling & Provisioning

资源调度与动态供给的算法设计与系统实现。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 信号感知 DAG 调度与动态供给 | signal-aware scheduling, DAG relative importance, carbon-aware, online threshold policy, joint scheduling-provisioning | SPADE(OSDI'26) |
| 市场机制 ML 训练芯片分配 | dynamic pricing, market clearing, Pareto efficiency, max-min fairness, credits, heterogeneous values | Quota Marketplace(OSDI'26) |
| Semi 信息感知抢占式 MLFQ 调度 | skip-join MLFQ, iteration-level preemption, semi information-agnostic, ENST, starvation prevention, head-of-line blocking | FastServe(NSDI'26) |
| 自动重写规则发现 (Superoptimization for SQL) | brute-force enumeration, SMT verification, query plan template, constraint-based rewriting, UNSAT trick, Calcite | WeTune(SIGMOD'22) |

---

## 信号感知 DAG 调度 (SPADE)

### 核心问题
数据中心扩张正撞上物理和环境天花板——碳强度、电价、可用功率等外部时变信号正变得与内部硬件容量同等重要。但现有系统是割裂的：传统 DAG 调度器（Spark FIFO/Fair、Decima、Graphene）假设稳定资源供给且完全信号无感；信号感知供给方案仅调整资源数量但不关心作业的 DAG 结构。两个决策是紧耦合的——在信号高时缩小资源如果恰好推迟了瓶颈任务，整个下游 pipeline 被阻塞。

### 关键洞察

1. **"相对重要性归一化"让瓶颈任务自然获得信号免疫**：rv,t = pv,t / maxu pu,t。瓶颈任务（最高分）始终 r=1 → 任何信号下都调度。低分任务 → r→0 → 仅低信号时调度。不需要理解底层 scorer 的具体逻辑，只需信任其排序。

2. **"指数型阈值函数有理论最优性"**：来自在线搜索理论的 one-way trading 问题——在时变价格下完成 N 次购买的最优策略是指数型保留价格曲线。在调度场景中："购买 unit" = "调度任务"，"价格" = "信号值"，"截止时间" = 队列不为空。

3. **"采样而非 argmax"是让 filter 有作用的前提**：如果总是取最高分任务（argmax），相对重要性永远为 1，阈值 φγ(1) = smax → 任何信号下都被调度。采样让低分任务有机会被选中 → 被 filter 推迟 → 在低信号窗口通过。

4. **"供给和调度必须联合优化"——通过 SAP ablation 证明**：仅根据信号设置 executor 配额（SAP）不知道哪个任务更重要，可能在高信号时缩减资源恰好阻塞瓶颈任务 → 严格劣于 SPADE。

- 来源：SPADE(OSDI'26)

### 实践启发
- **"相对重要性归一化"是通用调度 filter 设计模式**：适用于任何"在多个候选对象中做取舍"的场景——归一化到 [0,1] 后，top candidates 自然获得"免疫 filter"的优先级
- **"在线搜索理论 → 系统调度"是一个有生产力的迁移路径**：one-way trading 的指数型阈值在资源调度场景有自然对应，可推广到任何"离散决策 × 时变成本"的问题
- **"Ablation 作为论证手段"值得借鉴**：SAP 精心设计为"仅有供给无调度"，目的就是证明耦合的必要性——比随机 ablation 有力得多
- **γ 参数提供了一种比 deadline 更优雅的 trade-off 接口**：用户不需要为每个 job 指定截止时间，只需一个全局 γ ∈ [0,1] 控制"对环境信号的敏感度"
- **与 PowerSight 可协同**：PowerSight 预测功率限额 → SPADE 根据限额调度 DAG 作业 → 两个 OSDI '26 系统形成"预测→执行"链路

---

## 市场机制 ML 训练芯片分配 (Quota Marketplace)

### 核心问题
ML 训练芯片需求 8 年增长 100M 倍，但传统 static pools 每季度做一次人工分配决策——无法应对高度动态的需求（demo 爆发、会议冲刺）和供给波动（新硬件上线、serving clawback）。更根本的是，chip-hour 机制（如 Karma）假设所有工作负载价值相同——但不同工作负载的业务价值天然异构，且在组织层面必须区分优先级。

### 关键洞察

1. **"Credits 非零和 + 与资源类型/位置解耦"是 groundbreaking 抽象**：提高某团队优先级只需 mint 新 credit 并增加其 income——不需要从别人收回芯片。分配 committee 面对的是一维问题（谁有多少购买力）而非多维问题（哪种芯片、哪个位置、给谁多少）。类似央行——发币不影响总购买力（market weights 锚定）。

2. **"成本混合曲线"处理自有 vs 共享资源的定价**：拥有自有芯片的池享受内部折扣（prk = pr* · zrk/(srk+zrk)）。随着对共享市场的依赖增加，边际价格趋近全局参考价——类似能源市场。

3. **"价格作为拥塞信号"实现自动负载均衡**：H100 价格高 → 团队自动考虑旧芯片或低负载 cell → 无需中心化拓扑规划。价格信息本身就在引导资源使用去拥塞。

4. **"自动化竞价"是市场机制获取用户采纳的关键**：用户只需调整优先级队列，default settings 在大多数场景下工作良好。如果要求用户每次手动出价，市场机制会因为认知负担而失败。

5. **理论证明 chip-hour 在异构价值下失效**：Karma 等机制在 bi-valued instances（HIGH/LOW 两档）下就无法同时保证 Pareto 效率和 max-min 公平性——而 QM 可以。

- 来源：Quota Marketplace(OSDI'26)

### 实践启发
- **"非零和 credits"是稀缺资源分配的新范式**：传统思维是"分蛋糕"（零和），credits 将其转化为"印钞票"（非零和+market weights 锚定总量）。适用于任何"长周期人工分配 → 需动态自动化"的资源场景。
- **市场机制的 user adoption 关键不是经济理论，而是 UX 自动化**：QM 的 automated bidder + default settings 让大多数用户无需理解定价算法即可受益——这是市场机制从学术走向产品的关键设计决策。
- **价格信息作为透明信号的价值常被低估**：dashboard 展示实时价格+历史 → 团队自己就能做出更优的资源使用决策，不需要中心化调度器理解每项工作的机会成本。
- **Nested binary search 可以在实际系统中运行**：三层定价方程在理论上看起来复杂，但 binary search + 正确预处理后几乎线性时间可解——每 ~1 分钟一次的 frequency 完全可行。

---

## Semi 信息感知抢占式 MLFQ 调度 (FastServe)

### 核心问题
调度问题一般有三类设定：全知（SRPT，需预知 job size）、全盲（经典 MLFQ，零先验知识）、semi 盲（部分信息已知）。LLM 推理的调度恰好落在 semi 盲区——input length 已知（可精确 profile prefill 时间）但 output length 未知。经典 MLFQ 假设全盲 → 所有 job 从最高优先级开始 → 但在 LLM 中 prefill 时间长 → 第一轮 quantum 就耗尽 → 要么抢占（浪费 prefill 计算）要么不抢占（违反 MLFQ 语义 → HOL blocking 重现）。需要一种利用已知 input length 信息但又不需要预测 output length 的 MLFQ 变体。

### 关键洞察

1. **"Skip-join = 用确定性信息替代 ML 预测 → 在 MLFQ 框架中优雅嵌入已知信息"**：不是预测 output length（高 variance、不能用 ML 可靠预测），而是利用 deterministic prefill time → 新 job 直接 skip-join 到 `q_i ≥ t_prefill` 的最高优先级队列 → 跳过不必要的高优先级队列 → 消除 prefill 时的两难抉择。

2. **"MLFQ 的 quantum 设置与 LLM 的两阶段执行天然契合"**：最小 quantum = 最小 decode iteration time → prefill (长) > 最小 quantum → skip-join 自然将其放在低优先级。Decode tokens (< quantum) 自然保持在高优先级。不需要特殊处理两阶段——quantum 的值本身就编码了"prefill=长, decode=短"的信息。

3. **"Starvation prevention 是 tail latency 的保障——不是 MLFQ 的附加功能而是核心组件"**：periodic promotion to Q1 → 确保长 job 不会被永久饥饿。α=300ms 的选择基于 SLO（用户可容忍的延迟上限）。这个设计证明了"抢占式调度 + 公平性保障"可以在 LLM serving 中共存。

4. **"Skip-join MLFQ 在不同 input/output ratio (0.25–256×) 下始终最优"**：这一实验设计回答了 "如果用 fixed priority (by input length) 会怎样" 和 "如果用 naive MLFQ (全盲) 会怎样"——证明了 semi 盲是 LLM serving 的正确信息设定。

- 来源：FastServe(NSDI'26)

### 实践启发
- **"Semi information-agnostic 是一个被忽视的调度问题类"**：全知和全盲已经被大量研究，但很多实际系统恰好处于中间——部分信息已知、部分需要学习。FastServe 的 skip-join 是一个通用的半信息嵌入模式。
- **"MLFQ 的 quantum 设置如果与工作负载的自然阶段边界对齐，可以消除显式的阶段检测"**：FastServe 不需要显式区 prefill/decode——quantum 的值自动完成了这一区分。这是 MLFQ 设计的深层智慧：用时间窗口（而非显式分类）做调度决策。
- **"SPADE 的 relative importance 归一化和 FastServe 的 ENST 共享同一设计哲学"**：两个 NSDI/OSDI '26 调度论文都使用"综合多个信号到一个标量 ranking"的方法——SPADE 用 relative importance 归一化、FastServe 用 ENST 综合 promotion deadline + execution pipeline —— 都是将多维调度问题降维为单标量排序。
- **"抢占式调度在 GPU 上的可行性已经被 OS-level (Nixie) 和 application-level (FastServe) 两条路径验证"**：Nixie 在 consumer GPU 上做 temporal multiplexing、FastServe 在 datacenter GPU 上做 iteration-level preemption——两者互补。共同证明：GPU 不是"不可抢占"的。

---

## 自动重写规则发现：Superoptimization for SQL (WeTune)

### 核心问题
数据库查询重写规则（如 "outer join → inner join when NOT NULL constraint exists"）是查询优化的核心，但现有规则全部由专家手工编写，积累缓慢（数十年只有有限规则集）。ORM 框架（Rails ActiveRecord / Hibernate）生成的 SQL 常产生反直觉模式 → 手工规则无法覆盖 → 真实 Web 应用中 54% 的性能问题查询无法被最新 SQL Server 自动优化。核心挑战：如何自动发现"通用"的重写规则（不绑定具体表名/列名）而非具体查询的等价变换？

### 关键洞察

1. **"Superoptimization 方法论从编译器迁移到 SQL"**：编译器 peephole optimizer 穷举搜索所有可能的等价指令序列 → WeTune 穷举搜索所有可能的 query plan templates（size ≤ 4 operators → 3113 distinct templates）→ 对每对模板枚举所有约束组合 → SMT 验证等价性 → 筛选出可提升性能的规则。关键迁移难点：SQL 规则不能绑定具体表名/列名 → 引入符号化模板 + 约束集合。

2. **"规则 = conditional equivalence: 𝐶 ⇒ 𝑞_src ≡ 𝑞_dest"**：不等价是无条件的——需要当某些 schema 属性满足时才等价。约束集合 C 编码了外键关系（RefAttrs）、唯一约束（Unique）、非空约束（NotNull）等 → 这些约束让规则可以编码 "外键 → join 消除" "唯一约束 → distinct 消除" 等 schema-aware 优化。

3. **"证明 negated formula UNSAT 比证明 tautology 快得多"**：传统等价性验证需证明 `C ⇒ ∀t.q_src(t) = q_dest(t)` 在所有 interpretation 和 tuple 下成立 → SMT solver 需穷举。WeTune 改为证明 `¬(C ⇒ ∀t.q_src(t) = q_dest(t))` UNSAT → solver 找到 contradiction 即停 → 对正确规则几乎总是快速。实证：73/232 已知正确规则无 timeout 验证通过。

4. **"Interesting constraints heuristic 是使大规模枚举可行的关键"**：全部约束组合是组合爆炸的（~10⁶ pairs × exponential constraints）。WeTune 只枚举"有意义的"约束——即关联两个模板间表和属性的约束（RelEq、AttrsEq、SubAttrs 等）→ 大幅缩小搜索空间。

5. **"保守 timeout = false：安全关键系统的正确工程选择"**：当 SMT solver timeout → 保守视为规则不正确 → 牺牲 recall（可能漏掉正确但复杂的规则）换 precision（绝不让错误规则进入数据库）。100 条故意制造的错误规则中仅 4 条被成功判定为错误 → 96 条 timeout → 证明了保守策略的有效性。

- 来源：WeTune(SIGMOD'22)

### 实践启发
- **"Superoptimization 是可迁移的方法论"**：任何需要"自动发现等价变换规则"的领域都适用——API 调用组合优化、数据流图重写、ML 计算图优化（类似 TASO 在 DL compiler 中的工作）。核心模式：穷举候选 → 验证等价 → 筛选有用。
- **"约束集合 = 条件等价性——推广了 traditional rewriting"**：传统重写是 `A ≡ B`（无条件），WeTune 的范式是 `C ⇒ A ≡ B`（条件等价）。这类规则更强大——可以表达 "只有在满足外键约束时才有效" 的优化。可推广到任何 conditional optimization domain（编译器、网络策略、安全策略）。
- **"UNSAT > tautology 的 SMT 技巧不限于查询等价性"**：任何 "证明 A ⇒ B" 的问题 → 尝试 "证明 ¬(A ⇒ B) UNSAT" → solver 更容易找 contradiction。适用于形式化验证、程序合成、policy verification 等场景。
- **"时间换空间的搜索策略"**：36 小时 × 120 cores 的一次性离线计算 → 产出 43 条永久可用的规则 → 边际成本极低。类似 Drs.NAS "zero-cost proxy 替代训练验证"——用大规模离线计算换取在线零成本。
- **"枚举所有 + 验证 + 真实负载筛选 = 自动知识发现的标准三阶段架构"**：类似 FastServe "枚举调度策略 + 验证正确性 + 真实负载测试"。三阶段各有职责：阶段 1 宽进（穷举）、阶段 2 严出（形式化验证）、阶段 3 真用（经验验证 → 筛选）。可推广到任何 "从大量候选中筛选少量金标准" 的应用。
