# PPC+MAIO(FAST'26)

- **来源**: https://www.usenix.org/system/files/fast26-liu-yubo.pdf, FAST '26
- **作者**: Yubo Liu, Hongbo Li, Xiaojia Huang, Yongfeng Wang, Hanjun Guo, Hui Chen, Yuxin Ren, Ning Jia (Huawei)
- **一句话 TL;DR**: 华为可编程页缓存框架 PPC + 模型加载加速策略 MAIO——通过内核可堆叠路由文件系统(RFS)+用户态缓存策略运行时(CPRT)实现无侵入/灵活/轻量的内核页缓存可编程，MAIO 基于 I/O 模板（同服务同 I/O pattern）实现可中断预取+XPU 亲和+BAR 淘汰，模型加载延迟降 79%，推理启动吞吐升 36%。
- **资料类型**: 论文-系统（内核+AI 推理优化+工业部署）

---

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| PPC | Programmable Page Cache，可编程页缓存框架 | 本文的核心基础设施贡献 |
| RFS | Routing File System，内核可堆叠只读 FS，劫持底层 FS 的 cache miss | PPC 的内核部分 |
| CPRT | Cache Policy Runtime，用户态缓存策略运行时 | PPC 的用户态部分 |
| UPC | Userspace Procedure Call，per-core 非阻塞事件队列 (xarray) | RFS↔CPRT 的通信机制 |
| MAIO | Model-Accelerated I/O，基于 PPC 的模型加载加速策略 | 本文的案例/应用 |
| I/O Template | 每个推理服务的 I/O 序列模板（文件路径+偏移+大小，按 XPU worker 分组） | MAIO 的核心数据结构 |
| XPU Affinity | 数据加载到目标 XPU 所在 NUMA node | 加速 host→device 传输 |
| BAR Eviction | Burn-after-Reading，基于 I/O 模板中当前位置淘汰之前数据 | 精确感知数据生命周期 |
| Interruptible Prefetching | 新 ppc_prefetch() 调用到达时，PPC loader 中断旧预取执行新预取 | 避免冗余加载+自适应预取进度 |
| Service ID | 推理服务参数（模型名+TP+PD）的 hash | 关联 MaaS 模板与 I/O 模板 |
| Intelligence BooM | 华为企业级 LLM 推理解决方案（Ascend NPU + Kunpeng CPU + vLLM-Ascend） | 工业部署平台 |

---

## 背景与动机

### 模型加载是推理启动的主要瓶颈

- MaaS 场景中，模型加载占推理服务启动开销的 **>70%**（DeepSeek-R1-671B 启动 ~1h，加载 ~70%+）
- SSD 带宽平均仅利用 **17%**（图 1：峰值 5.93 GB/s，平均 1.05 GB/s）
- 现有优化（ServerlessLLM, BlitzScale）以**牺牲兼容性**换取性能→强依赖特定软硬件

### 兼容性的三个维度

1. **推理框架透明**：不能修改推理框架代码（对基础设施厂商是黑盒）
2. **内核无侵入**：生产环境数百上千节点升级内核需数年，只能加载独立内核模块
3. **无硬件依赖**：不依赖 NVLink/HCCS 等特定加速器特性

### 内核页缓存的三个不足（核心瓶颈）

| 观察 | 根因 | 影响 |
|------|------|------|
| 预取不能充分利用 SSD 并发 | kworker 数量限制 + 仅预取同一文件连续段 | 平均带宽仅 1.05 GB/s |
| 忽略 XPU 亲和性 | kworker 所在 NUMA node ≠ 目标 XPU 所在 node | host→device 传输效率损失 ~20% |
| 淘汰无法感知数据生命周期 | 采样+LRU，无法知道数据何时加载到 XPU | 冷数据不淘汰→内存受限时劣化 38%+ |

### 现有页缓存可编程方案的局限

| 方案 | 非侵入 | 灵活 | 轻量 |
|------|--------|------|------|
| FUSE-based (RFUSE) | ✓ | ✓ | ✗ (栈重) |
| eBPF-based (FetchBPF) | ✗ (需 kfunc) | ✗ (不支持复杂策略) | ✓ |
| fadvise | ✓ | ✗ (无法深度协作) | ✓ |
| **PPC** | **✓** | **✓** | **✓** |

---

## 方案设计

### PPC: Programmable Page Cache 框架

**架构**：RFS（内核可堆叠只读 FS）+ CPRT（用户态策略运行时）+ UPC（通信）

**RFS 关键实现**：
- 利用 Linux stacked filesystem 机制（类似 OverlayFS）劫持底层 FS 的 read/page fault 操作
- 记录 VFS 数据结构（superblock/inode/file/dentry）到原始结构的映射
- 当 cache miss 时：封装 I/O miss 信息→UPC 事件→用户态策略决策→执行预取/淘汰→再调用底层 FS 读数据
- 当 cache hit 时：直接返回数据（快速路径）
- **不修改**内核原生预取/淘汰机制，仅通过系统配置禁用它们

**UPC (Userspace Procedure Call)**：
- Per-core xarray 事件队列（无锁高并发）
- 非阻塞发送（仅入队开销）
- 用户态通过 poll/epoll 监听

**CPRT (Cache Policy Runtime)**：
- VFS 风格编程框架：用户实现 `ppc_init/exit/prefetch/evict` 四个函数→编译为 .so→`reg_policy` 注册
- 策略 Executor：线程池监听 UPC→聚合 I/O miss→调用用户函数
- Cache Manager：执行预取（core-bound 线程池+ioctl）+ 淘汰（fadvise DONTNEED）+ **可中断**+**XPU 亲和感知**

**PPC 性能开销**：
- 读吞吐：+3.7% (EXT4) / +6.4% (XFS) — vs RFUSE 的 +14-15%
- 内存：~30MB（RFS metadata + UPC events，不随并发度 scaling）
- CPU：UPC 事件监听 1-11%（随并发度变化）

### MAIO: Model-Accelerated I/O 策略

**核心洞察**：相同推理服务（相同模型+相同 TP/PD 配置）的模型加载 I/O pattern 是**可复现的**→可以预先追踪并缓存为 I/O 模板。

**I/O 模板**：
- 按 XPU Worker ID 分组（每个 XPU 一个 worker 进程）
- 每组包含有序 I/O 元组：⟨文件路径, 偏移, 大小⟩
- 存储开销极小：DeepSeek-R1-671B (662GB) → I/O 模板仅 **545KB**
- 模板与 MaaS 模板通过 Service ID 关联→共享生命周期

**三个核心机制**：

1. **Interruptible Prefetching**：从 miss 位置预取到 I/O group 末尾→新 miss 到达时 PPC loader 中断旧预取执行新预取→自适应+避免冗余
2. **XPU Affinity Loading**：根据 I/O 模板中的 Worker ID→XPU 映射→目标 NUMA node→PPC loader 将数据加载到对应 NUMA node
3. **BAR (Burn-after-Reading) Eviction**：维护 eviction cursor→`ppc_evict()` 淘汰 miss position 与 cursor 之间的数据（保持 1GB 安全距离）→精确感知数据生命周期

**与现有策略的对比**：
- vs 预测型（LRU/LFU）：MAIO 精确感知 I/O 时间+XPU 亲和+数据生命周期
- vs 经验型（EagerLoad 盲预取）：MAIO 不产生 cache thrashing + XPU 亲和
- vs 框架嵌入型（ServerlessLLM）：MAIO 兼容性强 + 可覆盖框架初始化阶段的空闲带宽 + 有淘汰策略

---

## 评估数据

### 模型加载延迟

| 场景 | MAIO vs Native | vs EagerLoad | vs PreCache | vs SLLM-NPU |
|------|---------------|-------------|-------------|-------------|
| 内存充足 | **-79%** | -32% | -37% | -17% |
| 64GB 受限 | **-74%** | 大幅领先 | 大幅领先 | N/A |

### 推理启动延迟

| 场景 | MAIO vs Native |
|------|---------------|
| 内存充足 | **-38%** |
| 内存受限 | **-51%** |

### 工业部署（DeepSeek-R1-671B, 2 nodes/16 NPUs）

- Model loading: 649s → **452s**（-30%）
- 甚至快于全 DRAM 预缓存（561s）——因为 XPU 亲和加速了 host→NPU 传输 + I/O 被完全隐藏在 metadata 解析后

### MaaS 弹性推理吞吐

| 场景 | MAIO vs Native | vs PreCache/EagerLoad |
|------|---------------|----------------------|
| 内存充足 | +13% | 无显著优势（模型加载占比低） |
| 内存受限 | **+28%** | +19-21% |

---

## 整体评估

### 真正的新意

1. **"可堆叠 FS + 用户态策略 = 页缓存可编程的第四范式"**：PPC 填补了 FUSE（太重）、eBPF（太受限）、fadvise（太弱）之间的空白——同时满足非侵入（独立内核模块）、灵活（任意策略.so）、轻量（~3-6% 开销）。这个框架的价值可能超过 MAIO 本身。

2. **"推理服务模板 → I/O 模板的映射"**：MaaS 平台已有的模板（模型+并行参数）包含足够信息来预测 I/O pattern→只需一次跟踪即可为同类型服务永久使用。这是"利用已有运维元数据预测 I/O"的案例——不需要 ML 预测、不需要在线学习。

3. **"可中断预取 = 自适应进度跟踪"**：prefetch 从 miss 位置到末尾→新 miss 到来时中断→跳转到新位置→避免"预取跑得比前端慢还继续加载旧数据"的低效。简单的"last-writer-wins"语义。

### 优点

- 工业部署验证（Huawei Intelligence BooM, Ascend NPU, vLLM-Ascend, DeepSeek-R1-671B）
- 兼容性作为一等设计目标（内核模块化+框架透明+硬件无关）
- PPC 框架+MAIO 策略两层清晰的分离——框架可复用于其他场景的缓存优化
- I/O 模板的存储开销论证（545KB for 662GB model）→无实际障碍

### 局限

- RFS 当前仅支持只读场景（模型加载是只读的，但框架的通用性受限）
- MAIO 的实现依赖 MaaS 平台的模板机制→非 MaaS 场景需要额外适配
- BAR eviction 的 1GB 安全距离是经验值，不同场景可能需调优
- 多 MAIO 实例共存时的资源争用（I/O/CPU）当前仅通过 cgroup 粗糙控制
- PPC 不支持写入→无法用于 checkpoint 保存等场景

### 适用条件

- LLM 推理服务的模型加载（只读、大文件、多 XPU）
- 同一推理服务被多次启动（弹性扩缩、多租户）→I/O 模板摊销成本
- 有 MaaS 平台或类似模板机制的部署环境

### 可复用启发

1. **"I/O 模板 = 利用部署元数据预测 I/O，取代在线学习"**：不需要 ML、不需要采样、不需要统计——同一服务的 I/O pattern 是确定的→只需跟踪一次。"如果你的系统已经有 service template（如 K8s deployment spec），它可能已经包含预测 I/O 的全部信息"。

2. **"可堆叠 FS = 劫持 cache miss 的最小侵入路径"**：不需要修改 VFS、不需要修改底层 FS——只需要 stacked FS 劫持 cache miss→用户态决策→返回预取列表。这是"内核机制 + 用户态策略"分离设计的教科书案例。

3. **"可中断预取 = last-writer-wins 的简单自适应"**：不需要预测前端 I/O 进度——新 miss = 前端已经超过了预取位置→中断旧预取跳到新位置。最朴素的反馈机制往往最有效。

4. **"BAR 淘汰 = 利用只读场景的'数据用后即弃'特性"**：模型数据加载到 XPU 后 host 副本无用→miss position 之前的数据都可以淘汰。只读+一次性消费的场景使淘汰逻辑极其简单——不需要热度追踪、不需要 LRU。

### 讨论问题

- PPC 的 RFS 能否扩展到支持写入（如 checkpoint 保存到本地 SSD 的场景）——这会引入脏页管理和 crash consistency 问题
- 如果模型更新（fine-tuned checkpoint），I/O 模板是否需要重新生成——MAIO 如何检测 I/O pattern 变化
- 在多节点推理（TP=16 across 2 nodes）中，I/O 模板的跨节点共享（NFS）是否会成为瓶颈
