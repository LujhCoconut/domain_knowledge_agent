# ADAngel(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-liu-yao.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: DPR 计算模型将任意精度混合 GEMM 分解为部分积重构——运行时根据任务 shape/bit-width 自适应选择最优 kernel，decode 比 llama.cpp 快 up to 5.10×，prefill 比 TensorRT-LLM 快 1.17-2.38×。

## 核心问题

APQ（任意精度量化，如 W4A8）是边缘 LLM 推理的关键技术。但现有边缘硬件缺乏原生混合精度支持。三种方案各有局限：Padding（upcast 低位→浪费带宽）、LUT（预计算表→内存开销大）、Bit-disaggregation（1-bit 分解→固定范式不适应 shape/bit-width 变化）。**没有一个方案适应 LLM 推理中 GEMM 任务的异构性**（prefill vs decode、不同 shape/bit-width 组合）。

## 关键洞察

1. **"DPR (Decomposition-Partial Product-Reconstruction) 计算模型"**：系统化地通过不同 bit-partition 方案生成多种 mpGEMM 算法→不是硬选一个范式。
2. **"Computation Strategy Set + Oracle Policy Map"**：预生成多种高度优化的 kernel→离线穷举分析→运行时轻量 dispatcher 根据任务 shape/bit-width 选择最优→接近零 overhead。
3. **"Prefill vs Decode 需要不同策略"**：prefill = compute-bound GEMM，decode = memory-bound GEMV。同一 LLM 推理内两个阶段的优化目标完全不同→adaptive mapping 是必须的。

- 来源：ADAngel(OSDI'26)

### 实践启发
- **"Bit-partition 生成多策略 + runtime dispatch"** 是异构硬件的通用优化模式——类似 Kareus 的 "execution schedule 搜索 + 运行时选择"
