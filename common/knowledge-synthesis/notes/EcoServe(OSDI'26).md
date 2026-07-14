# EcoServe(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-du.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 部分解耦（PaDG）策略——单实例内时间维度 prefill/decode 分离 + 多实例循环激活 + 稀疏化 KV cache 传输，在无高性能互连的普通 GPU 集群上 serving LLM，goodput 提升 1.96-2.51×。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| NoDG (Non-Disaggregated) | Prefill 和 decode 在同一实例中 colocate | 商品集群的自然选择——但相位干扰严重 |
| FuDG (Fully Disaggregated) | Prefill 和 decode 完全分离到不同实例 | 需要高性能互联传输 KV cache——商品集群不具备 |
| PaDG (Partially Disaggregated) | 时间维度解耦 + 跨实例协作 | EcoServe 的核心——在普通 GPU 集群上实现两者的优势 |
| Macro instance | 多个实例组成的基本服务单元，循环激活 | 保证 prefill 持续可用→救援延迟 |
| Mitosis scaling | 动态调整 macro instance 内的实例数 | 细粒度在线容量调整 |
| Commodity GPU cluster | L20 GPU + Ethernet——无 NVLink/InfiniBand | 主流实际部署而非前沿集群 |

## 核心问题

现有两种 LLM serving 策略都不适合普通 GPU 集群（无高性能互联的主流生产环境）：NoDG（prefill/decode colocate）有严重相位干扰；FuDG（完全解耦）依赖 NVLink/InfiniBand 传输 KV cache。实际生产中 L20 + Ethernet 集群仍然大量存在。

## 关键洞察

1. **"PaDG：时间解耦而非空间解耦"**：单实例内在时间维度上交替 prefill 和 decode → 避免两者同时争抢 GPU 资源。多实例间循环激活→保证 prefill 持续可用。
2. **"Macro instance = 跨实例协作的基本单元"**：多个实例组成 macro instance，协作而非独立工作→缓解单实例隔离带来的 prefill 不可用问题。
3. **"减少 KV cache 传输的数据量"**：不是完全消除传输（FuDG 的代价），而是让传输变得稀疏→在 Ethernet 上也可行。

- 来源：EcoServe(OSDI'26)

### 实践启发
- **"二分之外有第三选择"**：colocate vs disaggregate 不是二选一——partial disaggregation 在两者之间找到平衡点
- **"专为 commodity hardware 设计的系统"**：大多数系统研究假设前沿硬件（H100+NVLink+IB），但实际生产环境的硬件替换周期长得多
