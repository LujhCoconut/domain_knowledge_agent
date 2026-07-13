# ECHO(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-liu-guangda.pdf
- **年份**: 2026 (July 13–15, Seattle, WA)
- **全称**: ECHO: Efficient KV Cache Offloading with Lossless Prefetching for Serving Native Sparse Attention LLMs
- **作者**: Guangda Liu, Wenhao Chen, Chengwei Li, Zhenyu Ning (SJTU), Jing Lin, Yiwu Yao (Huawei), Quan Chen, Shixuan Sun, Jieru Zhao (SJTU), Minyi Guo (Guizhou Univ & SJTU)
- **开源**: https://github.com/sjtu-zhao-lab/ECHO
- **类型**: 论文-系统 (LLM serving + sparse attention + KV cache offloading)
- **一句话 TL;DR**: 针对原生稀疏注意力 LLM (DeepSeek-V3.2 DSA) 的 GPU HBM 容量瓶颈，ECHO 通过 graph-friendly cache manager（完全 GPU 图内执行）+ 无损 intra/inter-query prefetching（利用 index score 的数值可预测性），实现最高 **2.1×** 生成吞吐提升（vs SGLang），offloading 开销仅占 0.28% 解码延迟。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **Native Sparse Attention** | 训练时内置的稀疏注意力（如 DeepSeek-V3.2 的 DSA），不同于训练后附加的 training-free 方法 | ECHO 的核心目标模型类型 |
| **DSA** (DeepSeek Sparse Attention) | 通过轻量级 indexer 计算 token importance，只对 top-k (k=2048) token 做注意力 | ECHO 适配的注意力机制 |
| **Indexer** | DSA 中用于评估 token importance 的 MQA-like 模块（小头数+小维度+FP8） | ECHO 的 prefetching 依赖 index score 数值可预测性 |
| **MLA** (Multi-head Latent Attention) | 低秩压缩 KV 到 latent vector C，推理时只缓存 C | DeepSeek-V2/V3 的注意力机制，减少 KV cache 但增加了 DP 拆分复杂性 |
| **Graph-Friendly Cache Manager** | 所有元数据用固定长度整数 tensor + 并行 GPU 操作，完全兼容 CUDA Graph | 解决 Challenge 1: 动态 offloading 的管理开销 |
| **Intra-query Prefetching** | 在解码时，利用 EMA 预测 top-k 阈值，在 indexer 计算期间提前预取 KV | 解决 Challenge 2: 串行 indexer→recall→attention 依赖 |
| **Inter-query Prefetching** | 在 prefill 时，利用 query block 的串行处理，前一个 Q block 的 selected tokens 在下个 Q block 计算时并发预取 | Prefill 阶段的 prefetching |
| **EMA** (Exponential Moving Average) | `ŝ_{t+1} = α·ŝ_t + (1−α)·s_t`，预测下一解码步的 top-k 阈值 | 将 top-k selection 近似为 top-p selection 的关键技术 |
| **Radix Select Top-K** | 构建分数直方图并多轮过滤的近似 top-k 算法 | Inter-query prefetching 使用其单轮粗粒度过滤 |
| **Warp Specialization / Software Pipeline** | 将不同 warp 组分配不同角色（TMA 加载 / GEMM 计算 / Prefetch），用异步 barrier 重叠执行 | Fused prefetching kernel 的实现基础 |
| **PD Disaggregation** | Prefill-Decoding 分离部署 | ECHO 推荐在解码实例开启 offloading，prefill 实例关闭 |

## 背景与动机

### 问题
- **稀疏注意力减少计算但不减少 KV cache 大小**：DSA 的 indexer 还需额外存储 K cache → KV cache 线性增长**更陡峭**
- DeepSeek-V3.2 (AWQ) 8×H20: 模型参数占 60%+ HBM，仅剩 ~511K token/DP worker 给 KV cache
- 100K token 请求只能并发 3-4 个 → 稀疏 attention kernel 本身算术密度低，需要**更大的 batch size** 才能饱和硬件
- **死循环**: HBM 容量限制 batch size → 低 batch size 无法饱和硬件 → 低吞吐

### 两个核心挑战

**Challenge 1: 动态 offloading 难以兼容 CUDA Graph 执行**
- 现有 KV cache 管理系统依赖动态 tensor slicing/concatenation → 无法被 graph capture
- 无 graph execution: DeepSeek-V3.2 吞吐下降 1.5×（比 dense 模型的 1.2× 更严重，因为稀疏 attention 有更多 kernel launches）
- 现有 cache allocator: SGLang 一次 alloc+free 约 12μs，ECHO 的 graph-friendly 版本缩至 6–8μs
- 即使分段 graph 也无法解决——每层每步都需 eviction/recall → graph 在所有层断裂

**Challenge 2: Top-k 语义阻止了 indexer 期间的 prefetching**
- DSA 必须完成对所有 L 个 token 的 index score 计算才能确定 top-k
- Indexer 计算 O(L²)，recall O(Lk)，当 L 足够大时 indexer 比 recall 耗时更长
- 但 indexer 和 recall 各占不同硬件资源（GPU compute vs PCIe BW），理论上可重叠
- 现有方案 (InfiniGen, FreeKV, CLO) 的 prefetching 基于 layer-to-layer/inter-step 近似 → **有损**（准确率下降）

### 我的分析
这是 OSDI '26 第二篇 LLM serving 论文（前一篇是 Strata）。二者对比很有意思：Strata 处理 dense attention 的层次化 KV cache 碎片化问题，ECHO 处理 sparse attention 的动态 token-level offloading 问题。ECHO 的核心洞察——"index score 的 top-k 阈值可以用 EMA 预测"——非常精巧，将一个理论上的串行依赖（必须先算完所有 score 才能知道 top-k）转化为了近似可并行的 top-p 问题。

## 方案介绍

### 整体架构 (Figure 5)

```
DP Scheduler → DP Attention Worker
                    ├── GPU KV Cache Pool (per-layer metadata)
                    ├── Host KV Cache Pool (per-model, large)
                    ├── Graph-Friendly Cache Manager
                    │     ├── Allocate (parallel atomicAdd)
                    │     ├── Free (parallel argtopk + scatter)
                    │     └── Recall (scatter + UVM transfer)
                    └── Fused Prefetching Kernels
                          ├── Intra-query (decoding)
                          └── Inter-query (prefill)
```

### 关键创新 1: Graph-Friendly Cache Manager (§4)

**核心设计**: 所有元数据用固定长度整数 tensor 存储于 GPU，所有操作用并行 GPU kernel 实现。

**五种元数据** (Table in §4.1):
- `GPUTokenFree`: bitmap, 标识 GPU pool slot 是否空闲
- `GPUTokenPriority`: 每个 slot 的 eviction 优先级（类似 LRU）
- `GPUIndicesBuffer`: allocate/free 操作的输出 buffer
- `GPUTokenToHost`: GPU slot → host slot 映射
- `HostTokenToGPU`: host slot → GPU slot 映射

**Per-layer 而非 per-model 管理**: 稀疏 attention 在不同层选择不同 token → 每层 cache 状态不同 → 需要 per-layer metadata。Metadata 总量：`4NH + 13NG` bytes = ~10MB/layer for DeepSeek-V3.2 (610MB total)。

**三个并行操作**:
1. **Allocate**: 并行读 `GPUTokenFree` → `atomicAdd` 到 global counter → 返回值确定哪些线程获得 slot → 更新 metadata
2. **Free**: 先保护 selected tokens 的 priority → `argtopk` 选出最低 priority slots → `scatter` 更新 metadata → 无需实际 KV 数据传输（host 有完整备份）
3. **Recall**: 用 `HostTokenToGPU` 检查哪些 selected tokens 不在 GPU → allocate + free 腾出空间 → UVM 直接 kernel 内读取 host memory → 更新双向映射

**与 CUDA Graph 兼容的关键**: 不使用动态 tensor slicing/concatenation，所有 tensor 固定预分配，只用 atomicAdd/argtopk/scatter 等并行操作。

### 关键创新 2: Intra-query Prefetching for Decoding (§5.1)

**洞察**: DSA 的 top-k selection 可以借助 index score 的数值可预测性近似为 top-p selection。

**机制**:
1. 用 EMA 预测下一个解码步的 k-th highest score: `ŝ_{t+1} = α·ŝ_t + (1−α)·s_t`（α=0.5）
2. 在 indexer 计算期间，token 的 score 一旦超过预测阈值即可被 prefetch
3. 候选 token 数接近 k=2048（EMA 预测准确度高）
4. 全局计数器限制 prefetch 量上限（防止某步预测过低导致过多 prefetch）
5. 已完成 prefetch 的 token 如不在最终 top-k 中 → 无影响（正确性保证），之后可能被 evict

**GPU pool hit rate**: 实测在 InfiniteBench 上大部分层达到 0.97-0.99 — 这意味着 recall overhead 已经很小，prefetching 在低 hit rate 场景收益更大（图 18: hit rate 0.5→1.29×, 0.9→1.51×）

### 关键创新 3: Inter-query Prefetching for Prefill (§5.2)

**洞察**: Prefill 按 Q blocks 顺序处理 → Q block i 的 selected tokens 在 Q block i+1 计算时并发预取。

**近似 top-k**: 只用 radix select 的单轮粗粒度过滤（256-bin histogram + score shift by EMA prediction）
- 目标：最小化 threshold bin size → 最大化选择精度
- score shift with EMA 显著缩小 threshold bin（Figure 9）

### 关键创新 4: Fused Prefetching Kernels with Pipelining (§5.3)

基于 DeepGEMM 的 indexer kernel 改造：

**Intra-query kernel** (解码):
- 3-stage software pipeline: TMA (加载 K blocks) → GEMM (计算 score) → Prefetch (比较阈值 + 启动 UVM 加载)
- Query vector 持久化在 shared memory
- 预取 warp 组额外 pipeline stage 避免阻塞 indexer

**Inter-query kernel** (prefill):
- 按 Q blocks 外层循环 + K blocks 内层循环
- Prefetch warp 组在当前 Q block GEMM 完成后启动，与下一 Q block 的 TMA/GEMM 重叠

## 证据与评估

### 测试环境
- **硬件**: 1 node, 8×H20 (96GB), 64GB/s PCIe Gen5, 224-core Xeon Platinum 8480+, 1.5TB DRAM
- **模型**: DeepSeek-V3.2-Exp (AWQ 4-bit + 部分层 unquantized), FP8 原始模型
- **Baseline**: vLLM v0.11.1, SGLang v0.5.4
- **部署**: SGLang/ECHO DP8 (attention) + TP8 (MoE); vLLM TP8 (attention+MoE)
- **数据集**: InfiniteBench (80-100K tokens, 318 reqs, ~26M input tokens), ShareGPT (短上下文)
- **Host KV pool**: 1.8M tokens (~1000GB host DRAM)

### 关键结果

| 实验 | 结果 | 要点 |
|------|------|------|
| InfiniteBench, max throughput, Inf rate | **2.15×** vs SGLang, **4.1×** vs vLLM | 有效 batch size 从 ~30 (SGLang) / ~1.5 (vLLM) 大幅提升 |
| InfiniteBench, GPU pool 200K | **3.10×** vs SGLang | GPU HBM 越受限，ECHO 优势越大 |
| InfiniteBench, GPU pool 110K | **4.12×** vs SGLang | SGLang/vLLM 严重退化，ECHO 靠 host pool 维持 |
| ShareGPT (短上下文) | TTFT +7.9% max, ITL +2.7–27.8%, e2e +15.9–19.2% (low load) → <4.6% (high load) | 轻负载下延迟开销明显，高负载下可忽略 |
| Offloading 开销 | **1.15ms / all-layer decode (0.28%)** | alloc: 0.17ms, free: 0.57ms, recall: 0.15ms, KV offload: 0.26ms |
| GPU pool hit rate | 0.97–0.99 (大部分层), 最低 0.88 (layer 17) | 高 hit rate 减少了 recall traffic |
| Intra-query prefetch | hit rate 0.5: **1.29×** 加速, 0.9: **1.51×** | End-to-end 增益较小（4%）因 MoE 占主导 |
| Inter-query prefetch | 最大 **1.1×** 加速 | 评估假设 token selection 随机分布 → 实际上重叠更大 |

### 延迟分解 (Figure 16)
- Prefill: ECHO +8.8% per-layer latency (KV offload overhead)
- Decode: ECHO +2.8% all-layer latency; graph replay +5.9ms (CPU launch + metadata)
- Offloading 自身: 仅 0.28% 解码延迟
- 其余 6.8ms 增加来自 DP worker 间 ReduceScatter 同步（ECHO 的更高并发导致的 communication jitter）

### Per-task 分析
- Code.Debug: +27.07%, En.MC: +2.83%, En.QA: +7.11%
- Code.Run: −1.74% (原因：任务请求少 + 长尾输出 → DP imbalance 弱化了 ECHO 优势)
- 收益一致性不如 max throughput benchmark（per-task 请求少 + 输出长度偏斜大）

## 整体评估

### 真正的新意
1. **Graph-friendly cache manager 设计**: 用固定长度整数 tensor + 并行 GPU 操作替代 CPU 控制的动态 allocator，首次让动态 token-level KV cache offloading 兼容 CUDA Graph
2. **EMA 预测 top-k 阈值**: 将 top-k selection 近似为 top-p，数值可预测性是一个精巧的发现（而非 heuristic）
3. **Fused kernel with warp specialization**: 将 prefetching 融入 indexer kernel 的 software pipeline，基于 DeepGEMM 的高性能 GEMM kernel 改造

### 优点
- **无损**: prefetching 不引入任何准确率损失（区别于 InfiniGen/FreeKV/CLO 的有损 prefetch）
- **系统基础**: Graph-friendly cache manager 不仅服务于 DSA，可扩展到其他 token-wise/block-wise 稀疏注意力
- **实现务实**: 基于 SGLang + DeepGEMM + Triton 实现，兼容性好
- **生产就绪**: PD disaggregation 支持、Multi-GPU DP+TP 部署、continuous batching
- **Offloading 开销极低**: 0.28% 解码延迟 → 证明了"graph-friendly + parallel GPU ops"的可行性

### 局限
1. **Intra-query prefetch 的 end-to-end 收益受限于 MoE 占比**: MoE 层占 ~70% 解码时间 → prefetch 节省被稀释 (4% e2e)
2. **Inter-query prefetch 收益低估**: 假设 token selection 随机分布，实际 vertical attention pattern 下重叠更大
3. **EMA 预测需要 per-layer per-step tracking**: 状态管理增加了一定复杂度
4. **仅支持 DSA/MLA**: 虽然 cache manager 通用，但 prefetching 依赖 DSA indexer 的具体数值特性
5. **轻负载延迟上升**: ITL +27.8% at low load — 当前 offloading 是 throughput-first 技术

### 与 Strata(OSDI'26) 的对比

| 维度 | Strata(OSDI'26) | ECHO(OSDI'26) |
|------|----------------|---------------|
| **目标模型** | Dense attention (Llama, Qwen) | Native sparse attention (DeepSeek DSA) |
| **Cache 粒度** | Per-request (整个 request 的 KV cache) | Per-token (动态 evict/recall 单个 token) |
| **Offloading 模式** | Static (prefill 时全部加载, decode 期间不变) | Dynamic (每步每层可能 evict/recall) |
| **I/O 机制** | GPU kernel I/O (128B 粒度) | UVM + GPU kernel (graph-compatible) |
| **Prefetch** | N/A (static offload) | Lossless EMA prediction + fused pipelining |
| **缓存管理** | Layer-first vs page-first layout 解耦 | Per-layer metadata + parallel GPU ops |
| **瓶颈** | PCIe BW 利用率低 (碎片化) | GPU HBM 容量不足 (KV cache 太大) |
| **提升** | 3.2-5× vs vLLM-LMCache | 2.1-4.1× vs SGLang |
| **延迟开销** | ~0 (short context 持平) | 0.28% decode (offload 自身) / +15-19% e2e (low load) |

**互补关系**: Strata 解决的是 "如何高效地搬运大块 cache"（I/O 碎片化），ECHO 解决的是 "如何在 GPU HBM 不够时做动态 token 级置换"（容量瓶颈）。二者可以在不同场景下互补——Strata 适合 dense model 的 request-level caching，ECHO 适合 sparse model 的 token-level offloading。

### 可复用启发

1. **"Graph-Friendly" 作为系统设计约束**: ECHO 展示了如何在 CUDA Graph 约束下重新设计内存管理——固定长度 tensor + 并行 GPU 操作替代动态 CPU 控制。这个模式可推广到任何 GPU 图编译场景（如 TensorRT、XLA）

2. **数值可预测性打破串行依赖**: EMA 预测 top-k 阈值是一个通用技巧——任何"先排序再选择"的 pipeline 都可以考虑用数值预测提前启动后续步骤

3. **Top-k ≈ Top-p 的转换**: 当阈值可预测时，top-k 和 top-p 的语义鸿沟可以桥梁化。这适用于任何需要基于排序做决策的系统

4. **Per-layer metadata 管理**: 稀疏 attention 产生 per-layer 发散的 cache 状态，per-layer 管理比 per-model 更精确。类似模式可能出现在其他层级化系统中

5. **UVM 用于避免 CPU 参与**: 用 GPU kernel 直接通过 unified virtual memory 访问 host memory，既保持 graph-compatible 又消除 host-side interference

6. **PD disaggregation 下的分工**: Prefill 不开 offloading（并发度低）、Decode 开 offloading（并发度高）。这种分工可推广到其他 disaggregated serving 场景
