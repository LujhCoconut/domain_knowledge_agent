# Prism(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-yu-shan.pdf
- **全称**: Prism: Cost-Efficient Multi-LLM Serving via GPU Memory Ballooning
- **系统名**: Prism (balloon driver: kvcached)
- **作者**: Shan Yu (UCLA), Yifan Qiao (UC Berkeley), Mingyuan Ma (Harvard), Yangmin Li (CMU), Shuo Yang (UC Berkeley), Xinyuan Tong (U Edinburgh), Yang Wang (Intel), Zhiqiang Xie (Stanford), Yuwei An (CMU), Shiyi Cao (UC Berkeley), Ke Bao (LMSYS), Deepak Vij, Xiaoning Ding, Yichen Wang (ByteDance), Qingda Lu (Alibaba Cloud), Zhong Wang (Tsinghua), Gao Gao (Novita AI), Harry Xu*, Junyi Shu* (UCLA), Jiarong Xing* (Rice), Ying Sheng* (UCLA) — 五校+六企联合作
- **开源**: https://github.com/ovg-project/kvcached (balloon driver, 已 10K+ GPU 生产部署)
- **类型**: 论文-系统 (multi-LLM serving + GPU memory management)
- **一句话 TL;DR**: 将虚拟机 memory ballooning 思想移植到 LLM serving——用 balloon driver (kvcached) 在 GPU 物理内存层面解耦虚拟/物理地址，弹性回收和再分配显存，统一 time-sharing（模型换入换出）和 space-sharing（模型共存）策略。在生产 trace 上实现 **3.3× TTFT SLO 达成率**、等 SLO 下 **>2× 成本降低**或 **3.5× 更多请求**。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **Memory Ballooning** | 虚拟化技术：hypervisor 动态从 guest VM 回收/分配内存 | Prism 移植到 GPU 多模型 serving 的核心思想 |
| **kvcached** | Prism 的 balloon driver 开源项目名 | GPU 物理内存管理器，解耦虚拟/物理地址 |
| **eTensor** (Elastic Tensor) | PyTorch extension 接口，封装了 CUDA VMM 的 page-level 映射 | 让 serving engine 像用普通 tensor 一样使用弹性内存 |
| **Bursty groups** | 生产 trace 中模型成组活跃、组随时间迁移的现象 | 核心发现：→ 需要混合 time/space sharing |
| **KVPR** (KV Pressure Ratio) | `w_token_rate / shared_kv`，其中 `w_token_rate = token_rate * token_size / SLO` | GPU 内存竞争强度的量化指标 → 驱动模型放置 |
| **Space sharing** | 多模型在 GPU 上共存，静态分区或共享 KV cache | 适合低流量模型和 interleaved 请求 |
| **Time sharing** | 模型换入换出（swapping weights）| 适合 bursty/sporadic 请求和空闲回收 |
| **Slack-aware arbitration** | 基于 Moore-Hodgson 算法按 deadline slack 排序的 GPU 本地调度 | 最大化 TTFT SLO 达成 |
| **Delay hit** | 多请求同时 cache miss 等待填充 → 冗余计算 | 与 Strata 中的同一概念，本节中通过 slack 仲裁缓解 |

## 背景与动机

### 问题
- LLM 推理成本高昂，提供商需同时维持数千基础+微调模型的可用性
- 许多长尾模型有极低请求量但不能下线
- 生产 GPU 利用率 <30%（空闲模型占显存但无请求）
- 现有两派方案各自无法应对真实的动态混合负载

### 核心发现：生产 Trace 分析 (4 条 trace, 58 模型, 长达 16 个月)

**发现 1: Bursty groups — 模型成组活跃并迁移**
- 同一时刻仅 23-50% 模型活跃，活跃组每小时变化 54-766 次
- 类似应用程序的 working set：有常驻模型，有偶尔出现的模型
- 驱动因素：Agentic pipeline 中推理模型 + 辅助模型的不对称调用
- **含义**: 静态分区造成 50% GPU 内存被空闲模型占用的碎片化

**发现 2: Volatile requests — 请求极度动态且不可预测**
- Request rate CV > 1，每模型每小时 40-100 个 idle intervals
- 连续两天同一时间的 traffic 的 Pearson 相关系数接近 0
- 频繁出现 interleaved activity（多模型并发活跃）→ time sharing 导致 model thrashing
- 也频繁出现单模型 burst → space sharing 因无法重新分配空闲内存而未能满足需求

**发现 3: Pure time sharing 和 pure space sharing 谁都不能单独应付**
- Pure time sharing: 交叠活跃期间反复 swap → PCIe transfer + engine re-init 主导 → SLO violations (Fig 2a)
- Pure space sharing: 单模型 burst 时空闲模型锁住内存 → active 模型 KV cache 受限 → queuing delay → SLO violations (Fig 2b)

### 核心洞察
> GPU memory is the unifying bottleneck. Time-sharing is about swapping weights; space-sharing is about scaling KV-cache. Treating GPU memory as an elastic resource — analogous to memory ballooning in virtualization — unifies both strategies under a single mechanism.

### 我的分析
这是 OSDI '26 中唯一的多模型 GPU 共享论文。与前 4 篇单模型 KV cache 论文不同，Prism 上升到了集群级别的模型管理和调度。其 balloon driver (kvcached) 在 CUDA VMM 层面重新抽象了 GPU 内存管理——这是一个系统设计层次的洞察：将内存管理从应用层（PagedAttention）下沉到驱动层（CUDA VMM），让多模型共享成为可能而无需修改 attention kernel。

## 方案介绍

### 三层架构 (Figure 3)

```
Global Scheduler (§6.1) — 模型放置决策，最小化 KVPR
        ↓
GPU-Local Scheduler (§6.2) — Slack-aware request arbitration
        ↓
Balloon Driver (§5) — kvcached: GPU物理内存重分配
        ↓
Serving Engine (SGLang/vLLM) — 单模型推理
```

### 关键创新 1: GPU Memory Ballooning — kvcached (§5)

**现有问题**: 主流 serving engine 用 PagedAttention 管理 KV pool，但使用 PyTorch 预分配的大 tensor 独占 GPU 内存。即使 KV block 空闲，物理内存也被锁死。

**kvcached 设计 (Figure 4)**:
- **CUDA VMM API**: 每个 engine 预留大段虚拟地址空间（virtual allocation），物理内存按 2MB page on-demand 映射
- **eTensor 抽象**: 对 serving engine 暴露为普通 PyTorch tensor，兼容 CUDA Graph，零 attention kernel 修改
- **D1: 统一权重和 KV cache 管理** — 解除模型时直接释放物理页；激活模型时缩小其他模型的物理限额
- **D2: 自动 token block 映射** — 内部 KV cache manager 将不同架构的 token block 映射到虚拟/物理页，不同模型隔离到不同物理页
- **D3: 开销优化** — 连续虚拟布局（所有 layer 的 K/V 在连续虚拟空间 → 2L× 加速分配）、异步预分配缓冲池、2MB 大页 + 优先填充部分使用的页
- **D4: eTensor 透明兼容** — 22 行代码集成 SGLang

**快速模型加载 (§5.3)**:
- **Engine pool**: 预初始化 engine + 虚拟地址空间 → 模型激活时从 pool 取 engine 直接加载权重（免 engine 初始化）
- **KV cache virtual memory manager**: 复用虚拟空间时动态对齐到新模型的 tensor layout
- **Parallel weight loading**: 利用同节点多 GPU 的 NVLink + 切分权重多 GPU 并行加载 → 聚合到目标 GPU
- 流式加载（单 GPU 仅需 30MB buffer）避免干扰运行中模型

### 关键创新 2: 内存中心的控制平面 (§6)

**Global: Load-Aware Model Placement (§6.1, Algorithm 1)**
- **KVPR 指标**: `KVPR = (token_rate × token_size / SLO) / shared_kv` — 量化 GPU 上内存竞争的紧迫度
- **Greedy descreasing KVPR**: 按 `w_token_rate` 降序排模型 → 依次分配到 KVPR 最小的 GPU
- **自然实现互补性**: 高需求模型与低需求模型共置 → 最大化 ballooning headroom
- **迁移节流**: 仅当 `KVPR_current - KVPR_best > τ` 时才迁移（避免抖动）
- **TP 支持**: 将 TP 模型拆分为 t p_size 个 entries，anti-affinity 约束确保不共置

**Local: Slack-Aware Request Arbitration (§6.2, Algorithm 2)**
- 每个 GPU 有 **共享请求队列**（非 per-model queue）
- 应用 Moore-Hodgson 算法：按 TTFT deadline 排序 → 依次加入 → 遇 deadline miss 则移除耗时最长的请求
- Prefill time `er = pr / cr` 可精确估计 → 允许证明最优性（最小化 deadline miss 数）
- Decode 不参与 reordering — TPOT 由内存 headroom 保障

### 模型启停与迁移
- **Eviction**: 基于 idle 阈值（默认 ~45s）→ 释放物理内存，engine+虚拟空间回收到 pool
- **Activation**: 从 engine pool 取 engine + parallel weight loading → 冷启动延迟 < TTFT SLO
- **Migration**: 源实例持续 serving 直到目标就绪 → 重叠迁移延迟与执行

## 证据与评估

### 测试环境
- **硬件**: 4 节点 × 8×H100-80G (NVLink 600GB/s + 100GbE)，双 Xeon 8480+
- **后端**: SGLang + kvcached (~10,400 行 Python + 774 行 C++)
- **模型**: 58 个 (1B-70B)，覆盖 dense/MoE 多架构
- **Traces**: Hyperbolic (4 个月, 24 模型), Arena-Chat (11 天, 84 模型)
- **SLO**: P95 TTFT 0.04-0.13s, P95 TPOT 5.2-50.9ms
- **Baselines**: Static Partition, MuxServe++, QLM (time sharing), ServerlessLLM

### 关键结果

| 实验 | 结果 | 要点 |
|------|------|------|
| TTFT SLO vs request rate | **2.3-3.5×** more reqs at 99% attainment vs MuxServe++/Static | KVPR 保持低压力 |
| TPOT SLO vs request rate | Prism 维持高达成率 | 平衡的负载降低内存引起的 preemption |
| SLO scale sweep | Prism 快速达到 99%，baseline 在最大 scale 仍 <85% | 弹性共享是关键 |
| GPU count sweep | Prism 仅需 **4-5 GPU** 达到 99% SLO（baseline 8 GPU 仍达不到） | 2× 成本降低 |
| 弹性内存 overhead | 仅 3-5% TTFT/TPOT overhead（worst-case, constant load, no sharing opportunity） | 动态映射代价极低 |
| 交叉模型内存共享 | 大幅优于 static partition 的 KV cache 受限导致的 OOM | kvcached 实现无缝 weight↔KV 重分配 |
| 敏感度分析 | idle threshold ~45s 最优, window size ~60s 最优, 性能对参数鲁棒 | 凸曲线表明 trade-off 可控 |

### 生产部署
- kvcached 开源 + 在两家公司的 **10K+ GPU** 集群生产部署
- 集成 SGLang 仅需 **22 行代码更改**
- 兼容 CUDA Graph，无需修改 attention kernel

## 整体评估

### 真正的新意
1. **Memory ballooning 移植到 GPU/LLM 领域**: 将虚拟化中成熟的 balloon driver 概念应用于 GPU 内存管理，这是跨领域的创新移植
2. **CUDA VMM 作为多模型共享的基础设施层**: 在此之前，LLM serving system 全在应用层管理 GPU 内存（PagedAttention, block table, allocation pool）。kvcached 证明了下沉到 CUDA VMM 层可以实现跨模型的弹性共享
3. **KVPR 作为内存竞争的统一指标**: 将 SLO、token rate、token size、KV cache capacity 综合为一个可比较的 scalar → 驱动贪心放置的决策基础
4. **Moore-Hodgson 在 LLM 请求仲裁中的应用**: 经典 deadline scheduling 算法的 LLM 特化（prefill time 可精确估计 → 可证明最优性）

### 优点
- **生产验证充分**: kvcached 开源 + 10K+ GPU 部署 + 两家公司使用
- **极简集成成本**: 22 行代码接入 SGLang，零 attention kernel 修改
- **理论+实践结合**: KVPR 有 bound 分析，调度有 Moore-Hodgson 最优性保证
- **全面的 trace 分析**: 4 条生产 trace (最长 16 个月、129 模型) → 发现 bursty groups 和 volatile requests 两个核心模式
- **统一了之前分裂的 two worlds**: time sharing 和 space sharing 通过内存弹性化统一

### 局限
1. **仅聚焦 GPU 内存管理**: 没有考虑网络（跨节点 KV cache 共享）和 CPU 卸载（PCT 内存层次的其他层级）
2. **Eviction threshold 需要 per-deployment 调优**: 虽然在 ~45s 附近有凸曲线，但最优值取决于 workload pattern
3. **Moore-Hodgson 仅针对 TTFT**: TPOT 是"间接"受益于内存 headroom，可能在特定 decode-heavy workload 中对 TPOT SLO 保护不足
4. **Engine pool 增加了内存开销**: 预分配虚拟地址空间和分布式上下文会占用部分 GPU 内存
5. **大模型 TP 的 anti-affinity 可能受限**: 当集群中仅有少数 GPU 时，TP 模型的碎片化放置可能效率降低

### 与 OSDI '26 其他 LLM 论文的关系

Prism 是 OSDI '26 中唯一上升到集群多模型管理层面的论文（其他 4 篇都是单模型优化）：

| 论文 | 层面 | 核心问题 |
|------|------|---------|
| Strata | 单模型 I/O | KV cache 碎片化传输 |
| ECHO | 单模型 Offloading | Sparse attention 动态 evict/recall |
| DirectKV | 单模型 Kernel | Zero-copy KV-C2C 带宽利用 |
| LMetric | 集群路由 | 请求调度（P-token × BS） |
| **Prism** | **集群 GPU 管理** | **多模型弹性显存共享** |

Prism 和 LMetric 是天然互补的：LMetric 做"请求发给哪个实例"→ Prism 做"模型放在哪个 GPU"→ 前者偏路由，后者偏 placement。二者结合可以形成一个完整的多模型集群调度栈。

### 可复用启发

1. **Memory ballooning 思想可推广到其他加速器**: FPGA、TPU、NPU 等也有类似的内存管理问题。将虚拟化层引入 accelerator memory management 是通用模式
2. **下沉内存管理到驱动层**: PagedAttention 等应用层内存管理有其局限——跨应用（模型）不可见。kvcached 证明了驱动层（CUDA VMM）是更好的抽象层
3. **KVPR 作为"需求/容量"比的指标设计**: 将多维（SLO, token rate, token size, capacity）压缩为一个比较标量 → 适合贪心/启发式决策
4. **Divide: space vs time complexity → Unify: memory-centric view**: 当两个优化维度看似矛盾时，找到它们共享的瓶颈资源（GPU 内存）并以该资源为中心重构问题
5. **Engine pool 模式**: 预初始化资源池 + 按需分配 → 消除冷启动延迟。可推广到其他"状态重"的服务（DB connection pool, model serving container pool）
6. **2MB page + on-demand mapping**: 平衡了粒度（2MB 不太大不太小）和碎片化，是 GPU 内存 ballooning 的 sweet spot
