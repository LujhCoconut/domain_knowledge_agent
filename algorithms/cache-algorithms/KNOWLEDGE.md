# Cache Algorithms

缓存淘汰算法与准入策略。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 自适应缓存淘汰 | per-object characterization, adaptive eviction, decoupled components, access patterns, multi-core scalability, hit rate | Merlin(OSDI'26) |
| 学习增强启发式缓存淘汰 | learning-augmented heuristics, data-control plane separation, cache-level learning, S4-FIFO, static heuristic + ML | S4-FIFO/LAH(OSDI'26) |

---

## 自适应缓存淘汰 (Merlin)

### 核心问题
现代工作负载访问模式多样且快速变化（LFU-friendly、recency、churn、scan），现有自适应淘汰算法（ARC/CAR/Cacheus）只在少数典型模式上生效→在其他模式上甚至不如静态算法（如 S3-FIFO/LIRS）。根本原因：(1) 特征化仅在粗粒度分类级别（将 workload 归类为 4 种之一）→无法捕捉混合模式的微妙组合 (2) 通过在互补算法间切换做 policy adjustment→算法间互相干扰→cost of adaptivity > benefit。

### 关键洞察

1. **"Per-object 级细粒度特征化替代粗粒度分类"**：不是将整个 workload 分为 4 类→每个对象独立特征化，同时考虑访问局部性（access locality）和缓存大小（cache size）→表达全谱访问模式。类似 Kareus "per-kernel execution schedule"——从粗到细粒度控制。
2. **"组件职责解耦替代 policy switching"**：每个组件做单一任务（识别 access pattern、估计对象价值、决定淘汰顺序）→消除切换基础算法带来的互相干扰。类似 Ambulance "proposal lane"——不是竞争切换，而是职责分离。
3. **"低开销 + 高多核可扩展性使 adaptivity 值得付出"**：此前自适应淘汰的主要问题是 overhead 吞噬 hit rate 收益——Merlin 证明 adaptivity 的复杂性成本可以低于收益。

- 来源：Merlin(OSDI'26)

### 实践启发
- **"Fine-grained per-object > coarse-grained workload classification"**：不仅是缓存淘汰——任何自适应系统都应考虑 per-entity 而非 per-workload 的感知粒度
- **"Policy switching 的 hidden cost——算法间干扰"**：在两个互补算法间切换看似合理，但切换边界本身引入的干扰可能大于收益——职责解耦是更好的方案

---

## 学习增强启发式缓存淘汰 (S4-FIFO / LAH)

### 核心问题
缓存淘汰算法分为两类：静态启发（S3-FIFO/LRU/2Q——简单、可预测、工业采用）和智能算法（ARC/LRB/LHD——自适应但复杂性高、易不稳定、几乎未被工业采用）。核心矛盾：智能算法理论上应同时提高效率和鲁棒性，但实践中受 objective mismatch（学习目标 ≠ 缓存真实性能指标）和 instability（在某些 trace 上大幅变差）困扰——导致在最差 trace 上 miss ratio 甚至超过简单 FIFO。

### 关键洞察

1. **"Learning-Augmented Heuristics = 数据面+控制面解耦"**：不是让学习取代启发式——是静态启发在数据面做快速读写（simple、fast、predictable），控制面异步学习 cache 级参数（occasional、non-blocking）。这是数据-控制分离在缓存领域的应用——类似 UCCL-Tran "data plane + control plane"。
2. **"Cache-level learning > object-level learning——更稳健"**：per-object 预测（如 reuse distance、未来访问概率）对单个对象可能错误，导致灾难性错误淘汰。Cache 级参数学习（如 ghost cache 大小、插入位置、晋升阈值）即便不精确也只造成边界性能损失。**Learning at the right granularity matters more than learning power。**
3. **"单模型预训练 + 嵌入静态启发 = 零 per-workload tuning"**：4140 production traces 上预训练一个模型→嵌入 S4-FIFO→1035 evaluation traces 上无需 per-workload 调参。效率 +26%（vs S3-FIFO），+8%（vs 3L-Cache best SOTA），最差 trace miss ratio 仅增加 0.8%（vs 3L-Cache 8.8%）。

- 来源：S4-FIFO / LAH(OSDI'26)

### 实践启发
- **"学习增强而非学习替代"**：不是用 ML 替换启发式→增强启发式的参数。工业采用的门槛是：不能比现有方案更差（robustness）+ 不能太复杂（simplicity）+ 不需要 per-workload 调优。LAH 同时满足三个。类似 GraCE "编译器增强 CUDA Graph 而非替代"——增强 > 替代是工业采用的务实哲学
- **"Cache-level parameter learning vs object-level prediction"——粒度选择决定稳健性**：与 Merlin "per-object characterization" 形成有趣对比——两者都是 OSDI '26 的缓存论文但选择相反粒度（object-level vs cache-level）。两者互补：Merlin 提供细粒度，LAH 提供稳健性。最佳选择取决于部署场景对稳健性的要求
