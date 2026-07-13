# Strata(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-xie-zhiqiang.pdf
- **年份**: 2026 (July 13–15, Seattle, WA)
- **全称**: Strata: Hierarchical Context Caching for Long Context Language Model Serving
- **作者**: Zhiqiang Xie (Stanford & NVIDIA), Ziyi Xu (SJTU), Mark Zhao (CU Boulder), Yuwei An (CMU), Vikram Sharma Mailthody (NVIDIA), Scott Mahlke (NVIDIA & UMich), Michael Garland (NVIDIA), Christos Kozyrakis (NVIDIA & Stanford)
- **集成**: SGLang 开源项目, 已在多家 AI 公司生产部署
- **类型**: 论文-系统 (LLM serving + I/O + scheduling)
- **一句话 TL;DR**: 通过 GPU 辅助 I/O（解耦 GPU 和主机内存布局）和缓存感知调度（延迟命中消除、平衡批处理、气泡填充），Strata 在长上下文 LLM 推理上比 vLLM-LMCache 最高提升 5× 吞吐、比 TensorRT-LLM 最高提升 3.75×，同时不损害短上下文性能。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **PagedAttention** | 将 KV cache 按固定大小页面非连续分配（类似虚拟内存） | 问题根源：小页面（1-32 tokens）导致 I/O 碎片化 |
| **Layer-first layout** | GPU 内存中按层序存储所有 token 的 KV（Layer 0 连续，然后 Layer 1...） | 对计算友好但对 I/O 不友好——单个逻辑页散成 L 个非连续片段 |
| **Page-first layout** | 同一页的所有 layer 连续存储 | 对 I/O 友好（大块连续传输）但对计算不友好 |
| **GPU-assisted I/O** | 启动 CUDA kernel 做 GPU↔CPU 数据搬运（而非 cudaMemcpyAsync DMA） | Strata 核心创新：在小数据上实现高带宽 |
| **Delay hit** | 多个请求在同一 cache miss 被解决前并发发起，导致被当做 cache miss 的冗余计算 | 高吞吐下严重影响有效 cache hit rate |
| **HiRadixTree** | 扩展 SGLang RadixTree 支持 transient node（in-queue / in-flight 标记） | 用于追踪 delay hit 状态 |
| **Bundle hit** | 多个请求共享同一 context 且被调度到同一 batch | scheduling 的正面利用 |
| **Balanced batch** | 配比 prefill 计算量恰好覆盖 KV cache 加载延迟的 batch | 消除 loading-bound stall |
| **Bubble filling** | 在 PCIe I/O stall 期间插入 decoding batch（不冲突的 HBM 带宽密集型任务） | 提高整体利用率 |
| **Selective-write-through** | 仅当访问计数超过阈值时才备份 KV cache page | Strata 默认写策略 |
| **TTFT** (Time To First Token) | 首 token 延迟 | 用户感知延迟的核心指标 |

## 背景与动机

### 问题
- LLM context window 快速增长（Gemini、Claude 达到 1M tokens，Qwen 2M）
- KV cache 内存占用巨大：Llama-8B 的 40GB HBM 只能容纳 ~0.3M tokens
- 生产线采用层次化缓存（GPU HBM → CPU DRAM → SSD），但 **I/O 成为主导瓶颈**
- Figure 1 核心发现：在 Qwen2.5-14B + LooGLE 下，**74% 的 prefill 时间被 KV 传输阻塞**，导致最多 4× 吞吐下降

### 三个具体挑战

**挑战 1: KV Cache 碎片化 → PCIe 带宽利用率低**
- PagedAttention 使用 1-32 token 的小页面 → 单次传输仅 KB 级
- Little's Law: `Throughput = Concurrency × Size / Latency` → 小 S 导致低利用率
- 8192 tokens 的 KV 传输在 PCIe 5.0 上仅利用 ~22% 带宽，在 GH200 NVLink 上低至 5%
- 增大页面虽能改善带宽但严重损害 cache hit rate（Figure 2: page 512 比 page 1 的 TTFT 差 2×）
- Layer-first 布局进一步碎片化：一个逻辑页散成 L 层非连续片段

**挑战 2: 调度器感知不到 cache 加载成本 → delay hits**
- 当 context 远长于新输入 token 时，cache 加载时间超过 prefill 计算时间 → loading-bound
- Delay hit: 多个请求在 cache miss 解决期间并发到达，都在做冗余 prefill
- Agentic workload (Mooncake trace): 38% 请求在 1s 窗口内共享 ≥6K token 前缀
- 异步调度器（准备下一 batch 时当前 batch 还在执行）延长了 cache miss 窗口 → 加剧 delay hit

**挑战 3: 存储层延迟更高**
- SSD 读取延迟是 PCIe 的数百倍，现有方案无法有效掩盖

### 我的分析
这是 LLM serving 方向非常工程化的系统论文。和前面几篇 CXL tiered memory 论文（TMO/PACT/CAMP/M5）不同，这篇面对的是更上层的应用问题——在 GPU 内存层级之间管理 KV cache 而非通用内存页。但有趣的是，底层原理（Little's Law、I/O 碎片化、比例调度）是相通的。

## 方案介绍

### 整体架构 (Figure 4)

```
Request Queue → Scheduler (HiRadixTree) → GPU Executor
                       ↓                        ↓
                  Cache Controller ←→ GPU HBM ↔ CPU DRAM ↔ SSD
```

三大组件：
1. **Cache Controller** (§4.2) — 数据平面
2. **Scheduler** (§4.3) — 控制平面
3. **HiRadixTree** — 元数据（类似页表）

### 关键创新 1: GPU-Assisted I/O (§4.2)

**原理**: 启动 CUDA kernel（而非 cudaMemcpyAsync）做 GPU↔CPU 数据传输。

**优势**:
1. **高并发 C**: GPU 可启动数千线程做并发 I/O（CPU 只能数十个）
2. **低粒度开销 S**: GPU I/O 的 efficient 粒度只需 128B（vs DMA 需要 MB 级），即使单 page（KB 级）也能高效传输
3. **灵活内存布局**: kernel 中的轻量计算可以 on-the-fly 做 layout 变换

**Interference 控制**:
- 仅用 **2 个 CUDA blocks × 1024 threads**（约 2 SMs）
- 达到 48 GB/s（H200），同时 prefill 性能损失 <5%、decode 损失 <10%
- 使用 low-level instructions bypass cache 以避免污染
- 同时兼容 AMD ROCm backend

**Layout Transformation** (Figure 6):
- GPU 侧保持 layer-first（计算友好）
- Host 侧使用 page-first（传输友好，连续大块）
- I/O kernel 在传输时做地址变换：一个算术操作即可
- 解耦 GPU 和 host 的布局要求 → 两端各自最优

**三种写策略**:
| 策略 | 行为 | 适用场景 |
|------|------|---------|
| write-back | 仅 eviction 时备份 | 资源受限环境 |
| write-through | 每次生成就备份 | 对话场景 |
| selective-write-through (默认) | 访问计数超阈值才备份 | 通用（阈值 2，可调） |

### 关键创新 2: Cache-Aware Scheduling (§4.3)

分三阶段：

**1) Delay Hit Deferral (§4.3.1)**
- HiRadixTree 引入 transient node: `in-queue`（请求引用了新 context）、`in-flight`（cache 正在计算中）
- 新请求匹配到 transient node → defer 到下一轮，排到队首
- 默认匹配阈值: 100 tokens（避免短前缀匹配触发不必要延迟）
- 完成后 transient node 转为 standard node

**2) Balanced Batch Formation (§4.3.2, Algorithm 1)**
- 定义 `loading_bound` 阈值: load/compute ratio > 100（硬编码，硬件绑定）
- 遍历队列时：能放入 batch 且不造成 loading-bound → 加入；否则 → 移入 deprioritized 列表
- 优先加入 bundle hit 请求（共享 context 的请求）
- Batch 未满则从 deprioritized 列表中补充
- 防止饥饿：deprioritized 请求保序，每轮从队列首起

**3) Bubble Filling (Stall Hiding) (§4.3.3)**
- 当 batch 仍是 loading-bound 时：推迟 prefill，先执行 decoding batch
- Decoding 饱和 HBM 带宽，loading 饱和 PCIe 带宽 → 资源不冲突
- 也可以插入 prefill batch（适用于 P-D disaggregated 系统）

### 实现细节
- 集成到 SGLang v0.4.5
- Prefill-decode co-location 设计
- 调度器的关键路径用 C++ 实现（SGLang 主调度器是 Python）
- Default: selective-write-through，threshold=2
- Default GPU I/O: 2 blocks CPU→GPU（critical path），1 block GPU→CPU（non-critical）

## 证据与评估

### 测试环境
- **3 种硬件平台**:
  - H200: 8×H200 + NVLink + Sapphire Rapids + 1.6TB DRAM + PCIe 5.0 (64 GB/s)
  - H20-storage: 8×H20 + Intel P5510 NVMe (7 GB/s)
  - GH200: Grace Hopper Superchip + NVLink C2C (384 GB/s CPU↔GPU)
- **3 个模型**: Llama-3.1-8B, Qwen2.5-14B-1M, Llama-3.1-70B (TP=4)
- **4 个数据集**: LooGLE (21.6K avg input), NarrativeQA (54.8K), ReviewMT (17.7K, multi-agent), ShareGPT (680, short-context)
- **5 个 baseline**: vLLM, vLLM-LMCache, TRT-LLM, TRT-LLM-HiCache, SGLang-HiCache

### 关键结果

| 实验 | 结果 | 要点 |
|------|------|------|
| Llama-8B, LooGLE | **3.2×** vs SGLang-HiCache, **2.6×** vs vLLM-LMCache, **1.9×** vs TRT-LLM-HiCache | 吞吐提升 |
| Qwen-14B, LooGLE | **3.9×** vs SGLang-HiCache, **2.1×** vs vLLM-LMCache, **1.9×** vs TRT-LLM-HiCache | |
| Llama-70B, LooGLE | **5×** vs SGLang-HiCache, **5×** vs vLLM-LMCache, **3.75×** vs TRT-LLM-HiCache | 最大模型获益最大 |
| NarrativeQA (warm cache) | **2.3-2.6×** vs vLLM-LMCache | 稳态下仍有大幅提升 |
| ShareGPT (short) | 与 SGLang/SGLang-HiCache 持平 | 不损害短上下文性能 |
| ReviewMT (multi-turn) | **1.7×** vs SGLang-HiCache, **2.3×** vs vLLM-LMCache/TRT-LLM-HiCache | 更长解码减少了 prefill 优势但仍显著 |

### 消融实验 (Figure 9)

| 组件 | 峰值吞吐提升 | 分析 |
|------|------------|------|
| Strata-IO only | **2.3×** | GPU-assisted I/O 在高负载下主导 |
| Strata-Schedule-Only | **1.8×** | 调度在低负载下主导 |
| Strata-IO-LPM | 低负载好，高负载衰退 | 减少 on-device page reuse 但 cache eviction 频繁后失效 |
| Full Strata | 始终保持优势 | I/O + scheduling 互补 |

### 内存布局解耦 (Figure 13)
- DeepSeek-V3 on 8×H20: page-first layout 比 layer-first + large page 的 TTFT 改善 **2.1×**，吞吐 +**1.3×**

### GH200 跨平台 (Figure 14)
- SGLang-HiCache-GH 带宽从 40→150 GB/s，但**仍不如 Strata-PCIe**
- Strata-GH 接近 Oracle（无限带宽）性能
- **纯硬件升级不足以解决软件瓶颈**

### Delay hit 分析 (Figure 12)
- Cache resolve time 越长、吞吐越高 → delay hit 越严重
- 1 req/s 时影响可忽略；100 req/s 时 hit rate 大幅下降

### 不同 cache distance 下各组件贡献 (Figure 11)
- Min cache distance: delay hit mitigation 贡献最大（+42% throughput）
- Shuffle: I/O + balanced batch 各自贡献显著
- Max cache distance: I/O 机制贡献 95% 提升

## 整体评估

### 真正的新意
1. **GPU-assisted I/O for KV cache**: 用 CUDA kernel 而非 DMA 做 KV 传输，是全新的应用场景。之前 GPU I/O kernel 用于 graph traversal [EMOGI] 等场景，Strata 首次将其用于 LLM serving
2. **Layout decoupling**: Layer-first (GPU) vs page-first (host) 的 on-the-fly 变换，解决了 LLM serving 中长期存在的 layout tension
3. **Delay hit 在 LLM serving 中的首次系统性处理**: 将 networking 领域的概念移植到 LLM 调度，并通过 transient node 机制解决

### 优点
- **生产部署验证**: 已集成到 SGLang，在多家 AI 公司生产运行
- **跨硬件平台**: H200 PCIe、GH200 NVLink、H20+SSD 全验证
- **不损害短上下文**: 这是很多 LLM 优化系统做不到的——为长上下文优化往往伤害短上下文
- **GH200 实验揭示了软件栈不足**: 纯硬件带宽升级不足以解决碎片化 I/O 问题
- **消融实验清晰**: I/O 方案和调度方案各自的价值和交互很清楚

### 局限
1. **GPU I/O kernel 仍然消耗 SM 资源**: 虽然经过 carefully tuned（≤5% prefill 损失），但确实是非零开销，未来需要专门的 on-chip I/O accelerator
2. **公平性**: 调度器优先吞吐和 I/O 效率，可能对个别请求不公平（SLO violation），需要加入 SLO-aware 机制
3. **模型覆盖**: 仅支持 dense KV cache（standard attention），不覆盖 sparse/linear attention 的混合模型
4. **存储层 prefetch**: 当前仅与排队延迟重叠，未来需要更深的 prefetch pipeline
5. **公平性比较**: 大部分 baseline 未针对长上下文特意调优（如 TRT-LLM 的默认 page size 32），部分提升可能来自 baseline 配置不佳

### 与前面 CXL 论文的交叉

Strata 处理的是 **GPU 内存层级内的数据搬运问题**（HBM↔DRAM↔SSD），而 PACT/TMO/CAMP 处理的是 **CPU 内存层级内的页面放置问题**（DRAM↔CXL/NUMA）。有趣的是：

| 共通问题 | CXL Tiered Memory | LLM KV Cache |
|---------|-------------------|--------------|
| 碎片化 | 4KB page 迁移 | 1-32 token page 传输 |
| 粒度 tension | 大页 I/O 高效但浪费内存 | 大页 I/O 高效但降低 cache hit rate |
| 延迟隐藏 | 重叠 I/O 与计算 (PACT) | 重叠 I/O 与 prefill 计算 (Strata) |
| 反馈信号 | PSI (TMO) / PAC (PACT) | load/compute ratio (Strata) |
| 布局优化 | CHA/TOR 观测 (PACT) | layer-first vs page-first 解耦 (Strata) |
| 迁移/传输策略 | eager demotion + adaptive promotion | 三种 write policy + balanced batch |

**本质上 Strata 的"均衡批处理"和 PACT 的"eager demotion + adaptive promotion"都是同一类 problem——如何在高碎片化、动态负载下平衡 I/O 带宽分配和计算利用率。**

### 可复用启发

1. **GPU-assisted I/O 是未来趋势**: 对于需要小数据块高频传输的场景（KV cache、embedding table、graph data），GPU kernel 搬运比 DMA 更灵活高效。CUDA 12.8 新出的 cudaMemcpyBatchAsync 是一个折中方案

2. **Layout decoupling 模式**: 计算和 I/O 各自需要不同的数据布局，通过轻量在线变换解耦二者——这个模式可推广到其他 GPU 数据管理场景（如 MoE expert loading、分布式训练的 gradient allreduce buffer 布局）

3. **Delay hit 在分布式缓存系统（不仅是 Web cache/CDN）中普遍存在**: 任何有"cache miss → 回源 → 填充"过程的系统都可能遇到，Strata 的 transient node 机制是一个轻量级的解决方案

4. **Little's Law 用于诊断 I/O 瓶颈**: `X = C × S / L` — 要提升吞吐，只能增大并发 C、增大传输 S、或降低延迟 L。Strata 分别通过 GPU 高并发（↑C）、page-first layout（↑S）、PCIe→NVLink（↓L）来改善

5. **硬件升级不一定能解决软件瓶颈**: GH200 实验令人震撼——6× 带宽提升但 Strata-PCIe 仍然胜出。说明在利用新硬件能力之前，先要修好软件栈的碎片化和调度问题

6. **"不损害短上下文"的设计约束**: Strata 的意图性设计——在优化 paths 上集中资源、默认行为回退到 SGLang 基线——保证了不影响现有 workload

7. **SGLang 作为 LLM serving 的研究平台**: 其可扩展性（HiRadixTree 扩展 RadixTree）和与生产部署的紧密连接，是 LLM serving 系统研究的理想基础
