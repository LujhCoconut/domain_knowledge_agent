# μFork(SOSP'25)

- **来源**: SOSP '25, DOI:10.1145/3731569.3764809
- **作者**: John Alistair Kressel (Manchester), Hugo Lefeuvre (UBC), Pierre Olivier (Manchester)
- **类型**: 论文-系统/OS安全
- **一句话 TL;DR**: 在单地址空间 OS 中实现完整 POSIX fork——通过 CHERI 能力指针实现 μprocess 模拟 + CoPA (Copy-on-Pointer-Access) 延迟重定位，54μs fork（3.7× faster than 传统 fork），24% 更高 FaaS 吞吐。

## 核心问题

单地址空间 OS (SASOS) 有天然的 lightweightness 优势（kernel 和应用共享同一地址空间→零页表切换开销），但 POSIX fork 的语义建立在多地址空间之上（子进程需要独立的地址空间）。这使 SASOS 无法运行多进程 POSIX 应用。过往方案都有 trade-off：复制到新地址空间（loss of lightweightness）、不支持完整 POSIX（loss of compatibility）、或弱隔离（loss of isolation）。

## 关键洞察

1. **"μprocess = 同地址空间内的进程模拟"**：不创建新地址空间→在同一 SAS 内将父进程内存复制到不同位置→形成 μprocess（逻辑上独立的进程）。挑战有二：(C1) 子进程的所有绝对指针仍指向父进程区域→需要全局指针重定位；(C2) 需要强隔离同时保持 lightweightness。
2. **"CHERI 能力 = 一个硬件机制同时解决指针重定位 + 隔离两个问题"**：CHERI 将 64-bit 指针扩展为 128-bit capability（含 bounds、permissions、unforgeable tag）。对 C1：tagged memory 使 μFork 能精确识别哪些内存位置包含指针→只重定位真正的指针。对 C2：硬件 enforced capability checks 提供 intra-address-space 隔离→不需要页表切换。
3. **"CoPA (Copy-on-Pointer-Access) = fork 优化新维度"**：传统 CoW 在 write 时复制→CoPA 在 **load pointer** 时复制。子进程首次访问某页上的指针才触发复制+重定位→大幅减少不必要的 eager copy。CHERI 的 capability-load fault 使 CoPA 成为可能——硬件在加载 capability 时精确 fault→无 CHERI 的硬件无法实现。CoPA 比同步复制减少 fork 延迟 **89×**。

- 来源：μFork(SOSP'25)

## 实践启发

- **"CHERI 不仅是安全特性——也是 OS 基础设施"**：CHERI 常被视为内存安全工具→μFork 展示了 capability 可以用于指针重定位、进程隔离、efficient fork——将 CHERI 从 "安全检查" 提升为 "OS 构建块"。类似 InfiniDefrag "GPA 是虚拟的"——一个硬件能力的重新利用可以解锁全新的 OS 设计
- **"CoPA 揭示了 fork 优化的新维度"**：传统 CoW 只区分 read/write→CoPA 进一步区分 data access/pointer access。这是在更精细粒度上应用 lazy evaluation 的思想——pointers 是特殊数据，等待直到真正被解引用。类似 VTC "index mapping 替代 data copy"——懒惰到最后一刻
- **"SASOS + fork 兼容可以解锁新的部署模型"**：FaaS worker warm-up +24%、Redis snapshot 1.4-1.9× 更快、54μs fork——这些数字表明 SASOS 的 lightweightness 优势在 fork-intensive workloads 上表现突出。如果 CHERI 硬件普及，SASOS 可能是某些场景（FaaS、快速快照、多 worker）的最佳选择
- **"POSIX 兼容性是 OS 研究的硬约束——不是可选的"**：μFork 可以运行 unmodified Redis/Nginx——这降低了 SASOS 的 adoption barrier。类似 hS/Incr/LithOS 的 "transparency is non-negotiable" 哲学
