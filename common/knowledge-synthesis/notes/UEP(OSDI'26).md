# UEP(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-mao-ziming-uep.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: UEP 通过 CPU proxy 解耦 GPU 通信发起与 NIC 通信执行，使 MoE 专家并行通信在异构 GPU/NIC 硬件上可移植且保持高性能，打破 IBGDA 的 O(m×n) 集成成本。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| Expert Parallelism (EP) | 将不同 expert 分布到不同 GPU，token 激活以 all-to-all 方式通信 | MoE 训练/推理的核心并行策略 |
| IBGDA (InfiniBand GPUDirect Async) | GPU 直接写 NIC MMIO 寄存器发起 RDMA 的技术 | 现有 GPU-initiated 通信的基础，但造成 GPU-NIC 紧耦合 |
| GPU-initiated token-level communication | GPU 线程直接向 NIC 提交细粒度传输命令（per-token 或 per-chunk） | DeepEP 的核心设计，性能高但可移植性差 |
| CPU proxy | 运行在主机 CPU 上的多线程代理，接收 GPU 控制命令并代为执行 RDMA | UEP 的核心抽象——解耦通信发起与执行 |
| TransferCmd | 128-bit 的紧凑控制描述符（Write/Atomics/Drain/Barrier） | GPU 通过 FIFO 通道传递给 CPU proxy 的命令格式 |
| Immediate data | RDMA 写操作可在包头中携带的 32-bit 数据 | UEP 用它嵌入序号 + expert index，在接收端实现排序/条件应用 |
| SRD (Scalable Reliable Datagram) | AWS EFA 的可靠但不保序传输协议 | EFA 不保证有序交付，UEP 用 CPU proxy 在软件层补偿 |
| LL / HT mode | Low-Latency（立即发送，适合 decode）和 High-Throughput（批量+去重+分层 reduce，适合 prefill/training） | DeepEP/UEP 的两种通信模式 |
| Symmetric memory | GPU 暴露固定大小的 transport buffer，通信双方通过 offset 而非全局地址引用 | 减少 TransferCmd 位数，消除对 NVSHMEM 的依赖 |

## 背景与动机

- MoE 模型中 EP 通信占 forward pass 43.6%、端到端训练 32%，serving 中占 47%
- DeepEP（GPU-initiated token-level 通信）性能优异，但仅支持 NVIDIA GPU + NVIDIA NIC
- 根本原因：GPU 直接写 NIC MMIO 需要 proprietary register layout 和硬件级 co-design → O(m×n) 集成成本
- 例如：DeepEP 无法在 AWS EFA 上运行，也无法在 AMD GPU + Broadcom NIC 上运行

## 问题定义

**如何设计一个在异构 GPU（NVIDIA/AMD/Intel）和异构 NIC（EFA/Broadcom/ConnectX）上既可移植又保持 GPU-initiated token-level 通信高性能的 EP 通信系统？**

现有方案的分裂：
- CPU-initiated（NCCL/RCCL/PPLX）：可移植但性能差（缺少 token 级去重、分层 reduce 等优化）
- GPU-initiated（DeepEP/Mori-EP）：性能好但绑定特定 GPU-NIC 组合

## 方案介绍

### 核心洞察

**GPU 只需发起（initiate）token 级传输以获得最大性能，而传输的监控和管理不需要留在 GPU 上。CPU 通过 libibverbs 对任何 GPU/NIC 可移植，且 CPU 灵活到可以强制执行 GPU 内核所需的各种交付语义。**

### 架构

```
GPU → FIFO Channel (128-bit TransferCmd) → CPU Proxy Threads → libibverbs → GPUDirect RDMA → Remote GPU
```

三大组件：
1. **CPU-GPU FIFO 通道**（§3.1）：lock-free、单向（GPU→CPU）、split metadata（head 在 GPU 侧，tail 在 CPU 侧，各自本地 polling）
2. **多线程 CPU Proxy**（§3.2）：每 GPU 一个 proxy，最多 4 线程，负责连接建立、地址翻译、QP 负载均衡、语义强制执行
3. **交付语义强制执行**（§3.3）：利用 RDMA immediate data 嵌入序列号 + expert index，接收端 CPU proxy 条件性地缓冲/应用 atomic 消息

### 四种 TransferCmd

| 命令 | 作用 | GPU 侧是否阻塞 |
|------|------|----------------|
| Write | 委托 CPU proxy 执行 RDMA 写 + 可选 piggyback atomic | 否 |
| Atomics | 委托 CPU proxy 执行原子操作（远程 doorbell / 计数器更新） | 否 |
| Drain | 等待所有 outstanding RDMA 完成 | 是（检查 completion） |
| Barrier | 建立同步屏障（all-peer 或 same-rail） | 是（检查 completion） |

### 两种通信模式

- **LL mode**（decode）：token 立即可用就立即发送，无同步等待
- **HT mode**（prefill/training）：批量发送 + 消息去重 + 节点内转发 + 分层 reduce，多 ring buffer 通道

### 交付语义处理

- **LL kernel**：atomic 消息被 CPU proxy 缓冲在 control buffer 中，直到该 expert 的 X 个 write 全部到达后才应用（partial completion fence）
- **HT kernel**：per-channel 局部排序——同通道消息进入同 FIFO，接收端按序列号顺序应用

### 可移植性

- 支持新 NIC：只需 libibverbs 接口 + 少量适配代码
- 支持新 GPU：只需移植 GPU 侧 kernel（调 UEP transport API），CPU 侧代码完全复用
- NVDIA+EFA 仅需 3 person-months

## 证据与评估

### 测试平台

| 代号 | GPU | NIC | 规模 |
|------|-----|-----|------|
| NV_EFA3 | H200×8 | EFAv3 200G×16 | 4 节点 |
| NV_EFA4 | B200×8 | EFAv4 400G×8 | 4 节点 |
| NV_IB | H100×8 | ConnectX-7 400G×8 | 4 节点 |
| NV_C2C_IB | GH200×1 | ConnectX-7 200G×1 | 2 节点 |
| AMD_IB | MI300X×8 | ConnectX-7 400G×8 | 4-16 节点 |
| AMD_BRC | MI300X×8 | Broadcom Thor-2 400G×8 | 4 节点 |

### 关键实验结果

1. **Training on AMD** (Fig 8): UEP 比 RCCL 高 7-36% TFLOPS、7-45% tokens/s（DeepSeek-V3 16 节点）
2. **Training on NVIDIA+EFA** (Table 3): UEP 比 NCCL 高 12-24% TFLOPS（Qwen3-235B, DeepSeek-V3）
3. **Inference on SGLang+EFA** (Fig 9): UEP 比 NCCL 高 40% throughput（Qwen3 EP=32: 62K vs 44K tok/s）
4. **Microbenchmark on EFA** (Fig 10): EP32 dispatch UEP 比 PPLX 低 2.3× 延迟，combine 低 1.1-1.5×
5. **Microbenchmark on IB** (Fig 12): HT mode UEP 与 DeepEP 性能可比（dispatch 差距 <5%），比 PPLX 好 2.1×（dispatch）和 1.6×（combine）
6. **GH200 C2C** (Fig 13): LL mode UEP 延迟低于原始 DeepEP（cache-coherent C2C 链路消除 PCIe 开销）
7. **AMD+Broadcom** (Fig 14): UEP 在 Broadcom 和 IB NIC 上性能相当，首次在非 NVIDIA 平台运行 GPU-initiated token-level 通信
8. **Emulated atomics** (Fig 18): 软件模拟的 atomics 延迟与纯 RDMA write 几乎一致（~1µs 优势 over 硬件 atomic）

### CPU 开销

- CPU 利用率从 ~8% 升至 ~22%（仍远低于 100%）
- CPU proxy 延迟仅 3-5µs，相比 dispatch/combine 延迟（LL ~200µs, HT >2000µs）可忽略
- FIFO 通道可扩展到 8 Mops/s

## 整体评估

### 真正的新意
1. **"GPU 发起、CPU 执行"的解耦架构**：此前无人提出让 GPU 保持 token-level 发起但将 RDMA 执行委托给 CPU
2. **CPU 作为交付语义的"万能适配器"**：用 immediate data + 接收端 conditional buffering 在软件层实现硬件未提供的排序保证
3. **对 EP 通信系统可移植性问题的第一次系统化解决**：之前都是针对特定 GPU-NIC 组合的 ad hoc 方案

### 优点
- 架构简洁：CPU proxy 抽象统一了异构硬件差异
- 可移植性和性能兼得：在非 NVIDIA 平台上首次实现 GPU-initiated token-level 通信
- 与现有框架兼容：drop-in replacement for DeepEP API
- CPU 利用现有闲置资源（GPU 服务器 CPU 利用率通常 14-45%）

### 局限与假设
- LL mode 在 IB 上比 DeepEP 略慢（CPU proxy 对小消息的开销）
- 依赖 libibverbs——需要 NIC 厂商提供 verbs provider（大多数 RDMA NIC 都支持）
- CPU 和 GPU 通常 fate-share（同服务器），不引入独立故障域
- 未深入探索 congestion control（仅在 §6 讨论为 future work）

### 适用条件
- 任何需要 GPU-initiated token-level 通信但没有 IBGDA 支持的平台（非 NVIDIA GPU、非 IB NIC）
- 云环境（AWS EFA）——这是 UEP 的主要优势场景
- 异构集群（混合 GPU/NIC 厂商）

### 可复用启发
- **"解耦发起与执行"可推广**：任何需要"设备 A 直接控制设备 B 但缺乏硬件互操作性的场景"都可以引入中间代理（不限于 GPU↔NIC）
- **CPU 是异构系统中最被低估的桥梁**：libibverbs + CUDA/ROCm 提供了天然的可移植层
- **Immediate data 是廉价的控制通道**：32-bit 足够嵌入序列号 + 目标 index，避免额外的控制消息
- **"不需要全局排序，只需要局部排序"**：per-channel ordering 大幅降低实现复杂度
- **软件模拟 atomics 几乎零成本**：piggyback 在 immediate data 上，比硬件 RDMA atomic 快 ~1µs

### 讨论问题
- 随着 800G 网络到来，FIFO 通道是否会成为瓶颈？（作者认为轻量级 batching 可解决）
- CPU proxy 模式能否推广到其他 GPU-initiated 通信模式（非 EP，如 all-reduce）？
- 当 CPU 和 GPU 不 fate-share 时（disaggregated 架构），故障模型需要重新审视
