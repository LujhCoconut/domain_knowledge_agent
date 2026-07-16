# AITurbo(FAST'26)

- **来源**: https://www.usenix.org/system/files/fast26-hao.pdf, FAST '26
- **作者**: Yingyi Hao, Xingda Wei, Rong Chen (SJTU), Ting Yao, Huatao Wu (Huawei Cloud)
- **一句话 TL;DR**: 华为云 AI 存储系统——利用闲置 compute fabric(XPU-XPU 高速互联)做 staging buffer + Grouped I/O API 自动生成去重+负载均衡读/写计划，checkpoint 写 3.9-58.8× faster than 通用云存储，比 Gemini 快 5.9×，KVCache 读比 Mooncake 快 1.28×。

## 核心问题

AI 训练/推理对云存储带宽需求暴增(华为云 AI 消耗 >10%)，但 disaggregated 存储架构下提高存储带宽需增加存储服务器→成本线性增长。应用层优化(Megatron 1/4 代码量用于 checkpoint I/O)仍不理想→因为无法感知底层复杂的 disaggregated 架构。

## 方案设计

### 两个核心洞察

1. **Compute fabric 闲置**: XPU-XPU RDMA (200Gbps per XPU) 远超存储 fabric (100Gbps per node)→可作高速 staging buffer
2. **Grouped I/O API**: 类似 MPI 的 grouped communicator→应用声明"哪些 XPU 参与此次 I/O"→存储层自动推导优化计划

### 设计

- **Write plan**: 双线性规划→去重+负载均衡分配 chunk 到 storage servers→host DRAM staging→异步 flush
- **Read plan**: storage servers→host DRAM staging→compute fabric broadcast 到 requesting XPUs
- **Job controller**: 全局协调 grouped I/O，避免重复去重和独立规划

## 关键数据

| 场景 | AITurbo |
|------|---------|
| Checkpoint write vs 通用云存储 | **3.9-58.8×** faster |
| vs Gemini (应用级优化) | **5.9×** faster |
| KVCache read vs Mooncake | **1.28×** faster |
| 代码改动 | 仅 ~100s LOC vs Megatron 1/4 代码量 |
| 部署 | 华为云生产训练集群 |

## 可复用启发

1. **"闲置 compute fabric→storage staging→不增加存储成本提升带宽"**: XPU-XPU 高速互联不被存储瓶颈使用→作为 file transfer 的 staging area。类似 RASK 的思路——把工作从瓶颈资源搬到闲置资源

2. **"Grouped I/O = 让存储层感知应用层 I/O pattern→自动推导优化"**: 类似 PPC+MAIO 的 I/O 模板思路——应用声明意图，底层自动生成最优 plan。关键是 API 简单到足以被广泛采用

3. **"透明去重+全局规划 > 应用层手动优化"**: 存储层有全局视角→能看到跨 XPU 的重复 chunk→集中式去重比各 job 独立去重更有效
