# Resource Scheduling & Provisioning

资源调度与动态供给的算法设计与系统实现。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 信号感知 DAG 调度与动态供给 | signal-aware scheduling, DAG relative importance, carbon-aware, online threshold policy, joint scheduling-provisioning | SPADE(OSDI'26) |
| 市场机制 ML 训练芯片分配 | dynamic pricing, market clearing, Pareto efficiency, max-min fairness, credits, heterogeneous values | Quota Marketplace(OSDI'26) |

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
