# μShell(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-chen-jiyang.pdf
- **类型**: 论文-系统/架构
- **一句话 TL;DR**: 将 microkernel 原则应用于 FPGA shell——加速器作为可组合、可共享的硬件模块部署到独立 vFPGA，通过动态 IPC 连接，capability 强制隔离 + 组件感知调度。

## 核心问题
现有 FPGA shell 为**单体应用**设计——所有模块静态连接为单个不可分的加速器在一个 vFPGA 上。但实际应用是模块化的、可组合的（93% 相关性因共享函数使用）。单体方法导致：灵活性差（改一个模块→重建整个加速器）、可扩展性受限、资源浪费、调度开销大。

## 关键洞察
1. **"Microkernel 原则应用于 FPGA——硬件模块 = 进程"**：加速器分解为可共享、可组合的硬件模块→部署到独立 vFPGA→通过硬件 IPC 动态连接。类似 OS 中 microkernel 将服务分解为独立进程。
2. **"Capability-enforced isolation"**：硬件模块间通过 capability 机制隔离——类似 OS 的 capability-based security。
3. **"Component-aware task scheduler"**：知道哪些模块被哪些应用使用→高效调度 vFPGA 资源。

- 来源：μShell(OSDI'26)
