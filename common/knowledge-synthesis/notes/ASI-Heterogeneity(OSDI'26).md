# ASI Heterogeneity(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-li-suyi.pdf
- **类型**: 论文-运维系统 (Operational Systems)
- **一句话 TL;DR**: Alibaba 异构 GPU 集群六个月 trace 分析——155,410 GPU、81 个部门。核心发现：GPU 碎片（非 fractional-GPU 共享）是主要闲置来源，defrag + SpotGPU 将分配率从 68% 提高到 93%。

## 核心问题

生产 AI 集群不再为单一 workload 设计——LLM 训练/推理、经典 DNN、推荐模型共存，GPU 型号（多代/多供应商）异构。高需求 != 高有效利用率：GPU 空闲但因碎片化而无法被分配。先前关注集中在 fractional-GPU 共享，但实际生产集群中几乎不使用 GPU 共享。

## 关键洞察

1. Fractional-GPU fragmentation 不再是主要问题——shared GPU 几乎不用。真正的问题是 stranded GPU、CPU-GPU 匹配、网络拓扑约束。
2. Defrag 算法将 Slack GPU 资源节点数减 20.2%。
3. SpotGPU = preemption-cost-aware 调度——安全收获闲置资源，分配率 68%→93%。
