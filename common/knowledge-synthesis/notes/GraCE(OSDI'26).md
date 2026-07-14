# GraCE(OSDI'26)

- **来源**: https://www.usenix.org/conference/osdi26/presentation/ghosh (PDF: osdi26-ghosh.pdf)
- **类型**: 论文-编译器/系统
- **一句话 TL;DR**: CUDA Graph 感知的编译器框架——自动代码变换+参数间接化+cost-benefit 分析，**比 PyTorch2 的 CUDA Graph 收益翻倍**，无需程序员干预。

## 核心问题

ML 工作负载每次迭代 launch 数百个短 GPU kernel，每个 kernel 从 CPU 提交需 5-10µs。GPU 计算速度超过 CPU 提交速度→GPU 利用率 <50%（阿里/Azure 报告）。CUDA Graphs 将多个 kernel 捕获为单图→一次 dispatch 重放→消除 per-kernel launch 开销。但**实际部署 CUDA Graph 惊人困难**：(1) 程序不是面向 Graph 编写的（tensor 地址硬编码→de-allocation 后 crash；scalar parameter 值固化→跨迭代失效）(2) 即使能部署，parameter copy 开销也吞噬收益 (3) 盲目全局启用会导致部分应用变慢。

## 关键洞察

1. **"CUDA Graph-aware code transformation"**：编译器分析 IR→找到 Graph-oblivious 模式（如 CPU tensor → GPU memcopy、scalar 参数）→自动变换 IR 使 Graph 可用。类似 MPK 的 "自动 mega-kernelize"——不需要程序员手动适配硬件特性。
2. **"Indirect parameter passing"**：Tensor copy → pointer copy（数 KB → 8B）→大幅减少 CUDA Graph 的 parameter overhead。JIT 编译 kernel 自动 de-reference；vendor kernel 通过 prelude kernel 完成。
3. **"Cost-benefit guided deployment"**：自动 profiling 分析→仅对收益正的 kernel 启用 Graph→避免盲目全局应用导致的性能退化。

- 来源：GraCE(OSDI'26)

### 实践启发
- **"编译器桥接高层语义和底层硬件特性的 gap"**：PyTorch 程序离 CUDA Graph 有语义距离→编译器可以自动填补。类似 Twill "约束求解自动适配新架构"
- **"不是所有优化都需要全局启用"**：cost-benefit analysis 识别哪些 kernel 从 Graph 中获益→类似 Kareus "auto fallback to sequential"
