# Merlin(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-li-liujia.pdf
- **类型**: 论文-算法/系统
- **一句话 TL;DR**: 细粒度对象级自适应缓存淘汰——per-object 特征化覆盖全谱访问模式而非少数典型类型，组件职责解耦消除 base algorithm 间干扰。5423 traces 上 hit rate 稳健改善，吞吐 1.4-7.8×。

## 核心问题

现代工作负载访问模式多样且快速变化（LFU-friendly/recency/churn/scan），现有自适应淘汰算法（ARC/CAR/Cacheus）只适配少数典型模式→在其他模式上甚至差于静态算法。根本原因：(1) 特征化仅在粗粒度分类级别 (2) 通过在互补算法间切换做 policy adjustment→算法间互相干扰。

## 关键洞察

1. **"Per-object 级细粒度特征化替代粗粒度分类"**：不是将 workload 分为 4 类→每个对象独立特征化，同时考虑 access locality 和 cache size→表达全谱访问模式。
2. **"组件职责解耦替代 policy switching"**：每个组件做单一任务→消除 switching 带来的算法间干扰。类似 Ambulance "proposal lane"——不是竞争切换，而是职责分离。
3. **"低开销 + 高多核可扩展性"**：使自适应淘汰的复杂性成本 < 收益——以前自适应淘汰的最大问题是 overhead 吞噬了 hit rate 收益。

- 来源：Merlin(OSDI'26)
