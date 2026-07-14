# OpenTela(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-yao.pdf
- **类型**: 论文-运维系统 (Operational Systems)
- **一句话 TL;DR**: 用户态编排 overlay，将分散的 HPC 集群统一为跨机构的 LLM serving 平台——CRDT gossip 服务发现 + 异构 cluster manager/engine 统一 API + 异构感知调度。22 个月生产部署，1300 万请求、150 亿 tokens、142 个模型、1000+ 研究者。

## 核心问题

主权 AI 基础设施投资巨大（Alps 10K GH200、ABCI 3.0 6K H200、EU AI Factories C20B），但 HPC 集群面向批处理设计（Slurm、transient 分配、无持久端点），无法直接运行交互式 LLM serving（需要负载均衡、服务发现、弹性伸缩）。替换 Slurm 为 Kubernetes 不现实（HPC 依赖 MPI/拓扑感知等）。

## 关键洞察

1. **"Overlay 不替代现有集群管理器"**：用户态编排层在 Slurm/Kubernetes 之上→不需要 root 权限、不需要集群重配置→整合碎片化的异构 GPU 资源。
2. **"CRDT-based gossip 做容错服务发现"**：HPC 环境无 Kubernetes control plane→需要去中心化的服务发现机制。
3. **"Unified API over heterogeneous stacks"**：vLLM/SGLang/其他引擎 + Slurm/K8s 的统一接口→研究者不需要关心底层基础设施。

- 来源：OpenTela(OSDI'26)

### 实践启发
- **"Overlay 而不是替换"是整合异构基础设施的关键智慧**：改变底层调度器几乎不可能→在之上构建统一抽象层
- **"生产 trace 开源"**：22 个月、13M 请求的 trace 是宝贵的公开数据
