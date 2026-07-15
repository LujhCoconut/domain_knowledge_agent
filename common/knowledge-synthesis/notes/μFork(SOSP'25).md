# μFork(SOSP'25)

- **来源**: SOSP '25, doi:10.1145/3731569.3764809 (arXiv:2509.09439)
- **作者**: John Alistair Kressel (Manchester), Hugo Lefeuvre (UBC), Pierre Olivier (Manchester)
- **类型**: 论文-系统/OS安全
- **一句话 TL;DR**: 单地址空间 OS 中实现完整 POSIX fork——CHERI capability 硬件同时解决指针重定位(C1)和 intra-AS 隔离(C2)。CoPA (Copy-on-Pointer-Access) 在首次 load capability 时触发复制。54μs fork (3.7× faster than CheriBSD), 198× faster than Nephele (VM-based), 24% 更高 FaaS 吞吐。

## 核心问题

SASOS 的 lightweightness 来自同一地址空间（零页表切换、零 TLB flush、快速安全域切换）。但 POSIX fork 语义建立在多地址空间之上→SASOS 无法运行 50% of 最流行 Debian packages (Redis/Nginx/OpenSSH/Apache/Qmail)。过往方案在 lightweightness/compatibility/isolation 三角中总牺牲一角：segment-relative addressing(Angel/Mungi) 需大规模 compiler/toolchain 修改不现实；OS-as-a-process(Nephele/KylinX/Graphene) 重新引入多地址空间丧失 lightweightness；Iso-Unik 通过页表实现 fork 同样丧失 SASOS 优势；Junction/OSv 放弃 isolation。

## 关键洞察

1. **"μprocess = 同一地址空间内进程模拟，不是创建新 AS"**：父 μprocess 调用 fork→在同一虚拟地址空间中寻找足够大的空闲连续区域→复制父内存到新位置给子 μprocess。关键：不创建新页表→保留了 SASOS 的 zero-context-switch 优势。

2. **"CHERI capability——一个硬件机制同时解决两个正交挑战"**：(C1) 指针重定位——CHERI 的 1-bit validity tag（存在独立 tag memory 中，不可伪造）使 μFork 能精确识别哪些 16-byte slot 包含 capability→扫描整个页以 16-byte 粒度检查 tag→仅重定位真指针（整数被安全忽略）。这解决了 pointer tracking 这个 "hard problem [67]"。(C2) intra-AS 隔离——每个 capability 嵌 128-bit 含 bounds+permissions→硬件在解引用时 enforce bounds check→capability bounds 只能缩小不可扩大(monotonicity)→μprocess 不可能逃逸其内存区域。

3. **"CoPA (Copy-on-Pointer-Access) = fork 优化的第三维度"**：传统 CoW 仅复制 on write→SASOS fork 需要额外的 on pointer read 复制（因为子进程读包含指向父内存的指针页→必须先重定位才能安全使用）。µFork 定义三级共享策略：full copy（最重）→ CoA (Copy-on-Access，任何访问触发复制) → CoPA（仅 write 或 child load capability 时触发）。CoPA 通过 CHERI 的 **capability-load fault** 机制实现——页表额外 permission bit 使加载 capability 时精确 trap→非 capability load（普通数据读取）不触发→最大程度共享。对应 POSIX CoW 的语义——fork 后大部分页实际不会被修改。

4. **"Parameterized isolation = 适配不同威胁模型"**：fork 的三个使用模式有不同隔离需求：(U3) 特权分离(OpenSSH/qmail)→需要 adversarial fault isolation；(U2) 并发(Nginx)→仅需 non-adversarial fault isolation；(U4) CoW 快照(Redis)→可完全禁用隔离。μFork 允许 per-deployment 配置隔离级别→不支付不需要的安全开销。

5. **"Sealed capabilities = trapless syscall"**：传统 syscall 需要 costly trap→CHERI sealed capability 允许 μprocess 持有 sealed entry point→调用时硬件验证 capability 有效性→直接跳转到 kernel→消除 trap 开销（R1 compliant）。

- 来源：μFork(SOSP'25)

## 实践启发

- **"CHERI 不仅是安全检查——是 OS 构建块"**：capability tag→指针识别、capability bounds→intra-AS 隔离、sealed capability→fast syscall、capability-load fault→CoPA。四个 CHERI 特性分别解决 SASOS fork 的四个子问题。类似 InfiniDefrag "GPA 是虚拟的"——硬件能力的重新解释解锁全新 OS 设计
- **"CoPA 揭示 fork 优化的新维度——loading a pointer is semantically different from loading data"**：fork 优化从 CoW 的 read vs write 进化到 CoPA 的 data vs pointer × read vs write。Pointers 是特殊数据——应被区别对待
- **"SASOS + fork 在 fork-intensive 场景最有价值"**：FaaS Zygote warm-up +24%、Redis snapshot 1.4-1.9×、54μs fork→证明 lightweightness 优势在 fork-heavy workloads 上可转化为实际吞吐/延迟收益
- **"POSIX 兼容性不是可选项——是 OS 研究的 hard constraint"**：unmodified Redis/Nginx/MicroPython 零修改→研究系统必须兼容已有生态才有 adoption。类似 hS/Incr/LithOS "transparency is non-negotiable"
