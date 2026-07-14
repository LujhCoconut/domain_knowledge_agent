# TrainMover(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-lao.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 弹性+standby 机器替换故障节点——两阶段 delta 通信组重建+无通信 sandbox warmup+通用 standby 设计，中断恢复仅 ~20s（1024 GPU），预期减少 55% 浪费 GPU 小时（64K GPU 规模节省 140 万 GPU 小时/周）。

## 核心问题

大规模 LLM 训练被频繁中断——硬件故障、软件异常、管理事件（repair/patch/rebalance）。现有方案：(1) stop-reschedule-reinitialize → 小时级 downtime (2) reconfiguration → 可弹性替换机器但 joiner 的重新初始化（从 checkpoint）仍阻塞整体进度。关键：训练布局高度特化→乱改 layout 会触发 OOM 或性能退化。

## 关键洞察

1. **"Two-phase delta-based communication group setup"**：不完全重建 NCCL communicator→仅增量更新受影响的 group→大幅减少通信重建时间。
2. **"Communication-free sandboxed warmup"**：新 joiner 在通信隔离的 sandbox 中预热（加载模型、编译 kernel）→不阻塞已运行的训练→预热完成后再加入通信组。
3. **"General standby design"**：任意角色（TP/PP/DP）的机器都可被 standby 替换→不需要为每个角色维护专用备机池。

- 来源：TrainMover(OSDI'26)

### 实践启发
- **"Delta-based membership change > full reconfiguration"**：只更新受影响的部分而非重建全局→类似 NCCL 的增量 group 重建
- **"Sandbox warmup = 隔离预热 + 无缝加入"**：将准备工作和正在进行的训练分离→消除加入延迟
