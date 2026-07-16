# Bidaw(FAST'26)

- **来源**: https://www.usenix.org/system/files/fast26-hu-shipeng.pdf, FAST '26
- **作者**: Shipeng Hu, Guangyan Zhang (Tsinghua), Yuqi Zhou (CUGB), Yaya Wei, Ziyan Zhong (China Telecom), Jike Chen (Tsinghua)
- **一句话 TL;DR**: 交互式 LLM serving 的 KV cache 双向感知系统——计算端 I/O 感知请求调度（双队列+KV-size HRRN）+ 存储端基于 LLM 回答长度预测用户访问模式的淘汰策略+存储高效张量缓存，延迟降 3.58×，吞吐升 1.83×，逼近全内存 KVs 上界。
- **资料类型**: 论文-系统（AI 推理优化+工业 workload）

---

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| Interactive LLM Serving | 多轮人机对话 LLM 推理（用户与 LLM 交替回应） | 目标场景 |
| Two-tier Storage | Performance Layer (host memory) + Capacity Layer (SSD) | KV cache 的存储架构 |
| KV Cache (KVs) | 历史对话的 Key-Value 张量，需要加载到 GPU 才能推理下一轮 | 缓存的核心对象 |
| I/O-induced Request Blocking | 请求因 KV 加载慢阻塞 GPU→后续快请求饥饿 | 现有方案的致命问题 |
| Weighted Reuse Distance | 两次访问间隔内被访问的其他 KVs 总大小 | 量化 KV 访问时空局部性的核心指标 |
| Dual-queue Separation | Ready Queue (KV 在 host memory) + Preparing Queue (KV 在 SSD) | I/O 感知调度的基础 |
| disk-HRRN | 基于 KV 大小和等待时间的 Highest Response Ratio Next | 避免大 KV 请求饥饿 |
| Previous-answer-based Eviction | 用上一轮 LLM 回答长度预测用户下次访问时间→指导淘汰 | 核心创新：计算→存储的感知 |
| Ghost Cache | 用 Belady 最优算法对过去 trace 模拟命中率→建立加权重用距离与命中潜力的映射 | Hit Potential 预测基础 |
| Hit Potential | 在最优策略下某一 KV 访问能命中的概率 | 淘汰决策的直接依据 |
| Storage-efficient Tensor | 非 KV 的中间张量（如 normalized activation），cost efficiency 更高 | 用更少存储空间节省更多计算 |
| Cost Efficiency | Saved Computing Amount / Required Space (GFLOPs/MB) | 选择缓存哪个张量的核心指标 |
| Mix-grained GPU Memory | Big blocks (256 tokens) + Small blocks (16 tokens) | 提高 CPU-GPU 传输带宽利用率 |

---

## 背景与动机

### 交互式 LLM Serving 的 KV cache 挑战

- 多轮对话平均 **22.4 轮**，历史 KV 重算占 **93.1%** 的总计算量
- KV cache 缓存在 host memory + SSD 两层存储系统中
- Host memory 有限（1.6-3.2× GPU 内存），并发用户多时 KV 总数可达 memory 的 **3.91×**

### 现有方案的严重不足

| 方案 | 问题 |
|------|------|
| CachedAttention, FlashGen | Compute 和 Storage **双向互盲**→ KV 加载成为系统瓶颈 |
| FlashGen (re-compute) | 大模型上重算开销高，延迟反而更高 |

**性能差距**：vs 全内存 KVs 上界——延迟 **3.8×** 更高，吞吐 **2.0×** 更低。

### 三个 KV 访问特征（百万轮真实 workload 分析）

1. **KV 驻留时间长**：每用户对话跨度长→并发缓存 KV 总量可达 performance layer 的 3.91× → 需要精心淘汰
2. **时间局部性差**：**80%** KV 访问的加权重用距离 > 200GB（performance layer 总容量）→ traditional LRU/FIFO 命中率仅 ~20%
3. **KV 加载时间变异极大**：请求间的变异系数 >90%（KV 大小差异 + 存储层带宽差距）→ 即使 5s 窗口内到达的请求也有巨大差异

### 根因：Compute-Storage 双向互盲

- **Compute → Storage**：调度请求时不考虑 KV 加载延迟 → 大 KV 慢 I/O 阻塞小 KV 快请求
- **Storage → Compute**：淘汰 KVs 时不利用计算端的用户对话模式 → 仅靠过去访问信息→命中率极低

---

## 方案设计

### 1. I/O-aware Request Scheduling（计算→存储感知）

**双队列分离**：
- Ready Queue：KV 已在 host memory → 可直接调度 GPU 推理 (FCFS)
- Preparing Queue：KV 在 SSD → 先加载到 host memory → 提升到 Ready Queue
- 提升时按 **原始到达时间** 而非提升时间插入 Ready Queue→避免尾延迟恶化

**disk-HRRN (Preparing Queue 调度)**：
```
Response Ratio = 1 + Request waiting time / KV size
```
- 小 KV 请求天然高优先级→快速提升
- 大 KV 请求等待时间增长→优先级逐步提升→防止饥饿

**效果**：慢 SSD I/O 不再阻塞快 host memory I/O 的请求→平均排队时间 -57.5%。

### 2. Previous-answer-based Eviction（存储→计算感知）

**核心观察**：LLM 回答越长 → 用户阅读/理解/构思下一问题耗时越长 → 该用户下一次 KV 访问的延迟越大 → 加权重用距离越大。

**量化验证**：12 组不同时段的 trace → Spearman 相关系数 0.94-0.98（weighted reuse distance lower bound vs previous answer length）。

**三步淘汰决策**：

1. **Ghost Cache 估计命中率**：后台用 Belady 最优算法模拟→将加权重用距离分为 small/promising buckets/extreme→每 bucket 估命中率
2. **用户概率分布**：追踪每个用户历史 weighted reuse distance 分布 → 估计下次访问落在各 bucket 的概率
3. **Hit Potential = 各 bucket 概率 × 命中率的加权和**→ 最低 Hit Potential 的 KV 被淘汰

**效果**：miss rate -57.6% vs queue-enhanced，-69.9% vs LRU/FIFO/LFU。

### 3. Storage-efficient Tensor Caching

**关键观察**：不同中间张量有截然不同的 size vs saved compute trade-off。

| Tensor | Size (MB) | Saved GFLOPs | Cost Efficiency |
|--------|-----------|-------------|-----------------|
| KV Tensor | ~40 | ~1200 | 30.5 |
| **Tensor 6 (normalized activation)** | ~20 | ~1020 | **51.0** (最高) |

**方案**：缓存 storage-efficient tensor（如 normalized activation）替代 KV tensor→GPU 空闲 SMs 在低优先级 CUDA stream 上做转换（仅几十 ms，对数百-数千 ms 的推理延迟无影响）。

**适用性**：MHA-based LLMs (Llama, Qwen, OPT, Bloom 等)→GQA-based LLMs 中 KV 已较小，直接缓存 KV 更优。

---

## 评估数据

### 端到端性能

| 指标 | 结果 |
|------|------|
| 延迟 (vs SOTA) | **-3.58×** (最高), -83.9% (平均) |
| 吞吐 (vs SOTA) | **+1.43-1.83×** |
| vs 全内存 KVs 上界 | 逼近 |
| P90/P95/P99 尾延迟 | -47%~67% |

### 消融

| 技术 | 效果 |
|------|------|
| I/O-aware Scheduling | avg latency -1.58× |
| + Previous-answer Eviction | throughput +1.25× |
| + Storage-efficient Tensor | throughput +1.10× |

### 系统开销

| 操作 | 延迟 |
|------|------|
| 调度决策 | 0.62ms avg (GPU iteration ~10s ms→可忽略) |
| 淘汰决策 | 0.35ms |
| Tensor 转换 | ~10s ms (低优先级 CUDA stream→不影响推理) |

---

## 整体评估

### 真正的新意

1. **"加权重用距离与 LLM 回答长度的强正相关"**——这是全新的经验发现。此前无人将计算端的输出（回答长度）用于预测存储端的访问模式。Spearman 0.94-0.98 的相关性不是巧合——它源于交互式对话中人因（human-in-the-loop）的本质：长回答→长阅读时间→长访问间隔。

2. **"双向感知 = 两个方向的信息流动"**：Compute→Storage 是传统的（I/O 感知调度），Storage→Compute 才是反直觉的（用模型回答预测 KV 访问时间）。后者的 insight 在于——LLM 的输出本身包含了"用户什么时候会回来"的信息。

3. **"Hit Potential = ghost cache + user access distribution + answer-length lower bound"**：三信息源的融合——最优策略的模拟（ghost cache）、用户历史行为（access distribution）、实时信号（answer length）。不是学习→是统计估计+约束剪枝。

### 优点

- 百万轮真实 workload 的 KV 访问特征分析是扎实的 motivation
- 回答长度→重用距离的相关性发现既有直觉（长回答=长思考时间）又有量化（Spearman 0.94+）
- 存储高效张量缓存是一个实用且可泛化的优化（MHA 模型通用）
- 尾延迟的显著改善（-47%~67%）对交互式场景至关重要

### 局限

- Previous-answer-based eviction 依赖于真实时间戳→Poisson 模拟时间戳的 workload 上不生效（ShareGPT 实验结果证明了这一点）
- Ghost cache 的 Belady 模拟需要一定历史数据→冷启动阶段效果未知
- 存储高效张量缓存仅适用 MHA→GQA 需要回退到缓存 KV
- 仅测试单 GPU 场景→多 GPU tensor parallelism/pipeline parallelism 的调度复杂度未讨论

### 适用条件

- 交互式多轮对话 LLM serving（非 batch 离线推理）
- 真实用户行为（human-in-the-loop，有阅读/思考间隔）
- Host memory 容量不足以缓存所有用户的 KV
- MHA-based 模型（可利用 storage-efficient tensor）

### 可复用启发

1. **"LLM 的输出本身编码了未来的 I/O 模式"**：回答长度→用户下次请求时间。这不限于 KV cache——任何需要预测用户行为的 ML serving 系统都可以利用模型输出的统计特征（长度、复杂度、情感极性等）来优化资源管理。

2. **"Hit Potential = 最优策略模拟 + 用户分布 + 实时信号的三源融合"**：Ghost cache 提供"如果能看未来会怎样"的上界→用户分布提供个性化预测→实时信号提供约束。这是预测性缓存的通用框架。

3. **"缓存不应卡在 KV tensor——寻找 cost efficiency 更高的中间张量"**：不同中间张量有不同的 size/compute 比例→选择 cost efficiency 最高的。适用场景：任何"用存储换计算"的缓存系统→不仅 LLM inference，也可以是数据库物化视图选择、编译缓存等。

4. **"双队列分离——I/O 感知调度的最小可行方案"**：Ready Queue / Preparing Queue 的概念简单但有效——本质是按 I/O 延迟将请求分为"即刻可用"和"等待中"两类。适用场景：任何有多层存储+请求级 I/O 延迟变异的系统。

5. **"disk-HRRN = 等待时间/KV 大小的混合优先级"**：同时考虑 fairness（等待时间）和 efficiency（小 I/O 优先）。这是一个平衡 starvation 和 throughput 的轻量方案。

### 讨论问题

- 如果多个模型并行 serving（不同 size 的 LLM），回答长度→重用距离的映射是否需要 per-model 校准？
- Ghost cache 在 workload shift（如从工作日到周末用户行为变化）时是否需要重新校准？
- Bidaw 的 previous-answer-based eviction 是否可以与 CacheSlide 的 RPDC 范式结合——既利用跨请求的 KV 复用，又利用跨用户的回答长度预测？
