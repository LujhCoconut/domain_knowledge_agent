# DPAS(FAST'26)

- **来源**: FAST '26, UC Irvine + Kookmin University (Dongjoo Seo, Yongsoo Joo, Nikil Dutt 等)
- **一句话 TL;DR**: SSD I/O completion 优化——**PAS** 用最近两次 I/O 的二值睡眠结果(UNDER/OVER)自适应调整 hybrid polling 睡眠时长, 替代 epoch-based 统计; **DPAS** 动态切换 polling/interrupts/PAS 三模式, CPU 使用 -21pp vs Linux hybrid polling, YCSB +9%(3D XPoint)/+5%(TLC NAND)。

## 核心问题

现有 hybrid polling 的三个根本缺陷:
1. **Epoch-based 无法即时响应延迟突变**——新延迟要等到下一 epoch 才反映
2. **无法区分设备延迟 vs oversleep 误差**——都归为"I/O 耗时", 导致错误持续
3. **Hybrid polling 不是 always best**——CPU 争用激烈时 interrupt 更好, 负载低时 polling 更好, 但没有运行时切换机制

## 方案设计

### PAS: Per-I/O Adaptive Sleep

- **不依赖 epoch 统计**——仅用最近两次 I/O 的二值结果(UNDER = 睡眠太短, OVER = 睡眠太长)
- **自纠正**: OVER → 缩短下次睡眠; 持续 UNDER → 延长睡眠(说明设备延迟确实在增加)
- 支持并发 I/O 和动态调整追踪灵敏度

### DPAS: Dynamic Mode Switching

运行时检测 CPU 争用 + timer 异常 → 在三种模式间切换:
- **Polling**: 低 CPU 争用, 追求最低延迟
- **Interrupts**: 高 CPU 争用, 避免 polling 浪费 CPU
- **PAS (Hybrid Polling)**: 中等争用, 平衡 CPU 和延迟

## 关键数据

| 指标 | vs Linux HP | 说明 |
|------|-----------|------|
| CPU 使用 | **-21pp** | 4KB random read |
| YCSB (3D XPoint) | **+9%** | CPU 争用+I/O 干扰同时存在 |
| YCSB (TLC NAND) | **+5%** | |

## 可复用启发

1. **"二值反馈替代统计——UNDER/OVER 的二元信号足够驱动自适应"**: 不需要测量精确 I/O 时间, 只需知道"睡对了没"。这是 control theory 的 error-based feedback 思想在 I/O 调度中的应用

2. **"No single completion method is best——动态切换是必要的"**: Polling/Hybrid/Interrupts 各自最优区域不重叠→contest-aware runtime switching > static choice

3. **"分离 oversleep error vs device slowdown = 正确归因"**: 混合两种信号→策略错误积累。区分后→oversleep→缩短睡眠, 设备慢→接受并调整

## 归档

已归档到 `performance/storage-filesystem/` (SSD I/O 优化)。
