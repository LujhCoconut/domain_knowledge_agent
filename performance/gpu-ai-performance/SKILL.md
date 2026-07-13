# GPU / AI Performance

GPU 与 AI/ML 推理和训练的性能优化知识。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| LLM 层次化 KV Cache 管理 | GPU-assisted I/O, PagedAttention, layout decoupling, delay hit, TTFT | Strata(OSDI'26) |
| LLM Serving 调度 | balanced batch, bubble filling, bundle hit, cache-aware scheduling | Strata(OSDI'26) |
| GPU-CPU 数据传输 | PCIe bandwidth utilization, Little's Law, DMA vs kernel I/O | Strata(OSDI'26) |

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

## 待补充

- GPU 训练性能优化（分布式训练、FSDP、TP/PP/EP 并行策略）
- CUDA kernel 性能调优
- GPU 显存管理
- AI 编译器优化
- MoE 推理优化
