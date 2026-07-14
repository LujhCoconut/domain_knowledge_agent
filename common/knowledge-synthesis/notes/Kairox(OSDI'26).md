# Kairox(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-jiang-yapeng.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 在线 neuron balancing——动态在 GPU 和 CPU 之间根据激活模式重新分配 FFN 神经元，consumer GPU 上比 llama.cpp 快 3.15-3.93× (geomean)，比稀疏化 baseline 快 ~2.1×。

## 核心问题

Hybrid CPU-GPU LLM 推理中 CPU 计算能力弱成为瓶颈。静态 sparse offloading（PowerInfer 等）基于离线 profiling 将"热"神经元放 GPU、"冷"神经元放 CPU，但**运行时激活模式会变化**——静态 partition 无法适应→suboptimal throughput。

## 关键洞察

1. **"Online neuron balancing 替代 static partitioning"**：预测下一层激活模式→prefetch 需要 GPU 执行的神经元→overlap 数据传输与 computation。类似 FlowANN 的 discovery-expansion window 和 BatchGen 的 coroutine yield——找到"可以异步做的事"。
2. **"Temporal Activation Momentum (TAM)"**：捕获激活的 temporal persistence→区分有用神经元和短暂尖峰→避免 thrashing。类似 cache replacement 的 LFU/LRU 逻辑但针对 activation pattern。
3. **"Live Pipeline"**：在 layer i 的 Attention 阶段就预测 FFN 激活模式→提前开始 I/O→隐藏 PCIe 延迟。
4. **"Adaptive Neuron Balancer"**：实时调整 balancing 强度——CPU workload vs I/O overhead→保持最优均衡点。

- 来源：Kairox(OSDI'26)

### 实践启发
- **"Prefetch based on activation prediction" = 类似 instruction prefetching 但针对 neurons**：可用 activation locality 预测下一层需要哪些权重
- **"TAM = temporal persistence filter"**：短暂激活不值得迁移到 GPU——类似 page replacement 中的"don't swap pages that are about to be freed"
