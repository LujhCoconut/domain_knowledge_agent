# Cloud-Native Architecture

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 解耦式 GC 服务 | disaggregated GC, RDMA paging, multi-tenant orchestration, peak shaving, concurrent marking | DGC(OSDI'26) |
| 联邦 LLM Serving 平台 | CRDT gossip, sovereign AI, heterogeneous GPU federation, service discovery overlay, HPC-to-serving bridge | OpenTela(OSDI'26) |
| Continuation-Centric OS | continuation capture, effect system, serverless primitives, zero-copy snapshot, functional I/O | Arca(OSDI'26) |
| Serverless 冷启动快照 | SHELF format, spliceVMA, snapshot restore, cold start, physical-logical decoupling, bulk metadata restore | Spice(OSDI'26) |

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
