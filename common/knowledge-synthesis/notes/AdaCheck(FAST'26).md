# AdaCheck(FAST'26)

- **来源**: https://www.usenix.org/system/files/fast26-liu-weijie.pdf, FAST '26
- **作者**: Weijie Liu, Shengwei Li, Zhiquan Lai, Keshi Ge (NUDT), Qiaoling Chen (NTU), Peng Sun (Shanghai AI Lab), Dongsheng Li, Kai Lu (NUDT)
- **一句话 TL;DR**: LLM 训练自适应 checkpointing——通过 **tensor redundancy 抽象** (离线分析并行策略+模型架构的状态冗余) + **hash-based 三阶段通信压缩** (meta-check→hash→ring broadcast) + **online redundancy** (仅存 gradient 而非完整 state) , checkpoint size **-6.00~896×**, checkpoint frequency **+1.46~111×** vs SOTA。

## 核心问题

LLM 训练故障频繁 (LLaMA 3.1 16K GPUs 54天=419 failures, avg 3h/failure)。现有 checkpointing 不能同时做到: (1) 适应多种并行策略(ZeRO/MiCS/auto-planner)和模型架构(dense/MoE/MLA); (2) 识别并利用状态冗余(>90% 状态是冗余的，不需要全存); (3) 支持 1S1C(每步一 checkpoint)→近零故障恢复开销。

## 方案设计

### Tensor Redundancy 抽象

模型状态(parameters + optimizer states)视为 tensor 的多副本分布→通过分析 tensor redundancy 精确确定哪些 worker 的哪些状态需要保存。

### Offline Redundancy Utilization

- 构建 fault domain map(worker→node)→确保每个 tensor 至少有一个副本在 checkpoint 中(容忍单节点故障)
- 考虑 parameter-optimizer state 的关联(两者必须同时可恢复)

### Efficient Redundancy Detector (三阶段)

- Phase 1: **Meta-check** → 仅比较 tensor metadata(shape/dtype/version) → 快速排除不同 tensor
- Phase 2: **Hash-based** → 对相同 meta 的 tensor 计算 hash→缩小比较范围
- Phase 3: **Ring-based communication** → 环形拓扑并行 broadcast tensor 信息，避免 O(N²) pair-wise

128 workers → <3min。

### Online Redundancy Utilization (1S1C)

观察: 相邻 iteration 的 checkpoint 差异仅在于 **half-precision gradient** → 不存完整 model state，只存 gradient(仅 1/7 大小)。

## 关键数据

| 指标 | AdaCheck vs SOTA |
|------|-----------------|
| Checkpoint size | **-6.00~896×** |
| Checkpoint frequency | **+1.46~111×** |
| 训练吞吐开销 | near zero |
| 冗余检测 (128 workers) | <3min |
| 兼容 | ZeRO-1/3, MiCS, auto-planner; Dense/MoE/MLA |

## 可复用启发

1. **"Tensor redundancy 抽象 = 分析 state distribution 而非具体并行策略"**: 不关心用什么并行(ZeRO/MiCS/auto) → 只问"哪些 worker 有同一 tensor 的副本"。类似 GCR 的 control/data 分离——抽象出独立于具体实现的 modeling 层

2. **"三阶段通信压缩 = meta→hash→ring broadcast"**: 逐步缩小比较范围: meta 排除明显不同→hash 聚集可能相同→ring 最终确认。类比 two-stage GC(先 easy case→再 full check)。每阶段消灭剩余中的大部分

3. **"仅存 gradient = 利用 iteration 间 state update pattern"**: 相邻 checkpoint 的差异 = optimizer update = f(gradient)。不存 full state→存 compact gradient→replay 恢复。类似 GCR 的 dirty template 和 CacheSlide 的"layer 1 profiling→后续继承"

4. **"Fault domain map = 确保至少一个副本在 checkpoint 中存活"**: 不是任意一致副本→而是保证在任意单节点故障下仍有一个可用副本。考虑物理拓扑的 redundancy utilization
