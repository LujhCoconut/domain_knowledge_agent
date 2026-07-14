# POEGA(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-zhang-yunmo.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: GPU-centric 演化图分析框架——proxy graph 减少 OOM I/O + fused kernel 并发处理多 snapshot + bound-based pruning + adaptive state compaction，比 SOTA 快 3.7-23.5×。

## 核心问题

演化图分析 (EGA) 需对图快照序列评估查询。GPU 快但显存有限——增量计算的 I/O 瓶颈使现有 GPU EGA 无法扩展到大规模图。

## 方案

1. **Proxy graph**：在 GPU 内存中保留紧凑的代理图（保留计算关键结构），先近似计算 → 再精确定位需访问的完整图部分 → 显著减少 I/O
2. **Fused kernel 并发处理多 snapshot**：用 GPU 大规模并行性摊销 proxy graph 的额外计算开销——fuse 多个 snapshot 的计算到单个 kernel
3. **Bound-based pruning**：运行时按边界剪枝冗余的跨 snapshot 工作
4. **Adaptive multi-version state compaction**：压缩多版本顶点状态，解决大量 snapshot 并发分析时的内存压力

## 可复用启发
- **"用 approximate computation 换 I/O，再并行化摊销 compute 开销"**：proxy graph = approximate 结果 guide out-of-memory refinement。类似 DINGO（声明式 IO 换维护 I/O 减少）——用某种资源（计算/灵活性）换瓶颈资源（I/O）的通用策略
- 来源：POEGA(OSDI'26)
