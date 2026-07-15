# Spain(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-destefano.pdf
- **类型**: 论文-安全/密码学
- **一句话 TL;DR**: 数值计算的 succinct proof——允许约束近似满足（reflect numerical approximation），新证明协议+新编译方法。比自然基线改进多个数量级。

## 核心问题

Succinct proofs (ZK/execution integrity) 需要将计算翻译为有限域上的约束——但数值计算（浮点/定点近似实数）根本不在有限域中有自然表达。现有方案：要么做特殊化编码（失去通用性），要么做 end-to-end 专用协议（失去通用性+性能）。**语义鸿沟导致 LLM 训练/推理、物理模拟等数值工作负载无法从 succinct proofs 中受益。**

## 关键洞察

1. **"数值计算的近似误差是机会而非障碍"**：既然数值计算本身就有近似误差，约束系统也应允许**近似满足**（而非精确满足）→大幅降低证明生成开销。这是将数值特性转化为协议优势而非绕过。
2. **"新证明协议专为近似约束设计"**：不同于传统 SNARK/STARK 要求约束 exact satisfaction，Spain 的协议处理 "approximately satisfied" 约束。
3. **"通用但高效的数值编译"**：不开特殊化后门，核心协议不依赖具体计算——数值程序的任何变化不需要重做底层数学。

- 来源：Spain(OSDI'26)
