# LithOS(SOSP'25)

- **来源**: SOSP '25, DOI:10.1145/3731569.3764818
- **作者**: Patrick H. Coppock, Brian Zhang, Eliot H. Solomon, Vasileios Kypriotis (CMU), Leon Yang, Bikash Sharma, Dan Schatzberg (Meta), Todd C. Mowry, Dimitrios Skarlatos (CMU)
- **类型**: 论文-系统/GPU OS
- **一句话 TL;DR**: 首个 GPU 操作系统——将 OS 抽象（time-sharing、空间调度、隔离、DVFS）移植到 GPU，TPC 级调度 + 透明 kernel 原子化 + 硬件 right-sizing + 功耗管理，13× 尾延迟下降 vs MPS，25% 节能。

## 核心问题

数据中心 GPU 利用率极低——Microsoft 52% 平均、Alibaba 10% 中位数、Meta 生产 Ads 仅 27%。现有方案（NVIDIA MPS、MIG、Orion/REEF/TGS）存在三个根本缺陷：(1) 调度粒度过粗——以整个推理请求或 DNN operator 为单位，head-of-line blocking 严重 (2) 缺乏透明性——需要修改 ML 框架或驱动 (3) 无资源隔离保证。LithOS 首次用 OS 思想系统化解决 GPU 资源管理问题。

## 关键洞察

1. **"TPC 级空间调度 + TPC Stealing"**：以单个 Texture Processing Cluster 为调度单位→空闲 TPC 可被其他 workload "偷走"→大幅提升利用率。类似 vBOIDs "全局稳定性+局部灵活性"——TPC 是局部决策单元。
2. **"透明 kernel 原子化——不修改任何代码就能拆分巨型 kernel"**：通过修改 QMD (Queue MetaData) 的 program address 注入 Prelude→将 kernel thread blocks 切分为独立可调度的 "atoms"→打破 head-of-line blocking。类似 GraCE/MPK 的 "编译器桥接"——在低层做透明变换。
3. **"Two-point Amdahl 插值 = 轻量 hardware right-sizing"**：仅需 1 TPC 和 all TPCs 两次测量→拟合 `l = m/t + b` 曲线→预测最优 TPC 分配→节省 26% GPU capacity (<4% perf hit)。类似 Kareus "roofline model + single-layer profiling"——低成本近似替代高成本详尽探索。
4. **"Compute vs memory-bound → DVFS 决策"**：计算密集型 kernel 保持高频，内存密集型可降频→25% 节能（7% perf hit）。类似 SANI "adaptive granularity"——根据 kernel 特性而非全局策略做差异化处理。

- 来源：LithOS(SOSP'25)

## 实践启发

- **"OS 抽象可以也应当移植到 GPU"**：CPU 用了几十年的 time-sharing、spatial scheduling、isolation 在 GPU 上仍未实现→LithOS 证明这些抽象对 GPU 同样有效。这是 paradigm shift——从 "GPU 是黑盒加速器" 到 "GPU 是可控的计算平台"
- **"Transparency is non-negotiable for adoption"**：不修改模型/框架/runtime 是 LithOS 的设计原则——类似 hS/Incr "bolt-on" 哲学——降低 adoption barrier 比追求 optimal 更重要
- **"Kernel atomization = GPU 的 time-sharing primitive"**：CPU 有 timer interrupt 做抢占→GPU 没有→kernel atomization 提供了一种 "伪抢占"——将大 kernel 拆成小块→中间点可以重新调度
- **"Two-point model is surprisingly effective"**：硬件 right-sizing 通常需要复杂建模→LithOS 用最简单的两点插值就够用。类似 Merlin "per-object characterization"——一个问题看起来复杂，但简单的数学工具可能足够
- **"Rust in OS kernel is here"**：5K line Rust GPU OS→证明 Rust 在 OS 层（包括与 CUDA 驱动交互）是可行的
