# qTPU(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-tornow.pdf
- **类型**: 论文-系统/加速器
- **一句话 TL;DR**: 混合量子-经典张量网络 (hTN) 抽象——统一表达量子+经典计算，qTPU 编译器平衡经典成本与量子误差，runtime 跨异构 QPU+GPU/TPU 可扩展执行。经典 overhead 降 3-4 数量级，端到端加速 20×+。

## 核心问题

经典加速器 (GPU/TPU) 无法高效表示指数扩展的问题（如量子纠缠态）；QPU 适合但噪声大、错误率高、吞吐极低。实际应用需要**混合量子-经典执行**——但现有编程范式是 ad hoc 的手工 partition+orchestrate，缺乏统一抽象，无法做跨边界全局优化。

## 关键洞察

1. **"hTN (hybrid tensor network)——统一量子-经典计算的单一抽象"**：不仅是张量网络，是捕获量子 *和* 经典计算关系的统一表示。类似 VTC "virtual tensor" 但跨 quantum/classical 边界。
2. **"编译器平衡经典成本与量子误差"**：不是单纯最小化经典开销——当经典端多做些计算可以减少量子端误差时，编译器会做这个 trade-off。
3. **"Declarative specification → holistic optimization"**：声明式编程→编译器跨量子-经典边界做全局优化，类似于 compiler-driven approaches 在 classical domain（Twill/GraCE/MPK）。

- 来源：qTPU(OSDI'26)
