# OS Networking

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 用户态网络 runtime 去中心化 | User Interrupt, task stealing, flow migration, centralized bottleneck elimination | SBB(OSDI'26) |
| 内核级 TCP RPC 消息调度 | HOL blocking, work-conserving scheduling, message-oriented API, kTLS | Rakaia(OSDI'26) |
| 可移植专家并行通信 | CPU proxy, GPU-initiated token-level, RDMA immediate data, delivery semantics, heterogeneous GPU/NIC | UEP(OSDI'26) |

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
