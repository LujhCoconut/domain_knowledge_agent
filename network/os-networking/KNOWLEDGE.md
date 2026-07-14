# OS Networking

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 用户态网络 runtime 去中心化 | User Interrupt, task stealing, flow migration, centralized bottleneck elimination | SBB(OSDI'26) |
| 内核级 TCP RPC 消息调度 | HOL blocking, work-conserving scheduling, message-oriented API, kTLS | Rakaia(OSDI'26) |
| 可移植专家并行通信 | CPU proxy, GPU-initiated token-level, RDMA immediate data, delivery semantics, heterogeneous GPU/NIC | UEP(OSDI'26) |
| RDMA 软件传输层可扩展 | control/data path separation, UC multipath, control coalescing, receiver-driven CC, packet spraying | UCCL-Tran(OSDI'26) |
| FPGA 可编程 RDMA 卸载引擎 | decoupled state, streaming control-data separation, 100G RoCEv2, fully customizable transport, SmartNIC | BALBOA(OSDI'26) |
| SmartNIC 数据路径 KV Store | DPA, learned index tree, on-path processing, lock-free, stateless clients, range query, BlueField-3 | DPA-Store(OSDI'26) |
| DDIO 页着色 LLC 优化 | DDIO, page coloring, LLC conflict miss, sliced cache, leaky DMA, color-aware allocator | Sepia(OSDI'26) |

---

## 用户态网络 Runtime 去中心化

### 核心问题
现有用户态网络 runtime 依赖集中式 timer/monitor/dispatcher 进行请求抢占、CPU 分配和负载均衡——这些组件随 worker core 增长成为可扩展性瓶颈。传统方案增加核心数不能解决根本问题。

### 关键洞察

1. **集中式实体的扩展极限比预期更早到达**：C-timer/C-monitor/C-dispatcher 的竞争和同步开销随 N 增长
2. **User Interrupt 是实现去中心化抢占的新原语**：core-to-core 直接中断，无需集中式 timer core 的周期性检查
3. **Two-level 负载均衡处理不同时间尺度的不均衡**：临时→task stealing (快速+局部)；持续→flow migration (全局+正确)
- 来源：SBB(OSDI'26)

### 实践启发
- "去中心化优先"应成为高性能网络 runtime 的设计原则
- User Interrupt 是比 shared-memory queues 更高效的核心间信号机制

---

## 内核级 TCP RPC 消息调度

### 核心问题
POSIX TCP 字节流 API 与 RPC 消息语义根本不匹配——导致 HOL blocking 和繁重的用户态线程池开销。gRPC 的 I/O threads + work queues + worker pools + goroutines 本质是在字节流之上手动重建消息语义。

### 关键洞察

1. **"在最早介入点重构语义"优于在上层打补丁**：将消息解析推到内核 TCP receive path → 消除整个用户态机制栈
2. **Work-conserving scheduling 在 in-kernel 比在 userspace 更高效**：内核可以更早访问消息边界，不需要先上推再下分
3. **kTLS 使加密流量的内核级消息调度成为可能**：安全 + 性能不矛盾
- 来源：Rakaia(OSDI'26)

### 实践启发
- 如果底层 API 抽象（字节流）与上层需求（消息）不匹配，最根本的方案不是在用户态打补丁，而是在内核中最早介入点重构语义
- gRPC goroutine 数量随连接数非线性增长是用户态消息调度不可扩展的信号

---

## 可移植专家并行通信 (UEP)

### 核心问题
MoE 专家并行通信依赖 GPU-initiated token-level RDMA（如 DeepEP），性能优异但 GPU 和 NIC 紧耦合——GPU 需直接写 NIC MMIO 寄存器，依赖 proprietary register layout 和硬件级 co-design。导致 O(m×n) 集成成本：每对 GPU+NIC 组合需独立开发。DeepEP 仅支持 NVIDIA GPU + NVIDIA NIC，在 AWS EFA、AMD GPU + Broadcom 等平台上无法运行。EP 通信占训练 forward pass 43.6%、端到端 32%，serving 中占 47%，可移植性缺失直接影响成本优化和供应商选择。

### 关键洞察

1. **"GPU 发起、CPU 执行"解耦**：GPU 只需发起 token 级传输以获得 fine-grained overlap 的最大性能，传输的监控和管理不需要留在 GPU 上。CPU 通过 libibverbs 对任何 GPU（CUDA/ROCm）和任何 NIC 可移植。
2. **CPU 是异构系统中被低估的万能适配器**：GPU 服务器 CPU 利用率通常仅 14-45%，数百核心大量闲置。CPU proxy 利用这些核心执行 RDMA、强制交付语义、做流控——几乎零成本。
3. **"不需要全局排序，只需要局部排序"**：per-channel ordering（同通道消息入同 FIFO）大幅降低实现复杂度——仅需保证同一 ring buffer 的 write/atomic 不重排。
4. **软件模拟 atomics 比硬件 RDMA atomics 更快**：piggyback 在 immediate data 上由 CPU proxy 应用，省去额外 RDMA atomic 消息的 ~1µs 延迟——因为 atomic 携带的数据已在 write 的 immediate data 中。
5. **Immediate data 是最廉价的带外控制通道**：32-bit 足以嵌入序列号 + expert index + offset，无需额外控制消息。

- 来源：UEP(OSDI'26)

### 实践启发
- **"解耦发起与执行"可推广到任何设备间紧耦合场景**：不仅是 GPU↔NIC，任何"设备 A 需直接控制设备 B 但缺乏硬件互操作性"的场景都可引入中间代理
- CPU 是异构硬件之间最通用的"胶水"——libibverbs + CUDA/ROCm 提供了天然的可移植抽象层
- 在硬件不提供所需语义时，用软件在接收端补偿（conditional buffering + sequence number），比要求硬件升级更务实
- 多线程 CPU proxy 的设计模式可复用于任何需要"快速转发 GPU 命令到外部设备"的场景
- 端口努力从 O(m×n) 降到 O(m)：只需为每种 GPU 移植 kernel，CPU 侧代码完全复用

---

## RDMA 软件传输层可扩展 (UCCL-Tran)

### 核心问题
ML 工作负载的网络需求以月为单位快速演进（从 allreduce 到 all-to-all EP 到 disaggregated serving），但 RDMA NIC 的 host transport 层（CC、丢包恢复、多路径 LB）在 ASIC 硬件中固化——硬件变更需数年。具体痛点：(1) ECMP 单路径易发生 flow collision，Alibaba 被迫重构物理拓扑；(2) DCQCN 不适合 LLM 训练的低 flow entropy + 高突发流量，Meta 直接禁用了 CC；(3) MoE serving 的热 expert 造成 incast 但无商用 NIC 支持 receiver-driven CC；(4) 旧 NIC 的 go-back-N 重传在丢包时性能极差；(5) 异构 NIC 跨代通信带宽损失 2-33×。

### 关键洞察

1. **"用 UC bypass 硬件控制逻辑 + 用 imm_data 做 CPU 控制通道"**：RDMA UC（Unreliable Connection）保留 NIC 的分段/重组 offload 但 bypass 了硬件 CC 和丢包恢复。32-bit `write_with_imm` 将传输控制头（seq、ack、credit）送到接收端 CPU，data payload 仍通过 GPUDirect 直达 GPU memory。这是最优雅的数据-控制分离方案。

2. **"ML 工作负载的 bulk transfer 使多 QP 可行"**：RDMA 社区长期认为多 QP 不可扩展（SRNIC 报告 256→16K QPs 带宽降 46%），但 UCCL-Tran 发现这仅适用于 small-message CPU 工作负载。ML 的 MTU 级大包传输有效摊销了 QP swapping 开销——256 QPs 仅比 60 QPs 降 ~17%（RC）甚至无明显下降（UC）。这是一个上下文相关的关键修正。

3. **"Beefy CPU > Wimpy SmartNIC ARM"在 connection-intensive 场景下**：EFA 的 SRD 运行在 SmartNIC ARM 核上，在 all-to-all（大量连接）时被 UCCL-Tran 的服务器 CPU 碾压（3.27×）。服务器级 CPU 的绝对性能优势超过了 SmartNIC 的 data-path proximity 优势。

4. **"Control coalescing 是软件 transport 高效的关键"**：per-packet 决策（如硬件 DCQCN）需要极高 CPU 开销。UCCL-Tran 改为 per 32KB chunk 做 CC/LB 决策——精度损失 moderate（模拟显示 sender-driven 降 17.9%，receiver-driven 仅 2.8%），但 CPU 效率提升数十倍（1 core 饱和 400G 单向）。

5. **"连接拆分突破单核瓶颈"**：将 256 QPs 均分给多个 engine thread，每个 thread 独立维护 CC/LB 状态 → 消除单核处理瓶颈。800G 时代将更加关键。

- 来源：UCCL-Tran(OSDI'26)

### 实践启发
- **"UC + imm_data"是 RDMA 控制路径软件化的通用 recipe**：任何想绕过 RDMA 硬件 CC/可靠性逻辑的场景都可复用此模式
- **"不假设硬件可编程，而是用现有接口绕过硬件的固化逻辑"**比依赖 SmartNIC 或等硬件升级更务实、更快落地
- **UCCL-Tran + UEP 来自同一团队，共享设计哲学**：两者都把硬件加速器的控制平面移到 CPU 软件层——UEP 解耦 GPU-NIC 通信发起，UCCL-Tran 解耦 NIC 传输控制。这代表一个宏观趋势。
- **ML 工作负载的特征（大消息、bulk transfer、bursty）应被用来重新审视旧假设**：多 QP 不可扩展、RTT-based CC 不够精确、CPU 无法处理线速——这些假设在 ML 场景下都需要重新验证
- **对 SmartNIC 架构设计有启示**：通用服务器 CPU 在处理 connection-intensive control plane 时可能优于专用 SmartNIC ARM 核。SmartNIC 应聚焦于 data plane offload（分段/重组/DMA），控制平面留给 CPU

---

## FPGA 可编程 RDMA 卸载引擎 (BALBOA)

### 核心问题
商用 RDMA NIC (ConnectX 等) 是黑盒——传输层不可修改（安全策略/拥塞控制/应用逻辑卸载全被锁死）。FPGA 平台可编程但性能低（<100G）、协议不完整（缺 CRC/重传）、不兼容真实数据中心。学术界缺乏一个**既高性能又完全可编程**的 RDMA 平台。

### 关键洞察

1. **"Decoupled state architecture + streaming control-data separation"**：克服 FPGA 内存/时序瓶颈——控制路径和数据路径在硬件层流式分离。
2. **"完整 RoCEv2 协议栈在 FPGA 上可行"**：CRC + 重传 + 数百 QPs + switched network——此前被认为 FPGA 无法实现。
3. **"可编程传输层解锁两个用例"**：infra 层的加密+深度包检测 + application 层的推荐系统预处理卸载。

- 来源：BALBOA(OSDI'26)

### 实践启发
- **"BALBOA 和 UCCL-Tran 覆盖了 RDMA 可编程化的完整光谱"**：BALBOA 在**硬件层**重写 NIC 本身（FPGA），UCCL-Tran 在**软件层**解耦 data/control path（现有 NIC）——两者互补而非竞争
- **"开源硬件是打破黑盒供应商锁定的关键"**：如果 RDMA 研究只能依赖 ConnectX 黑盒，整个领域无法进步

---

## SmartNIC 数据路径 KV Store (DPA-Store)

### 核心问题
远程 KV store 三难：高吞吐 + 范围查询 + 低复杂度。Hash-based SmartNIC offload (MICA/KV-DIRECT) 快但不支持范围查询；RDMA 分布式需要客户端缓存→有状态→故障处理复杂；host 端 tree traversal 产生大量 DMA round-trip。

### 关键洞察

1. **"On-path 处理消除 OS 开销"**：请求不经过 host OS 网络栈——DPA 直接从 NIC buffer 取请求。16 核 × 16 线程 = 256 并行线程。
2. **"Learned index tree 存储在 DPA 内存"**：256 线程并发遍历→叶子层 fetch host 侧值。Writes 缓冲在 DPA、批量到 host。
3. **"计算密集型 rebalance 在 host 执行，事务性缝合回 SmartNIC"**：利用 host CPU 的大规模计算能力处理树结构调整，DPA 专注于快速路径。

- 来源：DPA-Store(OSDI'26)

### 实践启发
- **"Fast path 在 SmartNIC，slow path 在 host——职责按延迟/复杂度拆分"**：DPA（16 核 ARM）处理热路径，host CPU 处理复杂 rebalance。与 CoPilotIO、UEP、UCCL-Tran 共享设计哲学
- **"Learned index 在 SmartNIC 上天然适配"**：小模型（learned index）+ 高并发（256 线程）是 SmartNIC 的理想匹配

---

## DDIO 页着色 LLC 优化 (Sepia)

### 核心问题
Intel DDIO 使 NIC 接收数据可从 LLC 直接访问（避免 DRAM 往返），但 "leaky DMA"——数据在处理前被逐出 LLC。传统诊断认为是 DDIO 保留容量太小。**本文推翻此假设**。

### 关键洞察

1. **"冲突缺失是主要共因，而非容量缺失"**：Linux 默认内存分配器导致 page working set 在 sliced LLC 中分布不均→即使 LLC 有空间也发生 eviction。Page coloring 可提升有效容量 **77.8-94.4%**。
2. **"Sliced LLC 架构下 page placement 比单 LLC 时代更重要"**：现代 CPU 的分布式 LLC 使 page 在哪个 set 中落位影响巨大——这是硬件趋势使旧方案（page coloring）重新相关的典型案例。
3. **"仅 3.5 核饱和 200Gbps"**（vs Linux 6 核）：LLC miss 从 bottleneck 变为 minimally present（0.4% miss rate）。

- 来源：Sepia(OSDI'26)

### 实践启发
- **"冲突缺失常被误诊为容量缺失"**：不仅是 DDIO——page cache、KV store 索引等场景中 page coloring 可大幅提升有效缓存容量
- **"硬件趋势使老技术重新相关"**：sliced LLC 架构让 page coloring 从 "nice to have" 变为 "critical"——类似 Helmsman 的 clustering 回归
