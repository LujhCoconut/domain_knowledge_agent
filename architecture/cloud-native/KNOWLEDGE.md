# Cloud-Native Architecture

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 解耦式 GC 服务 | disaggregated GC, RDMA paging, multi-tenant orchestration, peak shaving, concurrent marking | DGC(OSDI'26) |
| 联邦 LLM Serving 平台 | CRDT gossip, sovereign AI, heterogeneous GPU federation, service discovery overlay, HPC-to-serving bridge | OpenTela(OSDI'26) |

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
