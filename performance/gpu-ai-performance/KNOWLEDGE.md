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
| 多模型 GPU 显存共享 | memory ballooning, CUDA VMM, elastic tensor, KVPR, time/space sharing, bursty groups | Prism(OSDI'26) |
| 万亿参数 MoE 训练 | overlap-aware partition, synthesized overlap schedule, dynamic bubble filling, pipeline parallelism | Tessera(OSDI'26) |
| 异质分布式训练 (SPMD) | asymmetric sharding, hierarchical communication, graph specialization, dynamic switching | Hetu-v2(OSDI'26) |
| 内核级 Compute-Comm Overlap | chunk-centric overlap, in-kernel communication, tile schedule reshaping, Triton compiler | Syncopate(OSDI'26) |

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
