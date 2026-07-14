# LiteSwitch(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-li-nanqinqin.pdf
- **全称**: Harvesting Sub-Microsecond CXL Memory Stalls with LiteSwitch
- **作者**: Nanqinqin Li (Princeton), Yuhong Zhong, Asaf Cidon (Columbia), Michael J. Freedman (Princeton)
- **类型**: 论文-系统 (hardware-software co-design + CXL memory)
- **一句话 TL;DR**: CXL 内存延迟是本地 DRAM 的 3×~（200-400ns）→ 延长了已有的 CPU 内存停顿→ 浪费 CPU 周期。现有方案要么在 DRAM 延迟尺度（SMT）要么在 flash 尺度（interrupt-based blocking I/O）工作——**两者之间的 200ns-1µs "中间空白"无人覆盖**。LiteSwitch 用硬件精确识别 CXL stall + **20ns 超快软件线程切换**（比常规 context switch 快一个数量级），在不修改应用的前提下回收 CXL 延迟损失的 **80%** 性能。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **CXL memory stall** | CPU 因等待 CXL 内存（直接连接或 switched）返回数据而停顿的周期 |
| **Stall cycles harvesting** | 利用一个线程因等待内存/IO 而阻塞的间隙执行另一个线程的有用工作 |
| **Middle gap** | ~200ns 到 1µs 的延迟区间——SMT 太细粒度（掩盖 DRAM 延迟），interrupt 太粗粒度（掩盖 flash 延迟），中间无人覆盖 |
| **Hardware stall identification** | CPU 硬件机制精确识别"这个 stall 是 CXL 造成的"并以低开销暴露给软件 |
| **20ns software switch** | 比常规 context switch（微秒级）快两个数量级——仅抢救必要的寄存器状态 |

## 背景与动机

### 问题
- CXL 内存延迟（直接连接 ~200ns、switched ~400-600ns）是本地 DRAM 的 3× 或更多
- 内存密集型工作负载将 20-80% 的 CPU 周期浪费在 memory stalls 上
- CXL 的更高延迟**延长了每次 stall 数百纳秒**→ 将已有的低效放大
- SMT 掩盖了 DRAM 级别的延迟（~100ns），但对 CXL 延迟效果有限
- Interrupt-based blocking（如异步 I/O）开销太大（微秒级），无法回收亚微秒级 stall

### LiteSwitch 的定位
**200ns-1µs 之间的"中间空白"是未被覆盖的优化空间**。LiteSwitch 是专门针对 CXL 延迟时间尺度（亚微秒级）设计的 stall harvesting 机制。

## 方案介绍

### 两个核心机制

**1. 硬件精确识别 CXL stall**
- CPU 硬件机制精确区分"这个 stall 是由 CXL 访问引起的"（而不是计算延迟、cache miss 等）
- 以近乎完美的精度暴露给软件
- 最小化开销——不增加数据路径延迟

**2. 20ns ultra-fast software thread switch**
- 保存在 <20ns 内切换到另一个 ready thread 所需的最小上下文
- 仅挽救必要的寄存器状态——不执行完整的操作系统上下文切换
- 比传统上下文切换快**一个数量级**
- 当一个 thread 遇到 CXL stall 时 → 切换到一个 ready thread，时间尺度与 stall 本身匹配（200ns-1µs）

## 证据与评估

| 指标 | 结果 |
|------|------|
| CXL 性能损失回收 | **最高 80%** |
| 软件切换延迟 | **< 20ns** |
| 覆盖的延迟区间 | **> 200ns**（CXL 直接连接 + switched） |
| 应用修改 | **无需** |
| 前提 | 每个 core 有足够数量的可用线程 |

## 整体评估

### 真正的新意
1. **首次覆盖了 CXL 延迟特有的"中间空白"**：在 SMT 和异步 I/O 之间的亚微秒级 stall 回收区间首次被覆盖
2. **硬件-软件协同设计的分工**：硬件负责识别（精准+低开销）→ 软件负责切换（快速+精简）
3. **20ns switch 是新的性能边界**：证明在亚微秒级 stall 中切换线程是可行的

### 可复用启发
- "中间空白"是系统设计的一个重要概念：现有机制（SMT、interrupt、polling）各自覆盖了一个延迟区间，相邻区间之间可能存在缺口
- 硬件精确识别 + 软件快速执行的协同模式是处理亚微秒级事件的最佳分工
- CXL 的延迟挑战不仅关乎带宽和容量——如何在 CPU 层面回收被延长的 stall 周期是一个被忽视的问题

### 与知识库 CXL 论文的关系

| 已有 CXL 论文 | 层面 | LiteSwitch |
|-------------|------|-----------|
| TMO/PACT/CAMP/OBASE/MDK | 操作系统/后端：迁移/offload/回收策略 | **CPU 前端：亚微秒级 stall 回收** |
| RamRyder | 带宽/容量管理 | |
| MAC/NEMO/M5 | 可观测性与近存计算 | |

LiteSwitch 补全了 CXL 论文的一个视角：不仅是"如何管理 CXL 上的数据"，还包括"如何在 CPU 层面回收 CXL 延迟的代价"。
