# CacheSlide(FAST'26)

- **来源**: https://www.usenix.org/system/files/fast26-liu-yang.pdf, FAST '26
- **作者**: Yang Liu, Yunfei Gu, Chentao Wu, Guangtao Xue, Jie Li, Minyi Guo (SJTU), Liqiang Zhang (Inspur), Junhao Hu (PKU), Jie Meng (Huawei Cloud)
- **一句话 TL;DR**: 面向 Agent 场景的第三种 KV cache 复用范式 RPDC——利用固定段保持相对顺序的性质，通过 CoPE 降低位置漂移 + 权重校正注意力（top-k 选择+加权融合）+ SLIDE（负荷-写入解耦+脏页感知淘汰），3.11-4.3× 延迟缩减，3.5-5.8× 吞吐提升。
- **资料类型**: 论文-系统（AI 推理优化）

---

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| PDC | Position-Dependent Caching，仅在固定绝对位置复用 KV cache（如 prefix） | 最严格、最安全但复用率最低 |
| PIC | Position-Independent Caching，忽略位置复用 KV，需重算部分 token 恢复精度 | 复用率高但精度不稳+I/O 开销大 |
| RPDC | Relative-Position-Dependent Caching，固定段保持相对顺序不变 | 本文提出的第三种范式 |
| PMKD | Positionally Misaligned KV Drift，位置编码漂移导致的 KV cache 相似度下降 | 需要最小化的目标 |
| CKSim | Cosine similarity between KV caches，衡量重用 KV 与重算 KV 的相似度 | 核心度量（量化 PMKD） |
| CCPE | Chunked Contextual Position Encoding，基于 CoPE 的分块上下文位置编码 | 降低固定段的位置漂移（∆pos 小） |
| RoPE | Rotary Position Embedding，每 token 唯一位置→位置敏感度高 | PMKD 严重的原因 |
| CoPE | Contextual Position Encoding，语义边界粒度→多 token 共享位置 | CCPE 的基础，位置敏感度低 |
| WCA | Weighted Correction Attention，选 top-k token 重算 KV + 加权融合回收 | 恢复固定段-更新段跨注意力 |
| SLIDE | Spill-aware & Load–write decoupling Intra-layer & Dirty-page Eviction | 系统层优化：解耦+脏页感知 |
| Relocate | 将重算的 selected tokens KVs 写入新分配页→不等 KV 加载完成 | 消除 intra-layer load-before-write lock |
| Dirty-page Eviction | 淘汰时优先 clean pages，脏页按 selected-token 数量降序淘汰→合并写 | 降 SSD 随机写+WAF |

---

## 背景与动机

### Agent 场景的 KV cache 复用挑战

LLM Agent（CoT 推理、Memory 管理、Function Calling）的输入 prompt 结构为：

```
System Prompt (static) + Updated Prompt (per-turn) + Fixed Prompt (historical, static)
```

- **Fixed segments** 在多轮推理中保持不变但**绝对位置**因 Updated Prompt 长度变化而漂移
- 大规模复用段占比高达输入长度的 60-90%（视 Agent 类型而定）

### 现有两种范式的缺陷

| 范式 | 代表系统 | 优点 | 在 Agent 场景的致命缺陷 |
|------|---------|------|----------------------|
| **PDC** (位置相关) | ContextCache, PromptCache | KV cache 精确匹配 | 仅能用 prefix，固定段在 suffix 位置无法复用；PromptCache 多位置存储内存爆炸 |
| **PIC** (位置无关) | CacheBlend, EPIC | 任意位置复用 | 重置位置索引=0 → PMKD → 需重算大量 token → 精度不稳 + I/O 瓶颈 |

### PMKD 的量化发现

- RoPE 下位置偏移 1000 tokens → CKSim 下降 **>90%**
- CoPE 下同等偏移 → CKSim 下降仅 **28%**
- 窗口 padding（固定更新段长度）导致 F1 比 baseline 低 **>78%**——不可行

**核心洞察**：Agent prompt 中固定段的**相对顺序**保持不变→这是一个可被利用的规律→定义为 RPDC。

---

## 方案设计

### 1. CCPE (Chunked Contextual Position Encoding)

**原理**：用 CoPE 替代 RoPE（低位置敏感度→位置漂移时 CKSim 下降小），并通过 task-specific pretraining 学习固定 chunk 的最频编码模式→推理时赋给复用段。

**效果**：复用段的 cached position ≈ real position（∆pos 可忽略）→ intra-segment attention + cross-fixed-segment attention 可以近无损复用。仅需恢复 fixed↔updated 跨注意力。

### 2. Weighted Correction Attention

**三步恢复跨注意力**：

1. **Layer 1 全量重算**：计算每个 token i 的偏差 `di = ∥Ki_recompute − Ki_reuse∥₂` → 选 top-k (默认 26%)
2. **Layer 2→L 加权融合**：仅对 Sk 中 token 重算 KV → 与缓存 KV 以 αi（偏差归一化权重）融合
3. **每四层 CKSim 门控**：检查 CKSim < 阈值 τ (0.12) → 移除该 token，从候选集 S 中补充偏差最大的 token

**关键观察**：相邻层的 KV 相似且深层更相似→层 1 选出需要重算的 token 子集后，后续层只需重算这些 token→深层偏差自然缩小。

### 3. SLIDE (KV Cache Manager)

**3a. Load–Write Decoupling (LWD)**：
- 传统：KV cache load 和 write 在每层串行→intra-layer load-before-write lock
- SLIDE：load 开始时同步发起 recompute→recompute 完成时不等 load→写入新分配的额外页→后续 decode 优先覆写这些 slot

**3b. Dirty-page Eviction**：
- 从 layer 2 起标记含 selected token 的页为 dirty，其余 clean
- 淘汰策略：clean pages 优先（避免碎片化写回）→脏页按 selected-token 数降序（更多 selected token = 更大合并写机会）
- 目的：将随机小写合并为顺序写→降 SSD WAF

---

## 评估数据

### TTFT 缩减

| 对比 | CacheSlide vs |
|------|--------------|
| ContextCache | **2.4-3.3×** TTFT 缩减 |
| CacheBlend | **1.21-2.11×** TTFT 缩减 + **1.97-2.28×** 精度提升 |
| PromptCache | **1.12-2.45×** TTFT 缩减 + **1.41-3.95×** 精度提升 |

### 并行/Beam Search 扩展

- batch=6 parallel: **2.3×** TTFT 优于 best baseline
- beam width=6: **2.1×** TTFT 优于 best baseline
- 随并发度增加，CacheSlide 优势扩大（SLIDE 的 spill 优化生效）

### SLIDE Ablation

| 消融项 | 效果 |
|--------|------|
| LWD (Load–Write Decoupling) | layer-wise 并行延迟 **-26.7–51.5%** |
| Dirty-page Eviction | 写阻塞 **-66.9–73.5%** |
| SSD WAF | **-3.11–3.62×** |
| GPU 存储 vs PromptCache | **-1.63–1.9×** |

### 吞吐

vs CacheBlend/EPIC（batch=8, Reflexion/HotpotQA）：+49.6%～82.2% 吞吐，吞吐标准差 -58.6%～77.4%。

### Top-k & CKSim 最优值

QPS 峰值：**top-k ≈ 0.26, CKSim ≈ 0.12**（跨模型和数据集一致）。

---

## 整体评估

### 真正的新意

1. **"RPDC = PDC 和 PIC 之间的第三种范式"**：不是"更 flexible 的 PDC"也不是"更 accurate 的 PIC"——而是利用 Agent 场景中固定段保持相对顺序这一被忽视的结构性质，创造出一种新的缓存范式。这是问题定义层面的贡献。

2. **"CoPE 降位置敏感度→让位置漂移从 '需要纠正的错误' 变成 '可忽略的偏差'"**：不是想办法纠正 PMKD，而是通过更换编码从根本上降低 PMKD 的幅度。这比修复漂移更根本——改变了"漂移有多严重"这个前提。

3. **"Layer 1 全量重算→选出 top-k→后续层仅重算这些 token"**：利用跨层 KV 相似性——关键观察是"layer 1 偏差最大，后续层相似度递增"。一种 lightweight profiling 方法：用最便宜的层定位问题，后续继承。

4. **"SLIDE 的 dirty-page 感知淘汰——将碎片化写入转化为合并顺序写"**：clean pages 优先淘汰→脏页按 selected-token 数排序淘汰→最大化合并写。这是"用语义信息（哪些 token 被选中重算）指导存储层决策（哪些页优先淘汰）"的跨层优化。

### 优点

- 在问题定义层面区分了 RPDC 与前两种范式——不仅是增量改进，而是范式定义
- PMKD 的量化分析（RoPE vs CoPE, CKSim vs 偏移量）为后续工作提供了基准数据
- 三层设计（CCPE→WCA→SLIDE）的因果链清晰：编码降漂移→选择性重算恢复注意力→系统层解耦+脏页感知
- 跨多种 Agent 类型（CoT/Memory/Tool）和模型规模的评估

### 局限

- CoPE 需要 adapter 训练（LoRA 微调 attention 权重）→对不能微调的场景（如 API-only 模型）不适用
- CCPE 的 pretraining 依赖 task-specific prompts→相同任务类型才能复用学习到的编码模式
- 固定的 top-k=0.26 和 CKSim=0.12 可能对特定任务/模型非最优（虽然实验表明跨模型稳定）
- SLIDE 的 dirty-page 计数依赖 Weighted Correction Attention 的 select 结果→如果 attention sparsity 模式变化，dirty-page 排序可能失准

### 适用条件

- Agent-based LLM serving（多轮推理、memory 管理、function calling）
- Prompt 结构包含固定段 + 可变更新段，且固定段相对顺序不变
- 模型支持 CoPE（或可接受 LoRA adapter 微调）

### 可复用启发

1. **"通过更换位置编码降低 PMKD——不是 fix the drift，是 reduce its magnitude"**：RoPE 的每 token 唯一位置是 PMKD 的根本原因→CoPE 的语义边界粒度天然抗漂移。适用场景：任何需要"相同内容在不同位置复用"的场景（跨文档检索、RAG、多轮对话）

2. **"Layer 1 作为 lightweight profiler——用最便宜的方式定位问题，后续层继承"**：不在每层都全量重算→仅 layer 1 全量→选出 top-k→后续层仅重算这些。适用场景：任何需要在多层（transformer layers/网络层次/存储层次）中定位瓶颈或异常的系统

3. **"Dirty-page 感知淘汰——语义信息指导存储决策"**：哪些页包含 selected tokens（更可能被再次修改）→优先淘汰 clean pages + 脏页按修改密度排序→最大化合并写。跨层信息（计算层"哪些 token 被重算"）指导存储层（"哪些页优先淘汰"）的案例

4. **"三种缓存范式（PDC/PIC/RPDC）的分类框架"**：不仅是 CacheSlide 的贡献——这是一个理解和选择 KV cache 复用策略的通用框架。选择哪个范式取决于 prompt 中固定段的性质：绝对位置不变→PDC；可任意重排→PIC；相对顺序不变但绝对位置漂移→RPDC

### 讨论问题

- 多 Agent 协作场景（不同 Agent 有不同 prompt 模板）下 CCPE 的 task-specific pretraining 能泛化吗？
- Dynamic update segment 的长度波动极大（如 function call 返回结果差异大）→∆pos 的最大漂移范围是否能保持 CKSim 在安全范围内？
- CacheSlide 与 PromptCache 是否可以组合——用 CCPE 处理固定段位置漂移 + PromptCache 的多位置缓存处理 prefix sharing——形成更全面的缓存策略？
