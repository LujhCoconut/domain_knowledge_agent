# Cache Algorithms

缓存淘汰算法与准入策略。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 自适应缓存淘汰 | per-object characterization, adaptive eviction, decoupled components, access patterns, multi-core scalability, hit rate | Merlin(OSDI'26) |

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
