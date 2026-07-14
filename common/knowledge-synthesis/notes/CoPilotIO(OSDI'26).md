# CoPilotIO(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-chen-guanyi.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: CPU 作为 GPU I/O 的副驾驶——split SQ/CQ 架构+硬件 barrier 同步+自适应 CPU-GPU co-polling，I/O 停顿 -55.5%，SM 需求 -50%，应用性能 up to +85%。

## 核心问题

GPU-centric I/O (BaM) 提供高吞吐和 on-demand 访问，但 GPU 需要持续轮询 NVMe completion queue → 三种 stall (intra-warp/inter-warp/inter-SM) → GPU compute 可用性 -87%。CPU-centric I/O (GDS) 不消耗 GPU 但性能低且无法 on-demand。

## 方案

GPU 发起 I/O + CPU 轮询完成队列：

1. **Split SQ/CQ**：Submission Queue 在 GPU 侧（直接发起 I/O），Completion Queue 映射到 CPU 侧（CPU 轮询完成）
2. **Hardware barrier-based synchronization**：GPU→CPU 的完成通知不走 kernel，用 PCIe barrier 直接同步
3. **Lock-free barrier-table**：低开销的多个 I/O 的完成跟踪
4. **CQ-based adaptive co-polling**：高 I/O 负载时 CPU 主导轮询，低负载时 GPU 自行轮询（减少跨 PCIe 通信）

## 可复用启发
- **"Split SQ/CQ"打破 all-GPU or all-CPU 的二分**：GPU 最适合发起 I/O（低延迟），CPU 最适合轮询完成（不浪费 GPU compute）
- 来源：CoPilotIO(OSDI'26)
