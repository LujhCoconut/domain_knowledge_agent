# Ichnaea(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-haque.pdf
- **全称**: Ichnaea: A Framework for Precise Tracking of Memory Objects
- **作者**: Samad Haque, Sibin Mohan (GWU), Aaron Paulos, Partha Pal (RTX BBN Technologies)
- **类型**: 论文-系统 (内存追踪 + 安全分析)
- **一句话 TL;DR**: 基于 Intel MPK (Memory Protection Keys) 构建精准、无损的对象级内存追踪框架——追踪 "谁访问了什么对象、什么时候、做了什么修改"。相比 Intel Pin，追踪开销降低 **10-60×**，同时捕获完整的 per-access context (call stack, thread id, data diff)。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **MPK** (Memory Protection Keys) | Intel/AMD 硬件特性，允许每个 page 标记一个 4-bit key，用户态可快速切换 key 的权限 | Ichnaea 的底层硬件机制 |
| `pkey_mprotect()` / `pkey_set()` | 用户态系统调用和寄存器写：设置 page 的 key 值 / 修改当前线程的 key 权限 | 比 `mprotect()` 快 100-1000×（无 TLB shootdown） |
| **ObjOfInterest** | 用户通过编译期 annotation 声明的需要追踪的对象 | Ichnaea 保护的目标 |
| **Collateral fault** | 与 ObjOfInterest 同页但非 target 的变量触发的保护故障 | Ichnaea 的 nuance：handler 快速识别并跳过，不记录 |
| **Snapshot** | ObjOfInterest 每次被修改时记录的完整运行时上下文 | Ichnaea 的核心输出 |
| **Dormant mode** | Ichnaea 在无 ObjOfInterest 访问时的默认状态（零开销） | 与 Pin 的 always-on 对比 |

## 背景与动机

### 问题
追踪"谁访问了什么对象、什么时候"对调试、取证、并发分析至关重要，但现有方案有根本局限：

| 方法 | Precision | Overhead | 说明 |
|------|-----------|----------|------|
| Intel Pin / DynamoRIO | 精确 | **10-100× slowdown** | 每条指令都经过插桩 |
| Compile-time instrumentation | 中 | 中 | 静态分析无法解决 aliasing + 间接控制流 |
| `mprotect`-based | 粗糙 | 高 (per-page fault) | TLB shootdown + syscall → 数微秒每次 |
| Hardware watchpoints | 极精确 | 仅 4 个 registers | 无法扩展到多个对象 |

现代 C/C++ 软件（如 nginx 160KLoC）大量使用数据驱动的控制流——function pointers、callback tables、state-carrying objects → 需要 precise object-level tracing 但现有工具无法同时满足 precision + low overhead + scale。

### 为什么 MPK 是关键

`pkey_set()` 改变当前线程对特定 key pages 的访问权限只需**一个寄存器写指令**（user-mode，无 syscall，无 TLB shootdown），而 `mprotect()` 需要 syscall + page table walk + cross-core IPI TLB invalidation → **速度差 100-1000×**。

### 我的分析
这是 OSDI '26 中第三篇安全/分析方向的论文。与 USEC (MAC framework) 和 Mohabi (SFI sandbox) 不同，Ichnaea 是**动态分析工具**。其核心洞察是利用了 Intel MPK 的 user-mode fast permission change——这个特性在学术圈已知（用于 in-process isolation）但在**对象级 tracing**领域是新颖的应用。论文最打动人的数字是"比 Pin 快 10-60×"——这从一个"分析工具太慢没人用变成可以用在生产环境"的质变。

## 方案介绍

### 核心机制

**1. Dormant-by-default 模式**
- 默认状态：所有 MPK key pages 可正常访问（零开销）
- 当 ObjOfInterest 被锁定时：用 `pkey_set()` 快速切换当前线程对该对象 key 的权限为 deny

**2. Per-access 精确捕获**
- 当任何代码尝试读写 ObjOfInterest → **SIGSEGV**
- Ichnaea handler 捕获 SIGSEGV → 记录完整上下文：
  - call stack (who)
  - thread ID + process ID
  - read vs write
  - 如果是 write：记录修改前后的**数据 diff**
- 处理完毕后 unlock 该页（再次 `pkey_set()`），返回应用程序

**3. Low-overhead pagefault handling**
- 开发了优化的 SIGSEGV handler 路径（§5.6.2）
- Collateral faults 的处理：同页的非 target 变量触发保护 → handler 识别后快速跳过（不加 trace 记录），仅支付一次 handler enter-exit cycle
- 默认策略容忍 collateral faults 以保持低开销

**4. 编译期 Annotation 工具链**
- `ICHNAEA_ISOLATE_GLOBAL`：将全局对象对齐到独立 MPK-keyed page
- `ICHNAEA_MARK_PTR`：标记需要追踪的指针
- `ICHNAEA_MARK_ALLOC_CHK`：hook 自定义 allocator，自动追踪 heap 分配的 ObjOfInterest
- 以 nginx 为例的集成 (Listing 2)

**5. Syscall window 处理**
- 当 ObjOfInterest 被用作 syscall buffer（如 `read()`）时 → 内核写入会触发 fault
- Ichnaea 的 libc wrapper (Listing 3) 在 syscall 前临时 unlock 对应 pages，syscall 返回后重新 lock
- 保证 kernel writes 被观察而不破坏 I/O 行为

## 证据与评估

### 测试环境
- nginx, PostgreSQL, 其他 complex C applications
- Intel Pin baseline
- MPK-enabled hardware (Intel Skylake-X+)

### 关键结果

| 指标 | 结果 |
|------|------|
| vs Intel Pin | **10-60× lower overhead** |
| vs `mprotect`-based | orders of magnitude faster |
| Collateral fault overhead | minimal（handler 快速识别并跳过） |
| Context richness | call stack + tid + data diff + read/write |
| Static instrumentation 对比 | 无需 compile all access sites；aliasing/indirect-flow 自动覆盖 |

### Feature comparison (Table 7)

| Feature | Intel Pin | Ichnaea |
|---------|-----------|---------|
| Supports dynamic allocation | 需要额外配置 | ✅ |
| Startup overhead | 高 | 低 |
| Per-access data diff | ❌ | ✅ |
| Requires manual write site discovery | 否 | 否 |

## 整体评估

### 真正的新意
1. **MPK 在对象级内存追踪中的首次应用**: 利用 `pkey_set()` 的 user-mode speed 解决"trace 所有对象访问"的 scalability 问题
2. **"Dormant→active→dormant" tracing 模式**: 与 Pin/DynamoRIO 的"always on"形成根本差异
3. **Collateral fault 的 pragmatic 处理**: 不追求物理完美隔离（那需要 linker script 修改每个 ObjOfInterest），而是通过 handler 快速跳过——工程折中

### 优点
- **极低 overhead**: 10-60× faster than Pin → 使生产环境 tracing 成为可能
- **rich context**: data diff + call stack + thread id → 比简单的 access count 有用得多
- **annotation-based deployment**: 编译期 macro 集成，非侵入式
- **MPK 的利用是 natural fit**: user-space key permission change 是 MPK 的核心 value prop

### 局限
- **需要 MPK 硬件**: Intel Skylake-X+ / AMD Zen 3+ → 旧硬件不支持
- **最多 16 个 key**: MPK 只有 4 bits per page → 如果 ObjOfInterest 超过 16 个页面需要复用 key（可能增加 collateral faults）
- **Collateral faults**: 同页非 target 变量的访问也会触发 handler（虽快速跳过但仍有开销）→ 不如"完美隔离"精确
- **Syscall wrapper 的手动维护**: 每个 kernel interface 使用 ObjOfInterest buffer 都需要 wrapper（libc 函数多）

### 可复用启发

1. **"Dormant-by-default monitoring" 是最佳的低开销设计模式**: 不做任何 tracing 直到感兴趣的事件发生 → 适用于任何 monitoring/tracing 系统
2. **MPK 作为"cheap page-fault injector"**: `pkey_set()` 的微秒级延迟远低于 `mprotect()` 的毫秒级 → 适用于任何需要"temporarily guard memory regions"的场景
3. **Collateral fault 容忍策略**: 不追求完美 isolation，接受"同页其他变量也会 trigger fault" + handler 快速跳过 → 大幅降低 setup 复杂度
4. **per-access data diff 对调试/取证价值极高**: 知道"谁在什么时候修改了什么"比单纯的"这页被访问了"有价值得多
