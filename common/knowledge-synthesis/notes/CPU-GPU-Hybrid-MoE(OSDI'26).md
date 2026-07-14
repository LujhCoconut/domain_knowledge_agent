# CPU-GPU Hybrid MoE (OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-wang-wenxin.pdf
- **全称**: Achieving Cloud-Grade SLOs for Local Mixture-of-Experts Inference through CPU–GPU Hybrid Design
- **作者**: Wenxin Wang (Tsinghua), Yule Hou, Yu Ji (Xingyun IC), Peng Qu, Youhui Zhang (Tsinghua & BNRist)
- **类型**: 论文-系统 (LLM inference + CPU-GPU hybrid architecture)
- **一句话 TL;DR**: 本地部署 MoE 大模型即便在低并发下也无法达到云级 SLO：12K+ prompt 超 30s TTFT 限制、decode 吞吐 <20 tokens/s、并发能力差。通过 CPU-GPU 混合架构实现云级 SLO：SLP (stream-loading prefill) 将 prefill 提升至 **1,200 tokens/s** 使 32K prompt 在 30s 内完成；分布式 SLP + SmallEP 在双 RTX 5090 上达 **1,800 tokens/s**，45K prompt 在 30s 内完成；CPU native FP8 推理另交付 **4-5×** 更低延迟。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **SLP** (Stream-Loading Prefill) | 流式加载 prefill——动态加载模型层到 GPU，处理长序列时避免预加载全模型 |
| **DSLP** (Distributed SLP) | 多 GPU 的分布式 SLP——与 SmallEP expert parallelism 集成 |
| **SmallEP** | 轻量级 expert parallelism——将 MoE expert 分布在多 GPU 间 |
| **Dual-batch attention–MoE overlap** | 双批次注意力-MoE 重叠——同时处理两个批次以隐藏延迟 |
| **CPU native FP8** | 在 CPU 上原生执行 FP8 运算——消除 GPU offload 延迟 |

## 核心洞察

本地 MoE 部署的**四个关键差距**：压缩模型质量让步、长 prefill 超时（>12K→>30s）、低 decode 吞吐（<20 tok/s）、混合 prefill-decode 并发差。CPU-GPU 混合设计填补了这些差距——关键不是"加速 compute"，而是**流体化数据流**（SLP 使 prefill 在层加载中进行而非等待），和**混合精度执行**（CPU FP8 消除 GPU offload 延迟）。

## 关键结果

| 指标 | 结果 |
|------|------|
| 单 GPU SLP | **1,200 tok/s**, 32K prompt in 30s |
| 双 GPU DSLP+SmallEP | **1,800 tok/s**, 45K prompt in 30s |
| CPU FP8 | **4-5×** lower latency |
| Decode 吞吐 | 从 <20→sustained throughput |

## 可复用启发

- "Stream-loading"范式可推广到任何"模型太大、layer 需要动态加载"的场景——不是减小模型，而是流体化加载
- CPU-GPU 混合推理在本地/边缘场景下比纯 GPU 方案更实用——利用现有硬件（双路 CPU + 消费级 GPU）
- FP8 在 CPU 上的 speedup（4-5×）是未充分探索的维度——通常 FP8 讨论聚焦 GPU
