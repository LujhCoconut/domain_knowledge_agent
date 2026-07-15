# GPU / AI Performance

GPU 与 AI/ML 推理和训练的性能优化知识。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| LLM 层次化 KV Cache 管理 | GPU-assisted I/O, PagedAttention, layout decoupling, delay hit, TTFT | Strata(OSDI'26) |
| LLM Serving 调度 | balanced batch, bubble filling, bundle hit, cache-aware scheduling | Strata(OSDI'26) |
| GPU-CPU 数据传输 | PCIe bandwidth utilization, Little's Law, DMA vs kernel I/O | Strata(OSDI'26) |
| 稀疏注意力 KV Cache 动态 Offloading | graph-friendly cache manager, EMA top-k prediction, lossless prefetching, warp specialization, DeepSeek DSA | ECHO(OSDI'26) |
| Zero-Copy KV Cache Offloading | CPU-memory-aware tiling, SMEM reuse, warp-level pipelining, fused P+A kernel, NVLink-C2C | DirectKV(OSDI'26) |
| LLM 请求调度与路由 | multiplicative scheduling, KV$-awareness, load balancing, P-token × BS, hotspot detection | LMetric(OSDI'26) |
| Tree-of-Thought 推理加速 | speculative exploration, reward barrier, intra/inter-query speculation, search-level + token-level synergy | SPEX(OSDI'26) |
| 多模型 GPU 显存共享 | memory ballooning, CUDA VMM, elastic tensor, KVPR, time/space sharing, bursty groups | Prism(OSDI'26) |
| 万亿参数 MoE 训练 | overlap-aware partition, synthesized overlap schedule, dynamic bubble filling, pipeline parallelism | Tessera(OSDI'26) |
| 异质分布式训练 (SPMD) | asymmetric sharding, hierarchical communication, graph specialization, dynamic switching | Hetu-v2(OSDI'26) |
| 内核级 Compute-Comm Overlap | chunk-centric overlap, in-kernel communication, tile schedule reshaping, Triton compiler | Syncopate(OSDI'26) |
| Agentic Workflow 编排 | declarative specification, profile-guided optimization, cross-layer orchestration, SLO-aware runtime | Murakkab(OSDI'26) |
| RL 后训练 Co-Scheduling | dependency bubble, co-execution group, rollout-training disaggregation, two-tier scheduling, residency constraint | Weave(OSDI'26) |
| RL 训练流变换 (M2Flow) | macro-to-micro flow, context switching, elastic pipelining, heterogeneous component orchestration | RLinf(OSDI'26) |
| RL 动态资源调度 (DynaRL) | dynamic hypergraph, resource migration, context-aware data routing, multi-level scheduling | DynaRL(OSDI'26) |
| Agentic RL 异构硬件解耦 | trajectory-level decoupling, hardware heterogeneity mapping, stale-bounded async, serverless reward | RollArt(OSDI'26) |
| 同步 RL Rollout 优化 | divided rollout, context-aware scheduling, adaptive grouped speculative decoding, heavy-tailed latency | Seer(OSDI'26) |
| 本地 CPU-GPU 混合 MoE 推理 | stream-loading prefill, CPU-GPU hybrid, SmallEP, local SLO, FP8 CPU inference | CPU-GPU Hybrid MoE(OSDI'26) |
| 批量推理协程调度 | sequence coroutine, yield/combine/partition/migrate, MoE batching, long-tail straggler, batch completion time | BatchGen(OSDI'26) |
| 训练能耗联合优化 | execution schedule, SM allocation, partitioned overlap, dynamic+static energy, multi-objective BO, GPU frequency | Kareus(OSDI'26) |
| RL 后训练容错 | role-based fault isolation, Detect-Restart-Reconnect, warm standby, UCX dynamic reconnect, ETTR | RobustRL(OSDI'26) |
| CPU-GPU 协同 I/O 引擎 | split SQ/CQ, CPU co-pilot, barrier-based sync, adaptive co-polling, GPU I/O stall reduction | CoPilotIO(OSDI'26) |
| GPU 十亿级向量搜索 | node-level dependency, tiered graph, discovery-expansion window, async edge fetching, ANNS | FlowANN(OSDI'26) |
| GPU 演化图分析 | proxy graph, approximate-then-refine, fused kernel, concurrent snapshots, bound-based pruning, multi-version compaction | POEGA(OSDI'26) |
| 商品 GPU 集群 LLM Serving | PaDG, macro instance, commodity clusters, prefill-decode interference, cross-instance orchestration, Ethernet | EcoServe(OSDI'26) |
| 流水线并行 LLM Serving | pipeline parallelism, chunked-prefill, greedy/predictive chunk sizing, delay scheduling, pipeline bubbles, PCIe GPUs | Pipeline Parallelism Revisited(OSDI'26) |
| 在线 Neuron 均衡 GPU-CPU 推理 | online neuron balancing, activation sparsity, live pipeline, TAM cache, adaptive balancer, consumer GPUs | Kairox(OSDI'26) |
| 任意精度量化推理加速 | DPR computation model, mpGEMM, bit-partition, adaptive kernel selection, APQ, edge LLM inference | ADAngel(OSDI'26) |
| Tensor Core SWP+WS 约束优化 | software pipelining, warp specialization, constraint optimization, Twill, FlashAttention, cross-generation portability | Twill(OSDI'26) |
| Mega-Kernel 编译器与运行时 | SM-level task graph, persistent kernel, decentralized scheduling, cross-operator pipelining, CUDA Graph alternative | MPK(OSDI'26) |
| CUDA Graph 编译器使能 | graph-aware code transformation, indirect parameter passing, cost-benefit guided deployment, kernel launch bottleneck | GraCE(OSDI'26) |
| Virtual Tensor 数据移动消除 | virtual tensor, index mapping, data movement elimination, tensor compilation, memory-bound, operator fusion | VTC(OSDI'26) |
| 训练中断弹性运行时 | delta communication group, sandbox warmup, standby replacement, interruption-resilient, elastic GPUs, ETTR | TrainMover(OSDI'26) |
| 消费者 GPU 时间复用 | temporal multiplexing, UVM thrashing, working set eviction, MLFQ scheduling, consumer GPU, transparent swap | Nixie(OSDI'26) |
| 移动端 LLM 推理内存带宽 | asymmetric interference, NPU bandwidth priority, speculative decoding preemption, jank rate, mobile SoC UMA, foreground QoS | Sereno(OSDI'26) |
| 移动 AMP CPU DNN 推理 | AMP asymmetry, performance-collapse paradox, adaptive granularity scheduling, core-kernel affinity, big.LITTLE | SANI(OSDI'26) |
| 推荐系统超高效 NAS | superproxy metric, training-free architecture search, recommendation models, model efficiency, FLOP reduction, AUC | Drs.NAS(OSDI'26) |
| GPU OS 资源管理 | TPC scheduling, kernel atomization, hardware right-sizing, DVFS, head-of-line blocking, GPU utilization, transparent interposition | LithOS(SOSP'25) |

---

## LLM 层次化 KV Cache 管理

### 核心问题
长上下文 LLM 推理中，KV cache 占用远超 GPU HBM 容量，必须层次化缓存（HBM→CPU DRAM→SSD），但 KV 传输成为主导瓶颈——小页面碎片化 + layer-first 内存布局导致 PCIe 带宽利用率仅 5-22%。

### 关键洞察

1. **PagedAttention 的 I/O 代价**：
   - 1-32 token 小页面 → 单次传输仅 KB 级
   - 大页面提升带宽但损害 cache hit rate（page 512 vs page 1 差 2× TTFT）
   - layer-first layout 将一个逻辑页散成 L 层非连续片段 → 进一步碎片化
   - 来源：Strata(OSDI'26) §3.1

2. **GPU-Assisted I/O**：
   - 启动 CUDA kernel 做 GPU↔CPU 传输（替代 cudaMemcpyAsync DMA）
   - GPU 数千线程并发（↑C）→ 即使小 S 也能达到高带宽
   - 仅需 128B 粒度即可高效（DMA 需要 MB 级）
   - 2 blocks × 1024 threads → 48 GB/s，prefill 损失 <5%
   - 来源：Strata(OSDI'26) §4.2

3. **Layout Decoupling**：
   - GPU 保持 layer-first（计算友好），Host 使用 page-first（传输友好）
   - I/O kernel 在传输时做 on-the-fly address transformation
   - 对端到端性能影响显著：DeepSeek-V3 TTFT 改善 2.1×
   - 来源：Strata(OSDI'26) §4.2.1

4. **三种写策略**:
   | 策略 | 行为 | 场景 |
   |------|------|------|
   | write-back | 仅 eviction 时备份 | 资源受限 |
   | write-through | 每次生成就备份 | 对话 |
   | selective-write-through | 访问计数超阈值才备份（默认） | 通用 |
   - 来源：Strata(OSDI'26) §4.4

### 实践启发

- **Little's Law 诊断 I/O 瓶颈**: `X = C × S / L` → 要提升吞吐，增大并发 C、增大传输 S、降低延迟 L 三选一或多选
- **GPU kernel I/O 比 DMA 更适合碎片化数据**: 小数据高频传输场景（KV cache、embedding、graph data）优于 cudaMemcpy
- **Layout decoupling 模式通用**: 计算和 I/O 各自最优布局 → 轻量在线变换解耦
- **硬件带宽升级不能解决软件碎片化问题**: GH200 6× 带宽提升但 Strata-PCIe 仍胜出

---

## LLM Serving 调度

### 核心问题
层次化缓存引入 KV 加载延迟 → 调度器需要将 I/O 视为一等资源，平衡计算和数据传输，避免 delay hit（并发请求同一 cache miss 时的冗余计算）。

### 关键洞察

1. **Delay Hit 现象**：
   - 多请求在 cache miss 解决期间并发到达 → 冗余 prefill
   - Agentic workload (Mooncake): 38% 请求在 1s 内共享 ≥6K token 前缀
   - 来源：Strata(OSDI'26) §3.2

2. **Transient Node 机制**：
   - HiRadixTree（扩展 SGLang RadixTree）引入 in-queue / in-flight 标记
   - 匹配到 transient node → defer 到下一轮，排到队首
   - 完成后转为 standard node（指向 ready cache）
   - 来源：Strata(OSDI'26) §4.3.1

3. **Balanced Batch Formation**：
   - Load/compute ratio > 100 → loading-bound → 移入 deprioritized list
   - 优先加入 bundle hit（共享 context）请求
   - 防止饥饿：保序，每轮从队列首开始
   - 来源：Strata(OSDI'26) §4.3.2

4. **Bubble Filling**：
   - Loading-bound 时插入 decoding batch（HBM 带宽密集，与 PCIe 不冲突）
   - 互补于 SGLang 的 prefill-first policy
   - 来源：Strata(OSDI'26) §4.3.3

### 实践启发

- **Delay hit 在分布式缓存系统中普遍存在**: 不仅限于 Web cache/CDN，也适用于分布式 KV cache、parameter server
- **Transient node 是轻量级的 delay hit 解决方案**: 比全局锁或事务性 cache fill 开销低得多
- **Balanced batch 本质是 I/O-aware load balancing**: 类似 PACT 的 "criticality-first" —— 都是将之前被忽视的维度（I/O/stall）纳入调度决策

---

## GPU-CPU 数据传输

### 关键洞察

- **DMA cudaMemcpyAsync 局限**: 需要 MB 级 transfer 才能饱和带宽
- **GPU-Assisted I/O 优势**: 128B 粒度即可高效，数千线程并发
- **cudaMemcpyBatchAsync (CUDA 12.8)**: 新 API，批量小传输单次 driver submission，不消耗 SM，但吞吐低于 GPU kernel I/O（38 vs 48 GB/s）
- **GH200 NVLink C2C 提供了 384 GB/s** 但软件碎片化使其实际利用率极低

### 实践启发

- **最优方案可能是混合**: GPU kernel I/O for critical CPU→GPU path (higher BW) + batch API for GPU→CPU backup (zero SM contention)
- **Interference 控制**: 少量 CUDA blocks (2) + bypass cache + 低 SM 占用

---

## 稀疏注意力 KV Cache 动态 Offloading

### 核心问题
Native sparse attention (DeepSeek DSA) 减少了注意力计算，但 KV cache 线性增长更陡峭（indexer 额外 K cache），GPU HBM 容量成为主要瓶颈。动态 token-level offloading 可以在同样 HBM 下支持更大 batch size，但面临两大挑战：管理开销破坏 CUDA Graph、top-k 语义阻碍 prefetching。

### 关键洞察

1. **Graph-Friendly Cache Manager**：
   - 所有元数据用固定长度整数 tensor 存储于 GPU（非 CPU）
   - Allocate: 并行 `atomicAdd`；Free: 并行 `argtopk + scatter`；Recall: scatter + UVM kernel 读取
   - 完全兼容 CUDA Graph → 解码路径保持单图执行
   - Per-layer metadata 管理（稀疏注意力每层选择不同 token）
   - 来源：ECHO(OSDI'26) §4

2. **EMA 预测 top-k 阈值实现无损 Intra-query Prefetch**：
   - 核心洞察：k-th highest score 跨解码步高度可预测（EMA α=0.5）
   - 将 top-k selection 近似为 top-p → 移除串行依赖
   - 在 indexer 计算期间 start prefetch（indexer 用 GPU compute，recall 用 PCIe BW → 可重叠）
   - 完全无损（不降低模型准确率，区别于 InfiniGen/FreeKV）
   - 来源：ECHO(OSDI'26) §5.1

3. **Inter-query Prefetch for Prefill**：
   - Q blocks 顺序处理 → Q block i 的选中 token 在 Q block i+1 计算时并发预取
   - 用 radix select 单轮粗粒度过滤（非精确 top-k）+ EMA score shift
   - 来源：ECHO(OSDI'26) §5.2

4. **Fused Kernels with Warp Specialization**：
   - 3-stage software pipeline: TMA (load) → GEMM (compute scores) → Prefetch (compare + UVM load)
   - 基于 DeepGEMM 改造
   - 预取 warp 组额外 pipeline stage + 全局计数器防止过度预取
   - 来源：ECHO(OSDI'26) §5.3

### 实践启发

- **"Graph-Friendly" 作为 GPU 系统设计约束**: 固定长度 tensor + 并行 GPU ops 替代动态 CPU 控制
- **数值可预测性打破串行依赖**: EMA 预测 top-k 阈值可推广到任何 "先排序再选择" pipeline
- **Per-layer 管理比 per-model 更精确**: 稀疏 attention 每层选择不同 token → 需要 per-layer state
- **UVM kernel direct access**: 避免 host CPU 参与，保持 graph-compatible
- **PD disaggregation 下的混合策略**: prefill 不开 offloading（低并发），decode 开 offloading（高并发）

### Strata vs ECHO 对比

| 维度 | Strata(OSDI'26) | ECHO(OSDI'26) |
|------|----------------|---------------|
| 目标模型 | Dense attention | Native sparse attention (DSA) |
| Offloading 模式 | Static (request-level) | Dynamic (token-level, per-layer per-step) |
| 缓存管理 | Layout decoupling + write policy | Graph-friendly per-layer metadata |
| Prefetch | N/A | Lossless EMA prediction + fused pipelining |
| 核心瓶颈 | PCIe BW 利用率低（碎片化） | GPU HBM 容量不足 |
| 吞吐提升 | 3.2-5× vs vLLM-LMCache | 2.1-4.1× vs SGLang |
| 延迟开销 | ~0（短上下文持平） | 0.28% decode (offload) / +15-19% e2e (low load) |

---

## Zero-Copy KV Cache Offloading

### 核心问题
Swap-based offloading (Pie, FlexGen) 需要 GPU staging buffer → 浪费 HBM + CPU-GPU 往返传输翻倍。Zero-copy 允许 GPU kernel 直接访问 CPU-resident KV，但 naïve 实现性能极差（PCIe 慢 20×，NVLink-C2C 慢 2×），因为 GEMM kernel 为 HBM 优化设计，反复从 CPU 取 operand 暴露带宽差距。

### 关键洞察

1. **SMEM tiling 反转消除 C2C 瓶颈**：
   - Naïve: 外层迭代 CPU-side KV → 每个 tile 都从 CPU 重新加载 → O(n³) C2C traffic
   - DirectKV (CPU-aware): 将 KV tile 在 SMEM 中 stationary，外层迭代 HBM 中的 Q/C → O(n²) C2C traffic
   - 代价：C matrix HBM 往返增多，但 HBM (4 TB/s) 带宽充足
   - 效果：CPU-GPU 传输 -50%，延迟 -49%，L2 hit rate 32.3%→75.1%
   - 来源：DirectKV(OSDI'26) §5.1

2. **Warp-Level Pipelining 重叠通信与计算**：
   - Producer warps (TMA 异步预取) / Consumer warps (GEMM) / Storer warps (CPU memory writeback)
   - HBM 吞吐 0.3→1.3 TB/s (4.3×)，延迟 -11%
   - 来源：DirectKV(OSDI'26) §5.2

3. **Fused Projection-Attention Kernel 消除 KV Round-Trip**：
   - 传统：Kernel1 (X→K/V, write to CPU) → Kernel2 (Q×K/V, re-read from CPU)
   - DirectKV: 同一 kernel 内 K/V 生成后留在 SMEM 直接被 attention 消费 → 消除冗余读写
   - HBM 吞吐 +15.8%，延迟 -49%
   - 来源：DirectKV(OSDI'26) §5.3-5.4

4. **NVLink-C2C 是硬件前提**：
   - GH200/GB200 提供 900 GB/s 双向 C2C（7× PCIe Gen5）
   - PCIe 上 DirectKV 主要用于 capacity extension，非 performance 提升
   - C2C latency 通过 warp pipelining 隐藏
   - 不依赖 UPT，仅用标准 pinned memory
   - 来源：DirectKV(OSDI'26) §7.4.3, §8.2

### 实践启发

- **SMEM 作为"on-chip hierarchy"**: 在慢速介质和快速介质之间引入 SMEM buffer 层
- **Tiling 策略反转**: "让慢速数据 stationary，快速数据流动"——适用于任何 asymmetric bandwidth 场景
- **Kernel fusion 消除 round-trip**: 适用于任何 intermediate tensor 跨 kernel 边界的 GPU pipeline
- **分离关注点**: kernel execution 与 KV management/scheduling 完全解耦，drop-in 兼容现有 serving stack
- **NVLink-C2C 使 zero-copy 成为可能**: 硬件趋势 (Vera CPU: 1.8 TB/s C2C) 将使 zero-copy 越来越重要

### 三篇 OSDI '26 KV Cache 论文对照

| 维度 | Strata | ECHO | DirectKV |
|------|--------|------|----------|
| 层次 | Application (I/O + scheduling) | Framework (metadata + prefetch) | Kernel (tiling + pipelining) |
| 目标模型 | Dense (Llama/Qwen) | Sparse (DeepSeek DSA) | Dense (Llama/OPT) |
| Offloading | Static request-level | Dynamic token-level | Zero-copy (no staging) |
| 硬件 | H200 PCIe 5.0, GH200 | H20 PCIe Gen5 | GH200 NVLink-C2C |
| 核心技术 | GPU kernel I/O + layout decoupling | Graph-friendly metadata + lossless prefetch | CPU-aware tiling + fused P+A kernel |
| GPU 内存节省 | ~0 (布局优化) | ~60% (host pool) | 43% (no buffer) |
| 性能提升 | 3.2-5× | 2.1-4.1× | 1.2× |
| 代码量 | 集成 SGLang | 基于 SGLang + DeepGEMM | 5300 行 CUDA |

---

## LLM 请求调度与路由

### 核心问题
LLM 集群中 global scheduler 需同时平衡 KV$-awareness（路由到缓存 prefix 的实例）和 load balancing（避免过载）。现有三类策略各有痛点：线性组合需 per-workload 调参，filter-based 需阈值调优且偏向负载均衡，simulation-based 需 per-model/hardware 开发。

### 关键洞察

1. **乘法消参原理**：
   - 线性组合 `Score = λ·KV_indicator + (1-λ)·load_indicator` 的排序列与乘法 `KV_indicator × load_indicator` 等价
   - 比较 `Score_i < Score_j` 时 λ 在乘法中自然消去
   - 因此 `Score = P-token × BS` 成为无需调参的统一调度分数
   - 来源：LMetric(OSDI'26) §5

2. **P-token 优于 1-KV$ hit ratio**：
   - Hit ratio 只反映匹配比例，不反映实际节省的计算量
   - P-token 额外编码了每个实例的排队 prefill 负载 → 自动绕过积压严重的实例
   - P50 TTFT 比 hit-ratio 方案低 14.4%，P95 低 42.8%
   - 来源：LMetric(OSDI'26) §5.1

3. **BS 优于 #Tokens**：
   - #Tokens 混合了 prefill 和 decode 负载，但 prefill 已被 P-token 覆盖
   - BS 更精确反映 decode 时间（decode time 与 BS 的线性关系更稳定）
   - 来源：LMetric(OSDI'26) §5.1

4. **失效条件数学推导（KV$ hotspot）**：
   - 当 `x/x̄ > |M|/|M̄|` 时（请求类流行度超过缓存该类的实例比例），乘法可能失效
   - 在 4 条真实 trace 中从未发生
   - 两阶段检测器：Phase 1 监控比率，Phase 2 确认后才过滤热点实例
   - 来源：LMetric(OSDI'26) §5.2

### 实践启发

- **乘法消参技巧可推广**: 任何"比较加权分数"场景（DB optimizer、CDN routing、负载均衡）都可考虑乘法替代线性组合
- **先理解 workload 结构再做简化**: 不是黑盒调参 → 分析 prefill/decode 二分结构 → 两个指标各管一阶段
- **推导失效边界让简单方法可信**: "simple but with known failure mode" 优于 "complex black-box"
- **Rust 框架让 policy 可公平对比**: indicator factory + DSL 将不同调度策略统一到同一基础设施

### OSDI '26 LLM Serving 全景（5 篇）

| | Strata | ECHO | DirectKV | LMetric |
|---|---|---|---|---|
| 方向 | KV 搬运效率 | KV 动态 offloading | Zero-copy 传输 | 请求调度 |
| 层次 | App I/O+调度 | Framework metadata | Kernel tiling | Router 层 |
| 核心 | GPU kernel I/O | Graph-friendly offload | CPU-aware tiling | P-token × BS |
| 调参 | 全局配置 | 全局配置 | 无需 | **无需** |
| 生产 | SGLang | N/A | N/A | **阿里百炼** |
| 核心 insight | Layout decoupling | EMA 预测 top-k | SMEM stationary KV | Multiplication cancels λ | Memory ballooning unifies time & space |

---

## 多模型 GPU 显存共享

### 核心问题
推理提供商需同时维持数百上千模型的可用性，但 70%+ 时间模型处于空闲状态。Pure space sharing 锁死空闲模型内存；pure time sharing 在抢占性负载下导致 model thrashing。需要弹性显存管理来同时支持两种模式。

### 关键洞察

1. **Bursty groups — 生产负载的核心特征**：
   - 23-50% 模型同时活跃，活跃组每小时变化 54-766 次
   - 类似应用 working set：常驻模型 + 偶尔出现的模型
   - 连续两天同一时间的 traffic Pearson correlation ≈ 0
   - 来源：Prism(OSDI'26) §3

2. **Memory ballooning 统一 time/space sharing**：
   - Time sharing = swapping weights；Space sharing = scaling KV cache
   - GPU 显存是二者的共同瓶颈 → 弹性化 GPU 显存 → 统一两种模式
   - 类比虚拟化中的 balloon driver：hypervisor 从空闲 VM 回收内存给活跃 VM
   - 来源：Prism(OSDI'26) §1, §5

3. **kvcached — CUDA VMM 层的弹性内存**：
   - 通过 CUDA VMM API 解耦虚拟/物理地址：engine 看到大段虚拟空间，物理页 on-demand 映射
   - eTensor 抽象：22 行代码集成 SGLang，零 attention kernel 修改
   - 2MB page + 连续虚拟布局 + 异步预分配缓冲池
   - 来源：Prism(OSDI'26) §5.2

4. **KVPR + Moore-Hodgson 双层控制**：
   - Global: KVPR = `(token_rate × token_size / SLO) / shared_kv` → 驱动模型 placement
   - Local: Moore-Hodgson deadline scheduling → 最大化 TTFT SLO 达成
   - 来源：Prism(OSDI'26) §6

### 实践启发

- **下沉内存管理到驱动层**: 应用层（PagedAttention）跨模型不可见 → CUDA VMM 层是更好的抽象
- **Memory ballooning 可推广**: FPGA、TPU、NPU 等加速器也有类似问题
- **KVPR 作为需求/容量比的指标**: 将多维压缩为一个比较标量 → 适合贪心决策
- **Engine pool 消除冷启动**: 预初始化资源池 + 按需分配，可推广到其他"状态重"的服务

### OSDI '26 LLM Serving 全景（6 篇）

| | Strata | ECHO | DirectKV | LMetric | Prism |
|---|---|---|---|---|---|
| 方向 | KV I/O | KV offloading | Zero-copy kernel | 请求调度 | **多模型显存共享** |
| 层面 | App I/O | Framework | Kernel | Router | **Cluster GPU mgmt** |
| 单/多模型 | 单 | 单 | 单 | 单（集群路由） | **多** |
| 核心 | GPU kernel I/O | Graph metadata | CPU-aware tiling | P-token × BS | **Memory ballooning** |
| 生产 | SGLang | — | — | 阿里百炼 | **10K+ GPU (kvcached)** |
| 核心 insight | Layout decoupling | EMA top-k prediction | SMEM stationary KV | Multiplication cancels λ | **Ballooning unifies time & space** |

---

## 万亿参数 MoE 训练 (Pipeline Parallelism)

### 核心问题
训练 Qwen3-Next 等千亿参数模型时，模型架构从 uniform Transformer blocks 演变为异质组合（DeltaNet + softmax attention + dense FFN + sparse MoE）。这种异质性打破现有 PP 系统的均匀性假设：不同层组合的 compute-communication 比例不同 → uniform overlap strategy 在某些组合中仅有 14% 的通信被隐藏。

### 关键洞察

1. **Overlap-aware partitioning 优于 compute-aware partitioning**：
   - 传统 PP partitioner 按 serial computation cost 均分 stage → 忽略 overlap 后的实际剩余通信
   - Tessera 离线 profile 每种层组合的 post-overlap cost → 用这个 cost 驱动 partition → 所有 stage 平衡
   - 来源：Tessera(OSDI'26) §overlap-aware partitioner

2. **Per-layer-combination synthesized overlap schedule**：
   - 为每对 (layer_type_A, layer_type_B) 单独合成最优 compute-communication 交错
   - 利用 virtual stages（同一物理 rank 多个虚拟 stage）实现细粒度重叠
   - 替代传统的 uniform 1F1B 策略
   - 来源：Tessera(OSDI'26) §overlap scheduler

3. **Dynamic bubble filling for MoE routing skew**：
   - MoE routing 产生各 stage 间的 token 负载不均衡 → transient idle slots
   - Dynamic bubble optimizer 监控 routing metadata → 在 idle slot 中插入可移动任务（gradient sync 等）
   - 来源：Tessera(OSDI'26) §dynamic bubble optimizer

### 实践启发

- **"Overlap-aware" 是通信密集并行的正确决策维度**：仅看 serial cost 不够
- **异质架构需要异质优化**：uniform strategy 在 certain 组合上必定次优
- **Dynamic bubble filling 可推广**：任何 "static plan + dynamic load skew" 系统都可受益

### 生产数据 (Alibaba Cloud)
- 10,000+ GPUs, Qwen3/Qwen3-Next pre-training
- 5 workloads at 4,096–12,288 GPUs: +20-33% throughput
- Trillion-parameter model: 39% MFU
- vs Megatron-Core: 1.24× MFU

---

## 异质分布式训练 (SPMD)

### 核心问题
SPMD 范式假设"所有设备同构且所有输入等量"——但在混合 GPU 代际、频繁设备故障（Llama 3: 54 天 419 次中断）、变长序列的现实中被打破。HSPMD 通过原语层扩展（非对称 sharding）+ 执行层双图机制（graph specialization + dynamic switching）统一处理三种异质性来源。

### 关键洞察

1. **扩展 SPMD 原语而非替代它**：保留"单设备视角编程"的简洁性，在 sharding 注解层添加不对称语义
2. **空间 vs 时间异质性的分离处理**：设备差异是 quasi-static → progressive graph specialization；数据差异是 per-batch → dynamic graph switching
3. **层级通信**：混合 GPU 代际场景中，先 intra-group all-reduce（同代 GPU）→ 再 inter-group reduce
- 来源：Hetu v2(OSDI'26)

### 与 Tessera 的关系

| | Tessera(OSDI'26) | Hetu-v2(OSDI'26) |
|---|---|---|
| 异质性来源 | 模型架构 (不同层类型) | 设备 (GPU 代际/故障) + 数据 (变长) |
| 并行维度 | Pipeline Parallelism | SPMD (DP/TP/Sharding) |
| 核心机制 | Overlap-aware partition + dynamic bubble | Asymmetric sharding + graph specialization/switching |

---

## 内核级 Compute-Communication Overlap

### 核心问题
当前分布式 GPU 编译器在内核级别重叠通信（NCCL streams + 多内核拆分）。这强制设备范围的同步、产生额外的内核启动开销，并且当波内最慢的瓦片延长通信尾部时，产生大量空闲时间。需要在内核**内部**以更细的粒度进行重叠。

### 关键洞察

1. **通信块抽象解耦粒度**：将 "通信应该以什么粒度发生" 作为独立于 "内核如何结构化" 的维度 → 块级方案可重用、可移植
2. **内核内部通信注入**：直接从融合内核内部发出通信操作（而非调用外部 NCCL）→ 消除内核启动开销，最小粒度降低数百倍
3. **瓦片调度重塑**：重新排列内核内部的瓦片执行顺序以优先处理已就绪的数据 → 同时保持寄存器/共享内存/缓存局部性
4. **多后端显式选择**：编译器为每个传输选择最优硬件后端（复制引擎/TMA/CUDA cores）
- 来源：Syncopate(OSDI'26)

### OSDI '26 GPU 系统三篇堆栈

| | Tessera | Hetu-v2 | **Syncopate** |
|---|---|---|---|
| 抽象级别 | PP 调度 (microbatch) | SPMD 分片 (device) | **内核 (tile/chunk)** |
| 通信重叠 | microbatch 之间 | inter-DP group | **intra-kernel tiles** |
| 加速 | 1.2-1.33× | matches specialized sys | **1.3× avg, 4.7× max** |

---

## Agentic Workflow 跨层优化

### 核心问题
Agentic workflow 的部署涉及三层独立优化：workflow 结构、每个 agent 的 model 选择、底层硬件 provisioning。三层互相不可见 → 无法端到端推理"用更便宜的模型是否仍能满足 accuracy SLO"。

### 关键洞察

1. **声明式规范分离逻辑与执行**：开发者描述"做什么"而非"用什么做"→ 系统自动匹配最优 model+hardware 组合
2. **Profile-guided optimizer 是跨层优化的关键**：离线 profiling 每个 model+hardware 组合的 cost/latency/accuracy → 在线选择满足 SLO 的最低 cost 配置
3. **Adaptive runtime**：动态重配置以响应流量变化和 model 更新
4. **Agentic inference ≠ standard LLM API calls**：多轮依赖、工具调用、条件分支——需要专门的 orchestration 系统而非通用 serving
- 来源：Murakkab(OSDI'26)

### 实践启发
- 声明式范式在 agentic workflow 中特别有效：workflow 结构复杂多变，手动指定每个 agent 的 model+hardware 组合不可扩展
- 跨层优化需要 profile 数据支撑——cost/latency/accuracy 三者之间存在可量化的 trade-off 曲面
- 能耗和成本的节省（3-4×）表明 agentic workflow 的资源浪费比 standard inference 更严重——因为有更多"过度配置"的自由度

---

## RL 后训练 Co-Scheduling

### 核心问题
RL 后训练的 rollout-training 解耦架构在两个专用集群之间交替执行——但 on-policy 同步要求产生**依赖气泡**：rollout 集群在 training 期间闲置，反之亦然。异步 off-policy 方案消除气泡但牺牲模型精度和收敛稳定性。

### 关键洞察

1. **Co-execution group 是消除 bubble 的正确中层抽象**：将多作业的 rollout 和 training 阶段跨 pool 交错编排——作业 A 的 rollout 填充作业 B 的 training bubble，反之亦然
2. **双层调度分离关注点**：组间调度器用保守随机规划（处理不可预测的序列长度）做粗粒度作业放置→组内调度器用可证明最优的轮询编排
3. **Residency constraint 是"热启动"的硬约束**：每个 worker 持有数百 GB 的模型状态——co-execution group 的大小受限于所有成员作业的状态能放进每个 worker 的主机内存
4. **100% SLO 达成的同时 1.84× 成本效率**：conservative planning + 确定性的组内调度保证了 SLO 不会因 bubble-filling 而违反
- 来源：Weave(OSDI'26)

### 实践启发
- "Dependency bubble"是任何有两个交替阶段跨不同资源池的系统的通用概念（不仅是 RL——generative AI 的 prefill-generate、ML 训练的 forward-backward、MapReduce 的 map-reduce）
- "Co-scheduling across pools"是解耦系统的正确调度抽象——不分别优化两个池，而是优化交叉池的依赖链
- Residency constraint 作为"warm-start"的硬约束：必须决定每个 worker 能"记住"多少个作业

---

## RL 训练流变换 (M2Flow)

### 核心问题
RL 训练工作流包含高度异构的组件（LLM 推理、training、reward models、agent tooling、embodied simulators），每个有不同的资源需求和动态性。现有系统用单一执行模式（colocated→长尾问题；pipelined→资源碎片化），无法适应这种多样性。

### 关键洞察

1. **"宏观逻辑流→微观执行流"解耦**：开发者编写高层 RL 工作流 → M2Flow 在时空两个维度上自动分解并重组为优化的微执行流
2. **Context switching 作为第三种调度策略**：RLinf worker 在不同 RL 组件间自适应切换，填充 accelerator 空闲间隙（与 colocated 和 pipelined 并列）
3. **Elastic pipelining**：灵活调整组件间的 pipeline 深度和资源分配
4. **Profiling-guided scheduling**：离线 profile 各组件的资源需求 → 在线生成最优执行计划
- 来源：RLinf(OSDI'26)

### 实践启发
- "高层描述→底层优化"的解耦设计是任何多组件异构工作流系统的通用范式
- RL 训练系统的核心瓶颈不是训练本身的吞吐，而是异构组件的调度效率
- Context switching 作为填充 accelerator idle gap 的策略，可以与 colocated/pipelined 互补使用

---

## RL 动态资源调度 (DynaRL)

### 核心问题
现代 RL 工作负载展现极端动态性（重尾 rollout、不规则工具交互、时变瓶颈），静态资源分配浪费高达 60% 计算。现有 RL 系统预先固定分配 GPU 且训练期间不变——与瓶颈的时间变化性质根本矛盾。

### 关键洞察

1. **动态超图作为统一控制面**：将整个 RL 管线建模为随时间演化的超图——计算/内存/通信资源都表示为可动态重分配的超边
2. **"静态分配→动态重分配"**：统一资源迁移接口 + context-aware 数据路由——运行时动态迁移资源以消除瓶颈
3. **多层次调度：粗粒度组件间 rebalancing + 细粒度资源迁移**——协同消除瓶颈
4. **在线调度开销可忽略**：证明动态调度在 production RL 训练中是可行的（无额外性能代价）
- 来源：DynaRL(OSDI'26)

### 实践启发
- 动态超图是"高度动态的多组件管线"的强大建模工具——不仅适用于 RL
- "运行时适应"+ "设计时优化"是互补策略：RLinf 在编译时变换工作流，DynaRL 在运行时动态重分配资源
- OSDI '26 四篇 RL 论文（Weave/RollArt/DynaRL/RLinf）共同表明 RL 训练系统的瓶颈已从"计算加速"转向"调度效率"

### OSDI '26 RL 训练五篇

| 论文 | 核心机制 | 优化维度 | 加速 |
|------|---------|---------|------|
| Weave | Co-execution group 消除 dependency bubble | 跨池调度 | 1.84× |
| **RollArt** | **异构硬件映射 + trajectory 级解耦** | **硬件解耦 + pipeline 分解** | **1.31-2.05×** |
| RLinf | M2Flow 宏→微流变换 | 工作流变换 | 1.07-2.43× |
| DynaRL | 动态超图 + 资源迁移 | 运行时资源重分配 | 1.98× |
| **Seer** | **divided rollout + context-aware speculative decode** | **同步 rollout 长尾优化** | **2.04×, 长尾 -72-94%** |

---

## 同步 RL Rollout 优化 (Seer)

### 核心问题
同步 RL 训练中 rollout 阶段占总时间的 63-87%（Moonlight 84%、Qwen2-VL 63%、Kimi-K2 87%），核心瓶颈是**重尾长轨迹分布**导致的负载不均衡和 KVCache 内存波动。长 CoT 生成的 KVCache 可能从几百 MB 爆发到数十 GB。

### 关键洞察

1. **"共享 prompt → 相似的输出行为"**：共享相同 prompt 的请求在输出长度和响应模式上高度相似——这是调度优化的关键信号
2. **Divided rollout**：将 rollout 批次按预测输出长度动态拆分，防止长请求拖累整个批次
3. **Context-aware scheduling**：利用 prompt 相似性预先感知长输出请求，在调度时特殊处理
4. **Adaptive grouped speculative decoding**：相似 prompt 请求分组共享草稿模型，减少重复计算
- 来源：Seer(OSDI'26)

### 实践启发
- "共享 prompt → 相似输出"不仅是语义观察，也是系统优化信号——适用于任何 LLM 批处理/推理场景
- 重尾延迟的本质是"最慢的请求主导了整个批次的 GPU 空闲时间"——divided rollout 是解决这一问题的直接方案

---

## Agentic RL 异构硬件解耦 (RollArt)

### 核心问题
Agentic RL 工作负载混合了计算密集型 prefill、带宽密集型 decode、CPU 密集型环境执行和突发性 reward 评估——单一 GPU 集群无法匹配所有硬件特性。即使是部分解耦的系统也将资源密集的 rollout 和 training 阶段 colocate。Reward 阶段在专用 GPU 上的利用率仅 7.4%。

### 关键洞察

1. **将每个 pipeline 阶段映射到最佳硬件**：prefill→H800 (compute-opt, 时间仅 H20 的 0.53×)、decode→H20 (BW-opt, 时间仅 H800 的 0.49-0.79×)、env→CPU cluster、reward→serverless
2. **Trajectory 级解耦**：慢或失败的环境不阻塞其他 trajectory——生成、环境交互和 reward 评分独立进行
3. **Staleness-bounded async**：rollout 与 training 重叠，带有 staleness bound —— 既获得异步效率，又保护收敛稳定性
4. **Serverless reward**：reward 工作负载利用率仅 7.4% → serverless 按需伸缩比专用 GPU 更经济
- 来源：RollArt(OSDI'26)

### 实践启发
- "将每个阶段映射到最佳硬件"是异构多阶段管道的通用优化策略——不仅适用于 RL
- Trajectory-level decoupling 是处理长尾效应的经典策略：不要让最慢的单元阻塞整个系统
- Serverless 模型在"低利用率 + 突发性"的工作负载上有天然优势——reward 评估恰好满足这两个条件

---

## 本地 CPU-GPU 混合 MoE 推理 (CPU-GPU Hybrid MoE)

### 核心问题
本地部署 MoE 大模型即便在低并发下也无法达到云级 SLO：四个关键差距——依赖压缩/量化模型（质量让步）、12K+ prompt 超 30s TTFT、decode 吞吐 <20 tok/s、混合 prefill-decode 并发差。

### 关键洞察

1. **Stream-loading prefill (SLP)**：不是减小模型而是**流体化加载**——动态流式加载模型层到 GPU，在层加载期间执行而非等待完整模型
2. **CPU-GPU 混合充分利用现有硬件**：双路 CPU + 消费级 GPU 的组合比纯 GPU 方案更实用
3. **CPU native FP8 是一个未充分探索的维度**：4-5× 延迟降低，通常 FP8 讨论聚焦 GPU
4. **Dual-batch attention-MoE overlap**：双批次重叠执行隐藏延迟
- 来源：CPU-GPU Hybrid MoE(OSDI'26)

### 实践启发
- "Stream-loading" 可推广到任何"模型太大、layer 需动态加载"的场景
- 本地/边缘场景下的 CPU-GPU 混合推理比纯 GPU 更实用
- FP8 在 CPU 上的加速是 under-explored 的优化维度

---

## 批量推理协程调度 (BatchGen)

### 核心问题
批量推理（离线推理、合成数据、评测、RL rollout、test-time scaling）已成为 AI 计算最大模式，但现有推理引擎（vLLM、SGLang、TensorRT-LLM）全部继承自交互式 serving 的延迟优先模型。两个结构性低效：(1) **Intra-sequence imbalance**：MoE 稀疏性导致 attention 和 expert 层需要不同 batch size 才能饱和 GPU，但传统系统 sequence 固定绑定 GPU 且 forward pass 原子执行，无法在 module 边界暂停、累积 sequence。(2) **Inter-sequence imbalance**：test-time scaling 和 reasoning 产生严重长尾——DeepSeek-R1 的 P99 输出长度是 P95 的 3.78×，最大值 9.2×。straggler 决定 BCT，导致 10-70% GPU 利用率损失。

### 关键洞察

1. **"序列协程"是推理系统的新抽象层次**：类比 Apache（thread-per-connection）→ Nginx（event-driven）的范式转变。每个 sequence 是独立 coroutine，可在 module 边界 yield、跨 GPU combine/partition/migrate。打破"sequence 固定绑定 GPU"的根本限制。

2. **Module 边界 = 天然调度点**：NN 的模块化结构（attention→MoE→下一层）提供自然的 coroutine yield point。Attention 小 batch 饱和 GPU，MoE 需要大 batch——在 attention 后 yield，combine attention 输出后再批量运行 MoE → expert batch size 可膨胀 10-100×。

3. **"超额订阅 + coroutine pool"模式**：scheduler 保持大量 inactive sequence 在 host memory 中，自由选择 combine 对象最大化 expert batch，而不是按到达顺序服务。类似 Nginx 的 keep-alive connection pool。

4. **"静态 plan + 动态 callback"分工**：rooline model 决定 yield point 和最优 batch size（静态、一次），运行时 callback（O_N_LONG_TAIL / O_N_REFILL）处理不可预测的长尾和空闲。两者解耦 = 高效且灵活。

5. **"弱 GPU 上优化收益更大"**：H20 上 speedup > H200——compute 越弱，batching 效率的边际收益越大。反直觉：不应只优化最强 GPU。

- 来源：BatchGen(OSDI'26)

### 实践启发
- 任何 modular NN 都可以在 module 边界插入 yield point——不仅是 MoE，VLM（encoder↔language）、multi-modal pipeline 都是 natural candidate
- "超额订阅"模式让 scheduler 有选择余地——在 batch inference 中应有意保持超过 GPU 容量的 sequence pool
- 动态 straggler 管理（检测→yield→partition）可复用于任何"固定 worker 数 + 长尾任务"的并行场景
- KV-cache 的 host checkpoint + lazy GPU allocation（每 sequence 仅 2 pages）是最小化内存压力的有效策略
- BatchGen 和 UEP 共享设计哲学：用软件层打破硬件刚性绑定（UEP 解耦 GPU-NIC，BatchGen 解耦 sequence-GPU）

---

## 训练能耗联合优化 (Kareus)

### 核心问题
大模型训练的能耗增长远超电力供给增长（预计 2035 年美国近 10% 电力用于数据中心），单次训练能耗可供电 24,000 户家庭一个月。现有方案各管一摊：Perseus 降低 off-critical-path 的 GPU 频率减少动态能耗但忽略 kernel 调度，Nanobatching 重叠通信和计算减少静态能耗（缩短时间）但忽略频率。**简单的 Perseus + Nanobatching 组合是次优的**——因为 SM 分配、频率、启动时机三者互为依赖，改变一个会改变其他要素的最优配置。

### 关键洞察

1. **"Execution schedule 的三要素应联合优化"**：SM 分配、kernel 启动时机、GPU 频率三者联合决定时间和能耗——即使总工作量相同，不同 schedule 可导致时间和能耗差 **3.29×**。现有方案各优化子集，naive 组合是次优的。

2. **"恒定频率 > 频率波动"的能耗优势**：GPU 动态功耗 ∝ f³（V²f，V ∝ f）。频率波动导致高功耗期的能耗浪费 > 低功耗期的节省。Nanobatching 提高 GPU 利用率但触发 GPU 频率 throttling——平均频率降低、平均功耗反而保持高位。Kareus 选择固定稍低频反而更快更省电。

3. **"重叠什么"比"重叠多少"更重要**：通信 kernel 与 memory-bound kernel（Norm）同时运行争内存带宽，与 compute-bound kernel（Linear）同时运行争 SM——资源竞争维度不同，最优 overlap 策略完全不同。

4. **"低频改变最优 schedule"**：低频率使所有 kernel 变得相对更 compute-bound（频率只影响计算速度、不影响内存/通信带宽）→ 改变了哪些 kernel 应与通信重叠。意味着不能先选 schedule 再调频率——必须同时优化。

5. **"大搜索空间可以通过结构约束分解"**（Partitioned overlap）：识别重复的通信+计算分区模式（Attention-AllReduce、MLP-AllReduce），强制同类型分区共享配置 → 将 85K candidates 的全局搜索分解为 manageable 的局部 subproblems。

- 来源：Kareus(OSDI'26)

### 实践启发
- **任何有 DVFS 的计算场景都应考虑"恒定频率优于频率波动"**：响应式频率调整的时间不对称性意味着恒定低频通常比高频+降频更节能。
- **Compute-communication overlap 优化时必须关心资源需求类型**：memory-bound vs compute-bound 的 co-run 效果完全不同。不仅是 overlap 与否的问题，更是"与什么重叠"的问题。
- **BO 做多目标优化需要多方向的 acquisition**：total/dynamic/static/uncertainty 四轮 pass 的设计可推广到任何需要找 time-energy Pareto 前沿的系统问题。
- **"温度敏感的性能/功耗测量"不可忽视**：GPU 功耗随温度漂移小但足以影响 Pareto 前沿准确性——需要 cooldown + 重复测量。这也意味着 profile 一次不能一劳永逸——季节/机房温度变化会影响最优 schedule。
- **自动回退到简单方案**：Kareus 在 GPU 欠利用时（small microbatch）自动选择 sequential 而非 nanobatching。一个系统不仅要知道何时用高级特性，还要知道何时不用。

---

## CPU-GPU 协同 I/O 引擎 (CoPilotIO)

### 核心问题
GPU-centric I/O (BaM) 提供高吞吐和 on-demand 访问，但 GPU 需持续轮询 NVMe completion queue→三种 stall（intra-warp/inter-warp/inter-SM）→GPU compute 可用性下降高达 87%。CPU-centric I/O (GDS) 不消耗 GPU 但性能低且无法 on-demand。现有选择是 all-GPU or all-CPU 的二分。

### 关键洞察

1. **"Split SQ/CQ 打破 all-GPU or all-CPU 的二分"**：Submission Queue 在 GPU 侧（直接发起 I/O，低延迟），Completion Queue 映射到 CPU 侧（CPU 轮询完成，不浪费 GPU compute）。GPU 和 CPU 各自做最擅长的事。
2. **"Hardware barrier-based synchronization"**：GPU→CPU 的完成通知不走 kernel，用 PCIe barrier 直接同步——消除 kernel I/O stack overhead。
3. **"CQ-based adaptive co-polling"**：高 I/O 负载时 CPU 主导轮询，低负载时 GPU 自行轮询——减少不必要跨 PCIe 通信。

- 来源：CoPilotIO(OSDI'26)

### 实践启发
- **"不是 CPU vs GPU，而是 CPU + GPU——职责分离而非替代"**：与 UEP（GPU 发起 CPU 执行 RDMA）、UCCL-Tran（NIC data path + CPU control path）共享同一个设计哲学
- **"Adaptive offloading"比"固定卸载"更优**：负载变化时动态迁移轮询角色

---

## GPU 十亿级向量搜索 (FlowANN)

### 核心问题
GPU ANNS 比 CPU 快 200×，但 GPU 显存有限（80-96GB），十亿级图索引需 239-334 GB。现有方案将图 offload 到 CPU 内存，但 step-level dependency（每步必须等所有邻居计算完）→GPU stall 等边获取。

### 关键洞察

1. **"Step-level dependency 可以解耦为 node-level dependency"**：每个节点有两个阶段——Discovery（作为邻居被访问，产生边获取需求）和 Expansion（被选为 parent 遍历邻居，使用已获取的边）。两者间通常隔了很多步→边获取可以延迟并与后续计算异步流水线化。
2. **"把 step barrier 拆掉"**：Tiered graph——hot 边在 GPU，有时间窗口的边 offload 到 CPU→异步获取与计算重叠。
3. **"discovery-expansion 窗口是关键"**：前期研究大多关注如何更快获取边，FlowANN 关注的是**何时获取**——重新组织获取时序，而不是重新设计获取机制。

- 来源：FlowANN(OSDI'26)

### 实践启发
- **"将粗粒度全局依赖解耦为细粒度局部依赖"是并行化的经典模式**：类似 BatchGen 的 attention-MoE yield、Ambulance 的 non-equivocation as race——本质都是识别出"可以晚点做的事"
- **"不改变 IO 机制，改变 IO 时序"**：当 IO 瓶颈无法消除时，重新组织 IO 时序以 overlap 计算

---

## GPU 演化图分析 (POEGA)

### 核心问题
演化图分析 (EGA) 需对图快照序列评估查询——GPU 快但显存有限，增量计算虽可用但 OOM I/O 瓶颈使现有 GPU EGA 无法扩展到大规模图。

### 关键洞察

1. **"用 approximate computation 换 I/O，再并行化摊销 compute 开销"**：Proxy graph（紧凑近似图）先做近似计算→指导精确 OOM I/O→减少不必要的 I/O。额外计算由 GPU 的大规模并行性摊销。
2. **"Fused kernel 并发处理多 snapshot"**：将多个 snapshot 的计算 fuse 到单个 kernel→最大化 GPU 并行度→摊销 proxy graph 的计算 overhead。
3. **"Bound-based pruning"**：运行时按边界剪枝冗余的跨 snapshot 工作——进一步减少不必要的计算。

- 来源：POEGA(OSDI'26)

### 实践启发
- **"用计算换 I/O，再并行化摊销计算"是 GPU 的通用策略**：GPU compute 便宜但 I/O 昂贵→用 compute 减少 I/O→再用 parallelism 吸收 compute 开销
- **"多 snapshot 并发"是演化图分析的独特优势**：静态图分析无法利用这一点——EGA 的 time dimension 提供了额外的并行度

---

## 商品 GPU 集群 LLM Serving (EcoServe)

### 核心问题
现有两种 LLM serving 策略都不适合普通 GPU 集群（L20 + Ethernet——无 NVLink/InfiniBand 的主流生产环境）：NoDG（prefill/decode colocate 在同一实例）有严重相位干扰——两种相位交替执行→decode 无法积累足够大 batch→吞吐差；FuDG（完全解耦 prefill 和 decode 到不同实例）依赖高性能互联传输 KV cache——在 ordinary Ethernet 上不可行。

### 关键洞察

1. **"PaDG：时间维度解耦而非空间解耦"**：单实例内在时间维度上交替 prefill 和 decode→避免两者同时争抢 GPU 资源。多个实例组成 macro instance 并循环激活→保证 prefill 持续可用→救援 decode 延迟。
2. **"减少 KV cache 传输的数据量使其在 Ethernet 上可行"**：不像 FuDG 要求传输完整 KV cache→而是稀疏化传输→在普通网络带宽下也可承受。
3. **"Macro instance = 跨实例协作的基本单元"**：多个实例协作而非独立工作→缓解单实例隔离带来的 prefill 不可用问题。Mitosis scaling 动态调整 macro instance 内实例数→在线细粒度容量调整。

- 来源：EcoServe(OSDI'26)

### 实践启发
- **"二分之外有第三选择"**：colocate vs disaggregate 不是二选一——partial disaggregation 在两者之间找到平衡点。类似 CoPilotIO 的 "all-GPU vs all-CPU → split SQ/CQ"、FlowANN 的 "step-level vs per-node → node-level dependency"
- **"系统设计应该面向实际部署环境而非前沿硬件"**：大多数研究假设 H100+NVLink+IB，但生产环境的硬件替换周期长得多——L20+Ethernet 依然是主流。好的系统设计应覆盖长尾硬件

---

## 流水线并行 LLM Serving (Pipeline Parallelism Revisited)

### 核心问题
Tensor Parallelism (TP) 已成为 LLM serving 标配——但在 **PCIe 互联的 commodity GPU** 上，每层 all-reduce 的通信量成为瓶颈。Pipeline Parallelism (PP) 通信量远小于 TP，理论上吞吐更高——但 **online serving 下 pipeline bubbles 严重**：请求到达时间不确定 + 输入长度可变→各 microbatch 计算量差异大→stage 间互相等待。

### 关键洞察

1. **"PP 的通信优势在 PCIe GPU 上被低估，但 bubbles 问题也被低估"**：PP 每步仅传小量 activation，远小于 TP 的 all-reduce。但 online workload 的动态性使固定 schedule 产生大量 bubbles。硬件条件变化（commodity GPU→PCIe 成为瓶颈）改变了 TP vs PP 的 trade-off。
2. **"动态 chunk 大小用更少 bubbles 实现同吞吐"**：Greedy chunk 填充最大允许大小→减少碎片。Predictive chunk 利用未来请求信息→前瞻性更优。类似 SPADE 的 "cross-task coordination" 和 EcoServe 的 "macro instance 协作"——用跨请求调度替代固定 schedule。
3. **"Delay scheduling 重平衡 decode 负载"**：延迟部分 decode 请求→将过载 stage 的工作移到后续 microbatch→进一步消除 bubbles。

- 来源：Pipeline Parallelism Revisited(OSDI'26)

### 实践启发
- **"PP 在 PCIe GPU 上值得重新评估"**：类似 Helmsman "clustering strikes back"——硬件条件变化改变了旧权衡。TP 在 NVLink GPU 上最优，PP 在 PCIe GPU 上可能更优→不存在普适的 "最佳并行策略"
- **"动态调度 > 静态 pipeline schedule"**：online serving 的负载变化使固定 schedule 产生大量 bubbles→需要 adaptive scheduling。类似 BatchGen 的 "sequence coroutines"——运行时重新组织执行顺序
- **"不是选择 TP 还是 PP，而是何时用哪个"**：PP 在带宽受限场景（PCIe/NPU）下被系统性低估了——应作为 commodity GPU 的默认选择之一

---

## 在线 Neuron 均衡 GPU-CPU 推理 (Kairox)

### 核心问题
Consumer GPU（如 RTX 4090 24GB）无法装下 13B+ 模型全量参数→必须做 CPU-GPU 混合推理。静态 sparse offloading（PowerInfer）基于离线 profiling 分"热/冷"神经元，但**运行时激活模式会变化**——静态 partition 无法适应→suboptimal。CPU 计算弱+PCIe 传输慢的双重瓶颈。

### 关键洞察

1. **"Online neuron balancing 替代 static partitioning"**：不提前固定哪些 neuron 在 GPU/CPU——而是根据当前 layer 的激活模式动态 prefetch 和 swap。类似 Kareus 的 "execution schedule 三要素联合优化"——静态分离注定次优。
2. **"Live Pipeline = 预测+预取覆盖传输延迟"**：在 layer i 的 Attention 阶段就预测 FFN 激活模式→提前从 CPU→GPU 传输所需 neuron→隐藏 PCIe 延迟。类似 FlowANN 的 discovery-expansion window。
3. **"Temporal Activation Momentum (TAM)"**：短暂激活尖峰不值得迁移到 GPU——用 temporal persistence filter 区分"持续有用"和"一闪而过"的 neuron。类似 cache replacement policy 但针对 activation pattern。
4. **"Adaptive Neuron Balancer"**：实时平衡 CPU workload vs I/O overhead——两者互为瓶颈，balancing 强度需要动态调整→类似 Ambulance 的 "protocol-rigged racing" 中的 cutoff 机制。

- 来源：Kairox(OSDI'26)

### 实践启发
- **"Activation-based prefetching"**：instruction prefetching 是 CPU 的经典技术——Kairox 将其迁移到 neuron 级别，利用 activation locality 预测下一层权重需求
- **"TAM = temporal persistence filter"**：短暂 spike 不值得做重量级操作（neuron 迁移）——类似 hot page tracking 中的"不要 swap 即将被 free 的 page"
- **"Local/consumer deployment 是 LLM 推理的重要方向"**：数据隐私+去云成本→本地推理需求巨大。Kairox 专注 consumer GPU 而非 H100 集群→与 EcoServe 和 PP Revisited 共享"面向实际硬件"的设计哲学

---

## 任意精度量化推理加速 (ADAngel)

### 核心问题
APQ（任意精度量化，如 W4A8）是边缘 LLM 推理的关键压缩技术——用不同 bit-width 量化 weights 和 activations 以获得最优 accuracy-efficiency trade-off。但现有边缘硬件缺乏原生混合精度 GEMM 支持。三种现有方案各有局限：Padding（upcast→浪费内存带宽）、LUT（预计算表→内存开销大）、Bit-disaggregation（1-bit 分解→固定范式不适应 shape/bit-width 变化）。**没有一个方案适应 LLM 推理中 GEMM 任务的异构性**——prefill 是 compute-bound GEMM、decode 是 memory-bound GEMV，shape 和 bit-width 差异巨大。

### 关键洞察

1. **"DPR (Decomposition-Partial Product-Reconstruction) 计算模型"**：将任意 bit-width 的 GEMM 系统化地分解为多个部分积→以不同 bit-partition 方案重构→生成多种 mpGEMM 算法。不是硬选 padding 或 bit-disaggregation，而是根据任务特征生成最优组合。
2. **"Computation Strategy Set + Oracle Policy Map"**：预生成多种高度优化的 kernel→离线穷举分析每个 (shape, bit-width) pair 的最佳 kernel→运行时轻量 dispatcher 查表选择→接近零 overhead。类似 Kareus 的 "roofline model + DAG critical path"。
3. **"Prefill vs Decode 需要不同策略——同一 LLM 内也异构"**：prefill = compute-bound（长序列、大 batch），decode = memory-bound（单 token、KV cache 访问多）。静态 kernel 选择在两个阶段间必然次优→adaptive mapping 是必需的。

- 来源：ADAngel(OSDI'26)

### 实践启发
- **"Bit-partition 多策略 + runtime dispatch"** 是异构硬件的通用优化模式：类似 Kareus "execution schedule 搜索 + 运行时选择"——离线枚举最优配置，在线零开销切换
- **"同一工作流内存在 compute-bound 和 memory-bound 两个 phase"**：不仅是 prefill/decode——任何混合 workload 都应考虑 per-phase optimization 而非一刀切
- **"通用硬件上的量化推理值得更多关注"**：不是所有部署都有 custom accelerator——oracle policy map 使通用 GPU 上的 APQ 也能达到接近专用硬件的效率

---

## Tensor Core SWP+WS 约束优化 (Twill)

### 核心问题
Tensor Core GPU 各代架构差异巨大——数据放置位置、线程需求、异步执行模型在 Hopper→Blackwell 间可能以倍数级别变化。每个程序在不同 GPU 代际上需要不同的最优软件流水线+warp 特化调度。现有方法依赖启发式编译器+人工直觉→无最优性保证→手工优化不可跨代移植。

### 关键洞察

1. **"SWP + WS 联合形式化为约束优化问题"**：软件流水线和 warp 特化不是两个独立变换——应作为单一优化问题联合求解。Twill 用现成的约束求解器求解→无 heuristic→保证全局最优。搜索空间被完整表达为约束→求解器穷举所有有效调度。
2. **"约束求解替代 heuristics——最优性保证"**：传统编译器的 heuristics 在复杂搜索空间中几乎必然次优。表达为约束→求解器找到全局最优→证明未被支配。
3. **"Twill 重新发现并证明 FlashAttention 手工优化已是最优"**：在 Hopper 和 Blackwell 架构上，Twill 自动推导出与专家手工优化相同的 SWP+WS 调度——**证明这些手工优化不可再优化**。这意味着未来的架构升级只需要新约束→自动新调度。

- 来源：Twill(OSDI'26)

### 实践启发
- **"约束求解替代 heuristics"是编译器优化的通用方法论**：当搜索空间足够大时，heuristic 几乎必然次优。表达为约束→求解器找全局最优。类似 Kareus "MBO 替代手动调优"——用数学优化替代人工经验
- **"跨代可移植 = 重求解"**：新 GPU 架构只需更新硬件约束→求解器自动产生新调度。程序不需要改变——只改变约束描述。这是 "write once, solve per architecture" 的范式
- **"证明 >= 提出"**：Twill 不仅产生调度，还能证明现有手工优化已是最优——这是编译器研究中的新颖贡献形式。非侵入式的上限证明可以为手工优化提供"不再需要继续手动调参"的信心

---

## Mega-Kernel 编译器与运行时 (MPK)

### 核心问题
现有 LLM 推理系统采用 kernel-per-operator 执行模型——每个算子一个 GPU kernel。三个被低估的限制：(1) **GPU 隐式 kernel barrier**：同 stream 上的连续 kernel 之间存在隐式 barrier→阻止跨 kernel 软件流水线 (2) **依赖仅在算子粒度表达**→compute-comm overlap 只能是 coarse-grained (3) **数百个 kernel launch 开销**→依赖 CUDA Graphs 但 Graphs 是静态的→动态 workload 灵活性差。

### 关键洞察

1. **"SM 级任务图替代算子级 DAG"**：依赖在单个 SM 粒度表达→每个 SM 独立调度→消除 kernel barrier→实现跨算子软件流水线+细粒度 compute-comm overlap。一个 all-reduce 不需要等整个 matmul 完成→只需依赖 matmul 中对应的 SM fragment。
2. **"Mega-kernel = 单一 persistent kernel + 去中心化调度"**：整个推理作为一个 kernel 运行→消除 kernel launch 开销→去中心化 SM 调度不需要 global barrier。类似 Ambulance "protocol-rigged racing"——用细粒度本地决策替代全局同步。
3. **"编译器自动 mega-kernelize"**：开发者不需要手动实现 persistent kernel——MPK 编译器自动从 tensor program 生成 SM 级任务图+CUDA kernel 实现。

- 来源：MPK(OSDI'26)

### 实践启发
- **"Kernel barrier 是最被低估的性能上限"**：implicit barrier 阻止了几乎所有跨算子优化——SM 级调度打破了这个桎梏
- **"去中心化调度 > 全局 barrier"**：每个 SM 独立决策何时执行哪个任务→消除全局同步点→类似 Ambulance/M3U 的 "lock relaxation"
- **"Mega-kernel 替代 CUDA Graphs"**：静态 graph 在动态 workload 下灵活性不足——persistent kernel 是更通用的方案

---

## CUDA Graph 编译器使能 (GraCE)

### 核心问题
ML 工作负载每次迭代 launch 数百个短 GPU kernel，每个 CPU→GPU kernel 提交需 5-10µs。GPU 计算速度超过 CPU 提交速度→GPU 利用率 <50%（阿里/Azure 报告）。CUDA Graphs 可将一组 kernel 捕获为单图→一次 dispatch 重放→消除 per-kernel launch 开销。但实际部署 CUDA Graph 极其困难：(1) **程序不是面向 Graph 编写的**——tensor 地址在 capture 时硬编码→host 端 dealloc 后 crash；scalar 参数值固化→跨迭代读到 stale 值 (2) **即使能部署，parameter copy 开销也吞噬收益** (3) **盲目全局启用会使部分应用变慢**。

### 关键洞察

1. **"CUDA Graph-aware code transformation——编译器桥接高层语义和底层硬件特性的 gap"**：PyTorch 程序与 CUDA Graph 有巨大语义距离。GraCE 自动分析 IR→找到 Graph-oblivious 模式（CPU tensor→GPU memcopy、scalar 参数）→自动变换 IR 使 Graph 可用。类似 MPK 的 "自动 mega-kernelize"——用户不需要手动适配硬件特性。
2. **"Indirect parameter passing——tensor copy→pointer copy (数 KB→8B)"**：大幅减少 CUDA Graph 的 parameter overhead。JIT 编译的 kernel 自动 de-reference indirected 参数；vendor 不可变 kernel (cuBLAS) 通过 prelude kernel 完成 de-reference→消除百倍级的数据复制。
3. **"Cost-benefit guided deployment"**：自动 profiling→仅对收益正的 kernel 启用 Graph→避免盲目全局应用。类似 Kareus "auto fallback to sequential"——不是所有场景都适合用。

- 来源：GraCE(OSDI'26)

### 实践启发
- **"编译器填补高层语义与低层硬件特性的 gap"**：语言级程序离硬件特性（CUDA Graph）有语义鸿沟→编译器自动桥接。类似 Twill "write once, solve per architecture"——编译器承担跨层适配的负担
- **"不是所有优化都要全局启用"**：cost-benefit analysis + selective deployment > blind global optimization。类似 SPADE 的 γ 参数——控制优化强度的可调 knob 优于 on/off
- **"Indirection 是最古老的性能技巧之一——但编译器可以自动插入"**：参数间接化 = 用 pointer 替代 tensor copy——编译器自动生成 indirection 和 de-reference 逻辑

---

## Virtual Tensor 数据移动消除 (VTC)

### 核心问题
计算能力飞速增长（H100 ~1 PFLOPS），但内存带宽增长远远落后→memory-bound 成为瓶颈（尤其 LLM decode 阶段）。现有编译器优化（layout transform、算子融合）只覆盖部分 data movement 操作→大量不必要的 global memory ↔ accelerator 数据传输被遗漏。

### 关键洞察

1. **"Virtual Tensor = index mapping 替代 data copy"**：不是将 producer tensor 物理复制到 consumer→而是用 index mapping 描述两者关系。只有当 compute 确实需要数据时才 lazily 按映射获取。类似 Duhu "pass-by-reference 替代 pass-by-value"——改变编程抽象而非硬件本身。
2. **"与现有 kernel 和 fusion（如 FlashAttention）无缝协作"**：不需要重写 operator kernel——virtual tensor 作为中间层在编译时插入→对上层和应用透明。Virtual tensor 的 index mapping 可以与 FlashAttention 等 handmade fusion 共存，进一步提升效果。
3. **"全谱 data movement 消除"**：layout transformation 和 operator fusion 都只覆盖部分 data movement→VTC 首次覆盖全谱→消除了之前无法触及的数据传输。

- 来源：VTC(OSDI'26)

### 实践启发
- **"Virtual memory 的思想应用于 tensor compilation"**：Virtual tensor 类似虚拟内存的 lazy paging——不搬数据直到必须。与 InfiniDefrag "GPA 是虚拟的" 和 Blowfish "GPA 已是虚拟层" 共享思想——利用虚拟化避免物理搬移
- **"Index mapping 是一个被低估的编译器中端优化"**：当前编译器聚焦于 compute kernel 生成（后端）和高层融合（前端），中间层的 data movement 消除是巨大空白

---

## 训练中断弹性运行时 (TrainMover)

### 核心问题
大规模 LLM 训练被频繁中断——硬件故障、软件异常、管理事件（repair/patch/rebalance→需重启机器）。16,000 GPU 作业每天累积 >1 小时 downtime，浪费 $86K。现有方案：(1) stop-reschedule-reinitialize（小时级）(2) reconfiguration（可弹性替换但 joiner 从 checkpoint 初始化慢）。关键：训练布局高度特化→乱改会触发 OOM 或性能退化。

### 关键洞察

1. **"Two-phase delta-based communication group setup"**：不全重建 NCCL communicator→仅增量更新受影响的 group（受影响机器退出+joiner 加入）→大幅减少通信重建时间。类似 RobustRL 的 "role-based 恢复"——故障隔离+局部修复。
2. **"Communication-free sandboxed warmup"**：新 joiner 在通信隔离的 sandbox 中预热（加载模型、编译 kernel→最耗时步骤）→不阻塞已运行的训练→预热完成后无缝加入通信组。类似 SDCHUNTER "解耦恢复和诊断"——离线做昂贵的事，不影响在线。
3. **"General standby design"**：任意角色（TP/PP/DP 任意维度）的机器都可被同构 standby 替换→不需要为每种角色维度维护专用备机池。弹性池 + 通用替换→备机利用率远高于专用备机。

- 来源：TrainMover(OSDI'26)

### 实践启发
- **"Delta-based membership > full reconfiguration"**：只更新受影响部分而非重建全局→类似 vBOIDs "全局稳定性+局部灵活性"、RobustRL "角色隔离恢复"
- **"Sandbox warmup = 隔离预热 + 无缝加入"**：将准备工作和正在进行的训练分离→消除加入延迟。类似 SDCHUNTER "Phase 1 隔离→Phase 2 精确" 的分层策略
- **"ETTR 是训练的硬指标"**：每天 downtime >1h → 直接转化为 $86K 浪费。TrainMover 将其降至 ~20s→**不能容忍小时级中断的体系结构必须支持弹性**

---

## 消费者 GPU 时间复用 (Nixie)

### 核心问题
消费者 GPU (RTX 4090/5090) 同时运行多个 ML 应用（LLM + diffusion + 代码补全）。每个模型 working set 几乎饱和 GPU 内存→同时运行超出容量。NVIDIA UVM 的 demand paging 假设 working set 可共存→严重 thrashing→吞吐崩溃+延迟尖峰。应用级 swap（llama-swap/Ollama）限于单应用→无法跨应用协调。consumer GPU 场景是 single-user、heterogeneous、快速切换——与 datacenter multi-tenant 完全不同。

### 关键洞察

1. **"Temporal multiplexing 替代 spatial multiplexing"**：不试图让多个模型同时驻留 GPU→每次只给一个应用完整显存→用完 evict/reload 下一个。利用 PCIe 双向带宽做快速切换。类似 vBOIDs "不要给调度器太多选择"——限制并发而非管理并发。
2. **"MLFQ-inspired 调度自动区分交互 vs 批处理"**：交互式应用（代码补全）自动高优先级→低延迟；后台批处理自动降级→不影响交互。不需要手动标注 workload 类型。
3. **"透明截获——不需要修改应用或驱动"**：截获 CUDA memory allocation + kernel launch→对 llama.cpp/SGLang/ComfyUI 全透明。

- 来源：Nixie(OSDI'26)

### 实践启发
- **"Consumer GPU = 反 datacenter GPU"**：consumer 是 single-user、heterogeneous、快速切换→大多数 GPU sharing 研究假设多租户 batch→不适用。类似 EcoServe 和 Kairox 的 "面向实际硬件" 哲学——consumer GPU 有自己独特的约束和优化机会
- **"Explicit swap > demand paging"**：当 working set >> GPU memory 时，知道何时换入换出比按需 page fault 更高效。UVM 的 thrashing 是隐式策略在极端条件下的失效——显式控制总是更优

---

## 移动端 LLM 推理内存带宽 (Sereno)

### 核心问题
移动 SoC 的统一内存架构（UMA）中 NPU 继承 ISP 的高内存优先级——这是历史设计为保护实时媒体任务（视频录制）而设。LLM 推理在 NPU 上运行，无意中获得了这个硬件级优先权→前台 UI 渲染的帧率被严重破坏（jank rate **+153%**），但 LLM 吞吐几乎不受影响（仅 -1.01%/1.64%）。这是**严重的不对称干扰**——不是软件调度问题，是硬件优先级策略与新兴 workload 的不匹配。

### 关键洞察

1. **"Asymmetric interference from legacy hardware prioritization"**：NPU 的硬件级内存优先级是为视频录制等实时媒体任务设计的→LLM 推理意外继承此特权→前台帧渲染被内存带宽饥饿。这是一个**硬件设计假设与新兴 workload 冲突**的典型案例——类似 ASI Heterogeneity "fractional-GPU 共享几乎不被使用"——硬件假设与生产现实之间存在 gap。
2. **"Speculative decoding = fine-grained preemption points for bandwidth yielding"**：推测解码的每个 token speculation 步骤提供天然的 yield 点→检测内存争抢→动态让出带宽给前台→重放最后几个 token 即可恢复推理→不丢失进度。类似 FlowANN "discovery-expansion window"——利用已有的推测步骤作为抢先点，不需要额外机制。
3. **"不修改硬件解决硬件级问题——软件自适应"**：利用 SoC 现有的性能监控单元检测带宽争抢→软件层动态降级 LLM 的带宽使用→前台恢复流畅。类似 EcoServe "为普通 GPU 集群设计"——面向实际硬件约束的务实方法。

- 来源：Sereno(OSDI'26)

### 实践启发
- **"继承的硬件特权可能是隐形杀手"**：NPU 的内存优先级为视频录制设计→LLM 继承了它→前台 UI 受损。当 repurpose 硬件给新 workload 时，必须检查继承的硬件策略是否仍适用
- **"推测解码的多重价值——不仅降低延迟，还提供抢占点"**：speculative tokens 可作为自然的 preemption boundary→类似 Ambulance "非 non-equivocation phase 也是 race"——已有的机制可以被重新利用为其他目的
- **"Jank rate 是移动端的真实 SLO"**：移动 LLM 推理不能只看 throughput/latency——用户的感知流畅度（jank frame 比例）才是真正的体验指标

---

## 移动 AMP CPU DNN 推理 (SANI)

### 核心问题
移动 SoC 的 AMP CPU（big+LITTLE cores）在 DNN 推理中面临 **performance-collapse paradox**——将所有核用于并行推理，反而因 big/LITTLE 不对称导致吞吐下降（最多 +37% 延迟）。根因是工作负载不平衡：big core 线程在 barrier 等待 LITTLE core 线程完成。现有方案：对称执行（只用 big core，浪费 LITTLE）、静态 partition（不适应 runtime 干扰）、忽略 core-kernel affinity。

### 关键洞察

1. **"Affinity-aware kernel issuer——每种 kernel 有最适合的 core 类型"**：离线 profiling 建立 kernel→core affinity map，运行时优先匹配。类似 ADAngel "oracle policy map" 但应用于 core-kernel 配对而非 bit-width。不是所有 kernel 在 big core 上都更快——某些 memory-bound kernel 在 LITTLE core 上匹配更好。
2. **"Adaptive granularity scheduler——给小核 small tasks，给大核 large tasks"**：动态融合/拆分任务以匹配异构计算能力。类似 Ambulance "protocol-rigged racing"——用偏置使更快一方承担更多工作。不是消除不对称，而是利用不对称。
3. **"On-demand kernel switcher"**：工作负载在 core 间迁移时高效转换 kernel 实现→保持 core-kernel affinity。避免迁移后性能下降（因为新 core 的 optimal kernel 可能不同）。

- 来源：SANI(OSDI'26)

### 实践启发
- **"AMP asymmetry 不应被克服而应被利用"**：performance-collapse paradox 的根源是试图消除不对称（均分任务），而 SANI 的策略是拥抱不对称（给大核更多任务）。类似 Nixie "不要给调度器太多选择"——适当偏置 > 均匀分配
- **"Core-kernel affinity 是被忽视的维度"**：同一种 kernel 在不同 core 类型上效率差异显著→不是所有工作都应在大核上运行。类似 ADAngel "bit-width aware kernel selection"——多维度的 affinity 匹配值得更多关注
- **"三篇移动端论文形成主题簇"**：LifeLine（GC copy→移动卡顿）、Sereno（NPU 带宽→移动 jank）、SANI（AMP 核间不平衡→移动推理延迟）——三篇都来自 OSDI '26，共同主题是**移动端系统性能的系统化解决**

---

## 推荐系统超高效 NAS (Drs.NAS)

### 核心问题
推荐系统占 Meta **70%+ AI 推理 cycle**（超大规模数据中心主导工作负载），但人工设计 DRS 架构无法 scale——需要 costly iterative exploration by domain experts。NAS 自动化搜索但面临两个瓶颈：(1) **搜索成本极高**——反复训练-验证 candidate architecture→5-18 GPU-hours→无法快速迭代 (2) **搜索结果不够高效**——仍 computation/memory-heavy→实际部署困难。

### 关键洞察

1. **"Superproxy 度量替代训练验证——zero training cost NAS"**：NAS 的主要搜索成本在训练阶段。Superproxy 是一个无需训练的度量，从 architecture graph 的结构特征直接评估其预测质量和计算效率→消除训练开销。类似 Merlin "per-object characterization 替代 workload classification"——用一个智能 metric 替代昂贵过程。
2. **"搜索结果极致高效——模型 108× 更小、89× 更少 FLOPs"**：不仅是搜索过程快（2 min on CPU vs 5-18 GPU-hours），搜索结果的模型本身也极度高效——AUC 持平或更优。类似 ADAngel "oracle policy map"——搜索+结果双优化。证明高效 architecture 可以和高质量预测共存。

- 来源：Drs.NAS(OSDI'26)

### 实践启发
- **"Zero-cost proxy for search"**：不需要训练就能评估 architecture 的好坏→将搜索从 hours 降到 minutes→使 NAS 可以从一次性离线搜索变成迭代快速设计。类似 Kareus "roofline model + single-layer profiling"——用低成本近似替代高成本评估
- **"Search efficiency + result efficiency 同时优化"**：Drs.NAS 不仅高效地找到 architecture，而且找到 highly efficient architecture。这在 NAS 领域是罕见的——搜索成本和搜索结果质量通常存在 trade-off

---

## GPU OS 资源管理 (LithOS)

### 核心问题
数据中心 GPU 利用率极低——Microsoft 52% 平均、Alibaba 10% 中位数、Meta 生产 Ads 仅 27%。这不是硬件不够快，而是 GPU 缺乏 OS 级资源管理抽象。现有方案（NVIDIA MPS 粗粒度时间复用、MIG 静态分区）和学术方案（Orion/REEF/TGS 的 operator 级调度）都存在三个根本缺陷：(1) 调度粒度过粗→head-of-line blocking (2) 缺乏透明性→需修改 ML 框架或驱动 (3) 无资源隔离。CPU 上 OS 用了几十年的多任务调度在 GPU 上几乎不存在。

### 关键洞察

1. **"TPC 级空间调度 + TPC Stealing——GPU 的 work stealing"**：以单个 Texture Processing Cluster（GPU 计算单元，A100 有 108 个）为调度粒度→空闲 TPC 可被其他 workload "偷走"→动态重分配。类似 GO 调度器的 work stealing——TPC 是 GPU 的 "P"（logical processor）。配合 online kernel latency predictor（按 batch 内 ordinal position 唯一标识 kernel node）→调度决策有数据依据。
2. **"透明 kernel 原子化——GPU 的 time-sharing primitive"**：CPU 有 timer interrupt→OS 可抢占；GPU 没有→一个 30ms 的 LLaMA 3 kernel 阻塞所有后续 work。LithOS 通过修改 QMD (Queue MetaData) 的 program address 注入 Prelude→将 kernel thread blocks 拆分 "atoms"（子集）→在 atom 边界重新调度→**55% 延迟波动下降**。不需要编译器、源码、PTX——完全透明。类似 GraCE "编译器桥接高层语义和底层硬件"——在底层做透明变换。
3. **"Two-point Amdahl 插值——轻量 hardware right-sizing"**：仅需 1 TPC 和 all TPCs 两次测量→拟合 `l = m/t + b`（串行+并行部分）→预测 kernel 实际利用的 TPC 上限→分配过剩的 TPC 给其他 work。**26% GPU capacity 节省，<4% perf hit**。类似 Kareus "roofline + single-layer profiling"——用低成本近似替代高成本详尽探索。
4. **"Compute vs memory-bound kernel → DVFS 决策"**：计算密集 kernel 保持高频（对频率敏感）→内存密集 kernel 降频（对频率不敏感）→25% 总 GPU 能耗节省（7% perf hit）。采用保守策略（高 learning period + 从 max freq 渐进降），因为 GPU 频率切换延迟高（~50ms）。

- 来源：LithOS(SOSP'25)

### 实践启发
- **"OS 抽象移植到 GPU 是 paradigm shift"**：CPU OS 用了几十年的 time-sharing、空间调度、isolation、DVFS——LithOS 证明这些抽象对 GPU 同样有效。从 "GPU 是黑盒加速器" 到 "GPU 是可调度计算平台" 的范式转变
- **"Transparency = adoption"**：不修改模型/框架/runtime 是 LithOS 的最高设计原则——贯穿 Rust 实现（~5K 行）+ CUDA Driver API interposition。类似 hS/Incr "bolt-on" 哲学——降低 adoption barrier 比追求 optimal 更重要
- **"Kernel atomization = GPU 抢占的务实方案"**：GPU 没有硬件 timer interrupt→atomization 以软件方式实现 "伪抢占"→在 atom 边界重新分配 TPC。这是一个**被硬件限制但可通过软件创新绕过的案例**
- **"Per-kernel right-sizing > whole-model right-sizing"**：不同 kernel 的 TPC scaling 行为差异极大（部分线性 scaling、部分快速 diminishing returns）→per-kernel 决策远优于 uniform 分配。类似 SANI "core-kernel affinity"——细粒度差异化 > 全局统一策略
