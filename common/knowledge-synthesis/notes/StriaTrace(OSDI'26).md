# StriaTrace(OSDI'26)

- **来源**: OSDI '26 (Operational Systems Track), https://www.usenix.org/system/files/osdi26-wu-haonan.pdf
- **全称**: StriaTrace: Efficient Tracing and Diagnosis for Online LLM Inference
- **作者**: Haonan Wu (SJTU & Alibaba), Yanqing Chen, Kun Qian, Xue Li, Jingbo Xu, Erci Xu (SJTU), Ennan Zhai, Wenyuan Yu, Guangtao Xue, Jingren Zhou (Alibaba)
- **类型**: 论文-系统 (Operational Systems — LLM inference observability)
- **一句话 TL;DR**: LLM 在线推理的 tracing 和诊断面临两难：通用工具（TorchProfiler/Nsight）开销 10-20%→不能用；训练工具无法捕捉偶发性推理异常。StriaTrace 用三个生产原则（仅追踪同步点+关键路径+异常时详细追踪）+ 动态 roofline 模型 + 相关性诊断，将 tracing 开销降低 **97.8%**，诊断了数百异常跨越 **19 种不同根因**。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **StriaTrace** | 面向在线 LLM 推理的轻量级 tracing 和诊断系统 |
| **Key synchronization points** | LLM 推理 pipeline 中的同步点（等待 KV cache 加载、GEMM 完成、AllReduce barrier）— 最易发生延迟异常的位置 |
| **Critical path tracing** | 只追踪请求执行的关键路径而非全部操作 |
| **Abnormality-only detailed tracing** | 默认只采集轻量指标，仅在检测到异常时触发详细 trace |
| **Regression-based roofline model** | 基于历史数据构建的动态 roofline，用于判断当前延迟是"正常但慢"还是"异常" |
| **Correlation-based diagnosis** | 在异常期间自动关联多维指标（GPU util、KV cache hit rate、batch size、通信延迟），定位根因 |

## 背景与动机

### 问题
- LLM 推理的 SLO 是严格的（TTFT < 10s, TPOT < 100ms），偶发性的性能异常即可违反
- 生产 trace 显示：大多数请求平均 TTFT 3.06s、TPOT 24.83ms — 但 **P99 始终超过 SLO**
- 根本原因有两个：(1) LLM 推理是流式的，难以在离线测试中再现确切的工作负载；(2) 各种优化（prefix KV cache、PD disaggregation）虽然提高吞吐但也增加了诊断复杂度

### 现有方案的两个局限

| 局限 | 说明 |
|------|------|
| 通用 tracing 工具开销过高 | TorchProfiler/Nsight 开销 10-20% → 在严格 SLO 下不能持续运行 |
| 训练专用诊断工具不适用推理 | 训练工具（如 Mycroft 的固定阈值 straggler 检测）不能捕捉推理中偶发的、用户触发的异常 |

## 方案介绍

### 三个生产原则

1. **Key synchronization points tracing**: 只追踪 pipeline 中的同步点——prefill 开始、KV cache 加载完成、GEMM 完成、AllReduce barrier、decode step 完成——这些点最容易暴露延迟异常
2. **Critical path tracing**: 不追踪每个操作，只追踪请求执行的关键路径
3. **Abnormality-only detailed tracing**: 默认轻量采集（<1% overhead），仅在检测到指标异常时自动升级为详细 trace

### 诊断引擎

- **动态 Roofline 模型**: 基于回归的在线 roofline，用于判断当前延迟是"正常范围"还是"异常"
- **Correlation-based 诊断**: 在异常时自动关联 GPU util、KV cache hit rate、batch size、通信延迟等多维指标，定位根因

## 证据与评估

| 指标 | 数据 |
|------|------|
| Tracing 开销 | **降低 97.8%**（<1% vs 10-20% 替代方案） |
| 诊断的异常数量 | **数百** |
| 识别的不同根因类型 | **19 种** |
| 生产部署规模 | 2K 实例集群（Alibaba） |
| 典型 TTFT/TPOT | 3.06s / 24.83ms（平均），P99 持续超过 SLO |

## 可复用启发

- "默认轻量 + 异常时详细"是生产 tracing 的核心设计范式：不是全量采集，而是在异常发生时自动升级
- 同步点是最好的追踪目标：不需要追踪所有操作，LLM 推理管线的同步/barrier 点就已经暴露了大部分延迟异常
- Roofline model 不是只用于性能分析——也可用于异常检测（判断延迟是"正常变慢"还是"应该调查的异常"）
