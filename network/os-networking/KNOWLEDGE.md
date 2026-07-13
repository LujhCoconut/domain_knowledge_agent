# OS Networking

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 用户态网络 runtime 去中心化 | User Interrupt, task stealing, flow migration, centralized bottleneck elimination | SBB(OSDI'26) |
| 内核级 TCP RPC 消息调度 | HOL blocking, work-conserving scheduling, message-oriented API, kTLS | Rakaia(OSDI'26) |

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
