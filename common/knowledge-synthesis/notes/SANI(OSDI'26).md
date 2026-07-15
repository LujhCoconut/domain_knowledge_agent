# SANI(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-sang.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 移动 AMP CPU 的不对称感知 DNN 推理——affinity-aware kernel issuer + adaptive granularity scheduler + on-demand kernel switcher，解决 performance-collapse paradox（加 LITTLE core 反而变慢）。延迟 -17.6-23.7%，能耗降 up to 39%。

## 核心问题

移动 SoC 的 AMP CPU（big+LITTLE）在 DNN 推理中面临 **performance-collapse paradox**——将算子拆分到所有核并行执行，反因为 big/LITTLE 不对称导致吞吐下降（最多 +37% 延迟）。根因是工作负载不平衡：big core 线程在 barrier 等 LITTLE core 线程完成。现有方案：对称执行（只用 big core，浪费 LITTLE）、静态 partition（不适应 runtime 干扰）、忽略 core-kernel affinity。

## 关键洞察

1. **"Affinity-aware kernel issuer"**：不是 naive 跨所有核分发→通过离线 profiling 发现每种 kernel 在各 core 上的最有效配对→优先匹配。类似 ADAngel "oracle policy map" 但应用于 core-kernel 匹配。
2. **"Adaptive granularity scheduler"**：动态融合/拆分任务，给小核 small tasks，给大核 large tasks→平衡异构核的工作量。类似 Ambulance "protocol-rigged racing"——用偏置使更快的一方承担更多工作。
3. **"On-demand kernel switcher"**：工作负载在 core 间迁移时高效转换 kernel→保持亲和性。

- 来源：SANI(OSDI'26)
