# Rakaia(OSDI'26)

- **来源**: OSDI '26, osdi26-yang-rui.pdf
- **全称**: Rakaia: Scalable In-Kernel Scheduling for TCP-Based RPCs
- **作者**: Rui Yang, Konstantinos Prasopoulos, Edouard Bugnion (EPFL)
- **类型**: 论文-系统 (networking + kernel + RPC)
- **一句话 TL;DR**: POSIX TCP 的字节流 API 与 RPC 的消息语义根本不匹配——导致 HOL blocking + 用户态线程池开销。Rakaia 将 **消息解析和工作守恒调度下沉到内核 TCP 接收路径**（最早介入点），消除 HOL blocking 并避免用户态繁重机制。基于 Linux 内核模块 + kTLS 支持，兼容 gRPC：vs Linux KCM 提升 **5×** throughput-under-SLO，vs gRPC-Go **1.56×**，vs gRPC-C++ **2.69×**，Silo TPC-C **1.39×**，OpenTelemetry **1.42×**。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **HOL blocking** (Head-of-Line) | 头请求阻塞：慢 RPC 阻塞同连接上后续 RPC 的处理 | TCP stream 导致的根本问题 |
| **KCM** (Kernel Connection Multiplexor) | Linux 内核现有的 TCP 消息 API | 对比 baseline（5× 改善） |
| **Work-conserving scheduling** | 让消息在到达时立刻被任何可用 core 处理，不等当前 core 空闲 | Rakaia 的核心调度策略 |
| **kTLS** | Kernel TLS — 内核内的 TLS 解密 | Rakaia 对加密流量的加速 |
| **Message-oriented API** | 直接暴露 RPC 消息而非字节流 | Rakaia 对用户的接口 |

## 核心洞察

RPC framework 在用户态做的全部复杂机制（I/O threads、work queues、worker pools、goroutines/channels）本质上是 **在字节流之上手动重建消息语义**。Rakaia 证明：把消息解析推到内核 TCP receive path 中——最早、最直接的介入点——可以消除整个用户态机制栈，同时获得更好的性能。

## 关键结果

| vs | 改善 |
|----|------|
| Linux KCM | **5×** throughput-under-SLO |
| gRPC-Go | **1.56×** |
| gRPC-C++ | **2.69×** |
| Silo TPC-C | **1.39×** |
| OpenTelemetry | **1.42×** |

## 可复用启发

- "在最早介入点重构语义"：如果底层 API 的语义抽象与上层需求不匹配，最根本的解决方式不是在上层打补丁（userspace abstractions），而是把语义重建推到最早的介入点（kernel receive path）
- gRPC 的 goroutine 数量非线性增长是用户态消息调度不可扩展的明确信号
- kTLS 在内核中使加密流量的消息级调度成为可能——安全 + 性能不再矛盾
