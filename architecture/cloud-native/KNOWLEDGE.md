# Cloud-Native Architecture

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 解耦式 GC 服务 | disaggregated GC, RDMA paging, multi-tenant orchestration, peak shaving, concurrent marking | DGC(OSDI'26) |
| 联邦 LLM Serving 平台 | CRDT gossip, sovereign AI, heterogeneous GPU federation, service discovery overlay, HPC-to-serving bridge | OpenTela(OSDI'26) |
| Continuation-Centric OS | continuation capture, effect system, serverless primitives, zero-copy snapshot, functional I/O | Arca(OSDI'26) |
| Serverless 冷启动快照 | SHELF format, spliceVMA, snapshot restore, cold start, physical-logical decoupling, bulk metadata restore | Spice(OSDI'26) |
| 分布式推测执行容错 | durable execution, distributed speculative execution, speculation sandbox, reactive repair, message-passing, persistence elision | libDSE(OSDI'26) |
| 本地-云盘混合存储架构 | local-cloud hybrid, ML I/O dispatch, write-back cache, auto-scale IOPS, append-only ordering, tiered pricing | Latte(FAST'26) |

---

## 解耦式垃圾回收服务 (DGC)

### 核心问题
并发 GC 的标记线程在多租户 CPU 受限环境中与 mutator 直接竞争 CPU → 应用可用 CPU 降至 60% → 平均延迟上升超过一个数量级。这是周期性资源消耗（标记 burst）+ 固定 CPU 限制的必然冲突。

### 关键洞察

1. **"Shaving the peaks"**：将周期性标记负载从原始运行时解耦为独立服务 → 消除与 mutator 的 CPU 竞争
2. **RDMA-based software paging** 消除远程执行的性能代价：按需页交换 → 远程标记引擎"接近本地性能"
3. **Global orchestrator 错峰调度**：多个运行时独立触发 GC → 错峰避免 burst 叠加 → 平滑总体负载
4. **资源池化**：独立的标记资源池被多运行时时间复用——提高整体资源利用率
- 来源：DGC(OSDI'26)

### 实践启发
- "Shaving the peaks" 策略适用于任何周期性资源消耗任务（日志刷新、索引构建、压缩、备份）
- 将"周期性任务"转变为"外部服务 + 错峰调度"是处理多租户环境中峰值问题的通用范式
- RDMA 不仅是数据传输工具——也是实现"远程执行但本地性能"的系统架构基础

---

## 联邦 LLM Serving 平台 (OpenTela)

### 核心问题
主权 AI 投资巨大（Alps 10K GH200、ABCI 3.0 6K H200、EU AI Factories C20B），但基础设施是 HPC 集群——设计用于批处理（Slurm、transient 分配、无持久端点）。LLM serving 需要负载均衡、服务发现、弹性伸缩——这些在 HPC 环境中不存在。替换 Slurm 为 Kubernetes 不可行（HPC 依赖 MPI/拓扑感知）。GPU 资源分散在异构集群和管理域之间。

### 关键洞察

1. **"Overlay 不替代现有集群管理器"**：用户态编排层在 Slurm/Kubernetes 之上→不需要 root 权限、不需要集群重配置。不替代现有系统，而是构建统一抽象层整合碎片资源。类似 vBOIDs "不改应用/编排框架"的策略。
2. **"CRDT-based gossip 做容错服务发现"**：HPC 环境无 centralized control plane→需要去中心化的服务发现。CRDT 处理网络分区和 transient allocations。
3. **"Unified API over heterogeneous stacks"**：vLLM/SGLang + Slurm/K8s 的统一接口→研究者只需提交 inference 需求，不需要知道 GPU 在哪个集群、由哪个调度器管理。

- 来源：OpenTela(OSDI'26)

### 实践启发
- **"Overlay 而不是替换"是异构基础设施整合的核心智慧**：改变底层调度器几乎不可能→在之上构建统一抽象。类似 InfiniDefrag "GPA 已经是虚拟层→不需要 compaction，只需 remap"——利用已有抽象层而非推倒重来
- **"Decentralized service discovery"适合去中心化资源池**：CRDT gossip 消除单点故障，特别适合跨管理域、非持久分配的 HPC 环境
- **"生产 trace 开源"**：22 个月、13M 请求、142 模型的 trace→宝贵的公开研究数据

---

## Continuation-Centric OS (Arca)

### 核心问题
Serverless 需要开发者**提前**拆分程序为细粒度函数——但最佳的拆分点很难预先知道。现有进程/VM 快照（CRIU/Firecracker）需数百 ms——根本无法在每个 I/O 操作后做快照。**缺少一个使 "捕获当前进程的剩余部分作为可恢复的函数" 变得廉价（µs 级）的 OS 原语。**

### 关键洞察

1. **"Continuation capture 作为 OS 核心原语而非库函数——五个数量级差距"**：Linux process snapshot 需 283ms，Arca 只需 **2.55µs**。差距来自 OS 是否为 continuation 而设计——不是优化现有 snapshot 机制，而是重新设计整个进程模型使 continuation capture 成为 zero-copy 操作。
2. **"Effect system 替代 syscall——functional paradigm 在 OS 层的实现"**：Arca 进程不直接做 I/O→返回 effect（I/O 描述 + 回调 continuation）。框架处理 I/O→resume continuation。这实现了 pure functional paradigm 在操作系统层面——每个函数调用是纯的，I/O 在外部处理。
3. **"Serverless 的真正原语不是 function——是 continuation"**：Function 要求开发者预定义拆分点。Continuation 使 OS 可以在运行时自动捕获 "从这里开始的剩余计算"——不需要开发者提前知道 split point。

- 来源：Arca(OSDI'26)

### 实践启发
- **"OS 为特定计算范式重新设计——而非在现有 OS 上叠加"**：Arca 的性能（µs vs ms）不是因为更好的 snapshot 算法，而是因为重新设计了整个 OS 的进程模型。这是真正的范式转变而非增量优化
- **"Effect system = I/O 的外部化"**：将 I/O 从进程中剥离→进程变为纯计算→可以随时被暂停/迁移/复制→适合极度弹性的 serverless
- **"Continuation 比 function 更适合 serverless"**：不是预定义函数，而是运行时确定"从哪里 pause"——这给了调度器最大的灵活性

---

## Serverless 冷启动快照 (Spice)

### 核心问题
Serverless 冷启动延迟是弹性的根本限制——81% 应用每分钟最多调用一次，60% 函数冷启动多于热启动。最有效方案是快照恢复（函数初始化后 snapshot→下次从磁盘恢复），但**现有 OS 缺乏快照恢复支持**：mmap/madvise 为增量进程启动设计→强制在高效磁盘布局和廉价虚拟地址重建之间 trade-off；内核缺少 bulk-restore→用户态需大量细粒度 syscall（CRIU 用数百个 setrlimit/prctl/mkdir）逐个重建→慢。

### 关键洞察

1. **"SHELF 格式 + spliceVMA 解耦物理存储布局和虚拟内存布局"**：磁盘上 snapshot 可以稀疏且乱序→spliceVMA 在内核中一次性 bulk 重建 VMA→无需复制到物理内存完美契合虚拟布局。类似 VTC "virtual tensor index mapping"——物理层级和逻辑层级解耦是最强大的优化之一。
2. **"Snapshot + working set 分离 = 避免不必要的 I/O"**：只恢复 working set pages→其余 lazy fault→类比冷热数据分层。Bulk metadata restore 替代逐个 syscall→消除数百个用户态 syscall 的开销。
3. **"OS 为 serverless 重新设计内存原语——不是优化 CRIU，是换掉它"**：现有系统（FaaSnap/CRIU）从磁盘恢复仍需 3.6-1197ms→Spice 仅 0.6-18ms。差距来自重新设计内存原语而非增量优化现有 snapshot 方案。

- 来源：Spice(OSDI'26)

### 实践启发
- **"物理-逻辑解耦是最强大的优化"**：类似 VTC virtual tensor、InfiniDefrag GPA-HPA remap——出现在存储/虚拟化/编译器等多领域
- **"Bulk restore > per-item restore"**：CRIU 的逐个 syscall 重建 = 批处理的完美反面案例——一个 spliceVMA 替代数百个 syscall
- **"OS 需要为 serverless 设计原语——不是在现有 OS 上打补丁"**：mmap/madvise 为传统进程设计→serverless 需要自己的 snapshot restore 原语。与 Arca 共享 "OS as serverless platform" 的设计哲学

---

## 分布式推测执行容错 (libDSE)

### 核心问题
Durable execution 引擎（Temporal/Azure Durable Functions/Beldi）自动持久化状态→透明恢复故障→简化分布式应用开发。但频繁的同步持久化产生显著延迟——而且随分布程度放大（更多组件→更频繁持久化→更高延迟）。现有方案无法绕过这个 correctness-performance 困境。

### 关键洞察

1. **"Decouple durable execution 的抽象与物理持久化"**：开发者代码假设同步持久化（简化编程），DSE runtime 透明地绕过并 delay 实际持久化→故障时反应式修复。类似 CoPilotIO "split SQ/CQ" 和 VTC "virtual tensor"——语义保证和物理执行解耦。
2. **"Speculation sandbox——隔离推测性执行的外部可见影响"**：Runtime 缓冲对外的所有输出（用户响应、legacy DB 写）直到底层状态真正 durable→外部系统永远看不到推测性结果。内部分布式组件可以自由 speculative 通信。
3. **"Trade-off 在 speculation unit 的故障概率"**：只要单次 RPC request 成功的概率 > 失败概率，绕过同步持久化就是净收益——在典型云环境中这一假设成立（故障率远低于成功率）。

- 来源：libDSE(OSDI'26)

### 实践启发
- **"语义-物理解耦"是云应用持久化的通用策略**：开发者看到同步语义，runtime 异步执行——类似 CoPilotIO "GPU 看到 I/O 完成，CPU 实际处理" 的分工模式
- **"Speculation sandbox = 外部边界缓冲"**：在所有外部可见的输出点设置缓冲→直到完成持久化才 release。这是 speculation 安全的必要前提——类似于事务的 write buffer/redo log

---

## 本地-云盘混合存储架构 (Latte)

### 核心问题
云本地存储（物理直连 SSD）提供近物理性能 + 低价，但缺乏云盘（EBS）的可用性、弹性和可访问性。高性能云盘（EBSX）可提供 30µs 延迟 + 1M IOPS + 强可用性，但价格是本地盘的 **20×**——对本地存储用户群体（CDN 缓存、大数据中间结果）无吸引力。需要一个架构同时获得本地盘的性能和 EBS 的弹性/可用性，且价格可行。

### 关键洞察

1. **"本地盘做高性能缓存 + 标准 EBS 做持久后端 → 用 ML dispatch 解耦两个路径"**：写入时 ML 二分类决定走缓存（吸收 burst + tail latency）还是后端（bypass 直写）；读取时 S3-FIFO 自动 promote 热数据到缓存。关键是 ML 模型足够轻量（Linear SVM, 200ns 推理），可 per-I/O 执行。

2. **"Auto-scale IOPS 使价格可行——不是固定保证最高性能，而是按需弹性伸缩"**：如果始终保证 1M IOPS，Latte 价格是本地盘的 13×；启用 auto-scale 后降至 2.1-4.0×——通过后端 IOPS 弹性伸缩，用户只在实际用到高 IOPS 时付费。这是"价格作为架构约束"的典型案例。

3. **"Append-only write ordering 替代分布式事务——两个独立路径的一致性由统一排序保证"**：写缓存和刷新后端都走 append-only 模式，compaction 期间保持相同顺序——简化为不需要复杂的一致性协议。

4. **"S3-FIFO candidate queue → 用极低成本过滤 one-hit-wonder（占 trace 的 72%）"**：首次 miss 仅记录元数据，第二次访问才 promote→缓存不被一次性访问污染→命中率 > 82%。

- 来源：Latte(FAST'26)

### 实践启发
- **"ML per-request dispatch + auto-scale backend" 是混合云服务的通用架构模式**：不仅适用于存储——任何 "fast-but-limited local + slow-but-elastic remote" 的组合（计算、内存、网络）都可以借鉴：用轻量 ML 决定每个请求走哪条路径，用弹性后端吸收溢出。
- **"价格可行性决定了架构能否落地"**：Latte 的 auto-scale IOPS 不仅仅是运维特性——它是架构从 PoC 走向生产的关键。在设计混合架构时，应该把"如何使边际成本可接受"作为一等架构约束。
- **"Append-only ordering 是跨路径一致性的轻量方案"**：当有多个独立写入路径时，强制所有路径共享同一个 append-only 顺序可以避免复杂的冲突解决逻辑。
