# VTC(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-hu-muyan.pdf
- **类型**: 论文-编译器
- **一句话 TL;DR**: Virtual Tensor——用 index mapping 跟踪数据移动替代物理 data transfer，首次消除全谱数据移动操作。比现有 ML 编译器快 up to 1.93× (avg 1.28×)，推理内存节省 up to 60% (avg 17.5%)。

## 核心问题

计算能力飞速增长（H100 ~1 PFLOPS），但内存带宽增长远远落后→memory-bound 成为瓶颈（尤其 LLM decode 阶段）。现有编译优化（layout transform、算子融合）只覆盖部分 data movement 操作→大量不必要的 global memory ↔ accelerator 数据传输被遗漏。

## 关键洞察

1. **"Virtual Tensor = index mapping 替代 data copy"**：不是将 producer 的 tensor 物理复制到 consumer，而是用 index mapping 描述它们之间的关系。只有当 compute 确实需要数据时才 lazily 按映射获取。类似 Duhu 的 "pass-by-reference 替代 pass-by-value"——改变编程抽象而非硬件。
2. **"与现有 kernel 和 fusion 无缝协作"**：不需要重写 operator kernel——virtual tensors 作为中间层透明优化。

- 来源：VTC(OSDI'26)

### 实践启发
- **"Virtual memory 的思想应用于 tensor compilation"**：Virtual tensor 类似虚拟内存的 lazy paging——不搬数据直到必须有。与 InfiniDefrag "GPA 是虚拟的" 共享思想
