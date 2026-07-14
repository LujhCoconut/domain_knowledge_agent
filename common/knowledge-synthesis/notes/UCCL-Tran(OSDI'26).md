# UCCL-Tran(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-zhou-yang.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: UCCL-Tran 将 RDMA NIC 的控制路径（CC/可靠性/多路径 LB）从硬件解耦到 CPU 软件层运行，使 GPU 网络传输可编程扩展，多路径 collectives 性能最高提升 4.5×。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| RDMA QP (Queue Pair) | RDMA NIC 的通信端点，分为 RC (Reliable Connection)/UC (Unreliable Connection)/UD (Unreliable Datagram) | UCCL-Tran 选择 UC 作为首选 QP（bypass 硬件 CC+可靠性），UD 作为最后手段（完全 bypass） |
| UC (Unreliable Connection) | 一对一消息语义，但 NIC 硬件不处理可靠性或 CC | UCCL-Tran 的首选——保留 NIC 分段/重组 offload，bypass 硬件控制逻辑 |
| RDMA write_with_imm | RDMA 写操作携带 32-bit immediate data 到接收端 CPU | UCCL-Tran 分离控制头和数据 payload 的核心机制 |
| Scatter-gather (SG) list | RDMA verb 中指定多个不连续内存地址的机制 | UD 模式下分离控制头（→CPU）和数据（→GPU）的唯一手段 |
| Control coalescing | 每 32KB chunk 而非每 packet 做传输控制决策 | UCCL-Tran 以 1 core 饱和 400G 的关键——用精度换效率 |
| Packet spraying | 随机将同一连接的包分散到多条路径 | UCCL-Tran 解决 flow collision 的软件多路径策略 |
| Chained posting | 一次 MMIO write 提交最多 32 个 RDMA verbs | 减少 UD 模式下高频 verb posting 的 MMIO 开销 |
| SRD (Scalable Reliable Datagram) | AWS EFA 的专有多路径可靠传输协议 | EFA NIC 不支持 UC/RC，UCCL-Tran 用 UD bypass SRD 后在 CPU 实现自己的传输 |
| Connection splitting | 将同一连接的 256 QPs 均匀分给多个 CPU engine thread | 突破单核瓶颈，800G 时代更重要 |
| EQDS | 接收端驱动的 credit-based CC 协议（UEC 标准） | UCCL-Tran 的 extensibility case study：在软件中实现硬件无法支持的 receiver-driven CC |
| GPUDirect | NIC 直接 DMA 到 GPU memory，不经过 CPU | 保持 data path 高效，CPU 仅处理 control path |

## 背景与动机

ML 工作负载的网络需求在过去十年快速演进（参数服务器→allreduce→all-to-all EP），但 RDMA NIC 的 host transport 层在硬件中固化，难以演变。六个具体痛点：

1. **Flow collision**：ECMP 单路径 RDMA 易发生 hash collision → Alibaba 被迫重构物理拓扑（rail-optimized dual-plane）
2. **DCQCN 不适合 LLM 训练**：Meta 报告 DCQCN 在低 flow entropy 高突发下表现差 → 直接禁用 CC（但脆弱的 lossless 网络无 CC 会 deadlock）
3. **MoE serving incast**：DeepSeek-V3 的热 expert 负载可达 average 的 10× → 需要 receiver-driven CC 但无商用 NIC 支持
4. **Application-transport codesign**：MLT 等方案需定制 loss recovery 但 ConnectX-7 不够可编程
5. **Inefficient loss recovery**：旧 RDMA NIC 的 go-back-N 重传在丢包时性能极差
6. **异构 NIC**：不同代/厂商 NIC 的控制逻辑微妙不同 → 跨代通信带宽损失 2-33×

**根本原因**：硬件变更需数年，但 ML 网络需求以月为单位演变。

## 问题定义

**如何在现有 RDMA NIC 上构建可软件扩展的 transport 层，既保持 GPUDirect 的数据路径性能，又让 CPU 灵活控制 CC、多路径 LB、丢包恢复等控制路径决策？**

两个核心挑战：
1. 如何分离现有 RDMA NIC 的数据路径和控制路径？
2. 如何在 CPU 上运行控制路径仍达到硬件级性能（每服务器 3.2+ Tbps）？

## 方案介绍

### 架构

```
ML Application → Collective Library (NCCL/RCCL) → UCCL-Tran Plugin (SHM) → UCCL-Tran Engines (TX/RX/Pacer per NIC)
                                                                                ↓
                                                              RDMA UC/RC/UD QPs (256 per connection)
```

### 数据-控制分离（三种策略，按优先级）

| 策略 | QP 类型 | 分离机制 | 适用 NIC |
|------|---------|----------|----------|
| **首选** | UC | `write_with_imm`：32-bit imm_data 携带控制头→CPU，data payload→GPU via GPUDirect | NVIDIA ConnectX |
| **备选** | RC (CC disabled) | 同 UC，但无法定制丢包恢复（硬件 baked reliability） | Broadcom Thor-2 |
| **最后** | UD | Scatter-gather `send/recv`：CPU 构建 2-entry sg_list（header 64B→CPU + payload→GPU），NIC 自动 merge/split | AWS EFA |

### 软件多路径

- 256 QPs per connection（UC/RC）或 16×16 QPs (UD Src×Dst) → 最多 256 条等价路径
- **Power-of-Two sampling**：每次选择 RTT 最低的 2 条路径中更优的
- **全局 CC**（默认）：所有路径共享一个 cwnd，避免 per-path 状态爆炸
- 反驳了 "多 QP 不可扩展" 的传统认知：ML 工作负载的 bulk transfer（MTU 级大包）有效摊销 QP swapping 开销

### 高效软件 Transport 技术

| 技术 | 作用 | 效果 |
|------|------|------|
| **Control coalescing** | 每 32KB chunk 而非每 packet 做 CC/LB 决策 | 1 core 饱和 400G 单向 |
| **Connection splitting** | 256 QPs 均分给多个 CPU engine thread | 多核负载均衡，突破单核瓶颈 |
| **Chained posting** | 1 次 MMIO 提交 32 verbs | 减少 UD 模式 MMIO 开销 |
| **DRR scheduling** | Deficit Round Robin 公平复用 engine thread | Run-to-completion 模型 |
| **ACK 高优先级 QP + DRR 预算倾斜** | ACK 处理优先 | CC 决策延迟 <10µs P50 |

### Extensibility 案例

1. **Multipath + packet spraying**：per-path RTT + Swift/CUBIC CC + Power-of-Two LB
2. **Receiver-driven CC (EQDS)**：专用 pacer thread per NIC 主动分配 credit 给 senders → 解决 incast
3. **Selective retransmission**：SACK + bitmap + GPU memory reorder buffer → 丢包率 1/16384 时仅 1% 性能下降（vs RDMA go-back-N 的 26-42%）

## 证据与评估

### 测试平台

| 代号 | GPU | NIC | 拓扑 |
|------|-----|-----|------|
| CX_ETH | H100×8 | ConnectX-7 400G×8 | 跨机架 fat-tree |
| AMD | MI300X×8 | Broadcom Thor-2 400G×8 | 跨机架 rail-optimized |
| EFA | A100×8 | AWS EFA 100G×4 | 跨机架 fat-tree |
| CX_IB | H100×8 | ConnectX-7 400G×8 | 同机架 InfiniBand |

### 关键结果

1. **CX_ETH**：UCCL-Tran 比 ConnectX-7 硬件 transport 高 **2.32×**（allreduce, 4 QPs）和 **4.54×**（all-to-all, 16 QPs）——因为软件 LB 避免 flow collision，硬件 DCQCN 在拥塞时指数退避
2. **AMD**：all-to-all 高 **1.78×**（vs Thor-2 16 QPs），allreduce 持平（rail-optimized topology 已减少拥塞）
3. **EFA**：all-to-all 高 **3.27×**（vs SRD）——beefy CPU core 比 wimpy SmartNIC ARM core 在 connection-intensive all-to-all 上快得多
4. **CX_IB**（无拥塞）：UCCL-Tran 与 ConnectX-7 ASIC 性能几乎相同（差距 <4%），证明软件 transport 可达到硬件级性能
5. **DeepSeek-V2-Lite 训练**：端到端 throughput 提升 **7.5%**
6. **DeepSeek-V3 serving 模拟**：prefill 延迟降 1.13×，decode 延迟降 **1.42×**
7. **Incast 处理**：UCCL-Tran EQDS 比 InfiniBand CC 降低 P99.9 FCT **4.88×**（permutation traffic 受害流）
8. **丢包恢复**：1/16384 丢包率仅 1% 性能下降（vs 硬件 go-back-N 的 26-42%）
9. **非 RDMA NIC**：AF_XDP 模式比 kernel TCP 高 **4.1×**（small msg）

### CPU 开销

- 2 额外 CPU cores per NIC（1 engine thread + 1 pacer thread for receiver-driven CC）
- 1 core 可饱和 400G 单向流量
- GPU 服务器通常 128-192 cores，CPU 利用率仅 14-45%

## 整体评估

### 真正的新意
1. **首次证明 RDMA 软件 transport 可在 ML 工作负载上达到 ASIC 级性能**：UC + 256 QPs + control coalescing + connection splitting 的组合是新的设计点
2. **分离数据/控制路径的方法学贡献**：write_with_imm (UC/RC)、scatter-gather (UD)、AF_XDP (non-RDMA) 三种策略覆盖几乎所有 NIC
3. **将 "多 QP 不可扩展" 的结论修正为上下文相关**：ML bulk transfer 的 QP swapping 开销可摊销，与传统认知（针对 small-message KVS）不同
4. **Receiver-driven CC 首次在商品 RDMA NIC 上实现**：无需 SmartNIC 或硬件修改

### 优点
- 软件可扩展性：新 CC/LB/丢包恢复算法可快速迭代部署
- 跨 NIC 厂商兼容：NVIDIA/Broadcom/AWS EFA/non-RDMA 全支持
- 与 UEP 形成互补：UEP 解决 GPU-NIC 耦合的可移植性，UCCL-Tran 解决网络传输层的可扩展性
- 开源 + NCCL plugin 接口，drop-in 替换

### 局限与假设
- **UC 并非所有 NIC 都支持**：Broadcom 不支持 UC，AWS EFA 无 UC/RC → 需要 fallback 策略（RC with CC disabled 或 UD）
- **RTT 是相对受限的拥塞信号**：软件无法访问 ECN marks/trimming status（NIC 硬件消费了这些 header），只能依赖 RTT + 丢包
- **Control coalescing 的精度损失**：32KB chunk 在严重拥塞时可能不够精细（但模拟显示 degradation moderate, 2.8-17.9%）
- **CPU-assisted IBGDA 集成未完成**（future work）

### 适用条件
- 任何需要为 ML 工作负载定制网络传输行为的场景
- 多路径数据中心网络（ECMP fabric）——单路径网络无多路径收益
- 异构 NIC 环境（跨代/跨厂商）
- 非 RDMA NIC 也能受益（AF_XDP 模式比 kernel TCP 快 4.1×）

### 可复用启发
- **"用 UC bypass 硬件 CC + 用 imm_data 做控制通道"是可推广的 NIC 解耦模式**：不仅限于 ML，任何想绕过 RDMA 硬件控制逻辑的场景都可借鉴
- **"ML 工作负载的 bulk transfer 特性使多 QP 可行"**：挑战了 RDMA 社区长期持有的 "多 QP 不可扩展" 假设。大规模数据传输摊销了 QP swapping——这是一个上下文相关的修正，不是普遍推翻。
- **"Beefy CPU > Wimpy SmartNIC ARM"**：在 connection-intensive 工作负载下，服务器级 CPU 的绝对性能优势超过了 SmartNIC 的数据路径 proximity 优势。这对 SmartNIC 架构设计有重要启示。
- **Control coalescing 的 trade-off 是可接受的**：per-RTT 决策 + 32KB chunk 在绝大多数场景下与 per-packet 决策的差距 <10%，但 CPU 效率提升数十倍。这是工程上的 "good enough" 判断。
- **与 UEP 共享设计哲学**：两者都用 CPU 打破硬件刚性（UEP 解耦 GPU-NIC 通信发起，UCCL-Tran 解耦 NIC 传输控制），且两者来自同一团队（UC Berkeley SkyLab / Ion Stoica）。这代表了一个更宏观的趋势：**把硬件加速器的控制平面移到 CPU 软件层**。

### 讨论问题
- 如果 NIC 硬件提供更好的 HW-SW interface（如 multipath UC 抽象、暴露 ECN/trimming 信号），UCCL-Tran 能再快多少？
- UCCL-Tran + UEP 组合能否成为下一代 GPU 网络栈的事实标准？
- 800G NIC 时代，connection splitting 的重要性是否会线性增长？
