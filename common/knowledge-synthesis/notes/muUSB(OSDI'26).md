# µUSB(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-zhang-xuankai.pdf
- **全称**: µUSB: Practical and Safe USB Driver Reuse for Arm TrustZone
- **作者**: Xuankai Zhang*, Sijin Li*, Pei Meng* (UESTC), Meng Wang (CISPA), Yongzhao Zhang, Ting Chen, Xiaosong Zhang, Liwei Guo (UESTC)
- **类型**: 论文-系统 (system security + driver reuse + program analysis)
- **一句话 TL;DR**: TrustZone 的 Secure I/O 缺乏 USB 外设支持——USB 是最多样化的外设类型（传感器、键鼠、摄像头、麦克风）。现有方案直接集成 USB 驱动到 TEE 不可行（协议复杂、高频 DMA、vendor 实现差异大）。µUSB 通过 **record → lift → replay**：从完整的复杂 USB 驱动的具体执行 trace 中**推导出功能性精简驱动**。基于 kernel specialization 和 USB FSM 的确定性，用轻量级 mutational recorder + 新颖的程序分析技术。首次使 in-TEE apps 可以访问 USB 设备。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **µUSB** (micro USB) | 从完整 USB driver 的执行 trace 中自动导出的精简、功能性 USB 驱动 |
| **Record → Lift → Replay** | µUSB 的三阶段流程：录制执行→提升为模板→在 TEE 中回放 |
| **Kernel specialization** | 核心洞察：Linux USB 驱动在具体硬件+工作负载下的执行路径是**高度可预测和可特化**的 |
| **Mutational recorder** | 轻量级录制器——记录 USB 驱动在具体硬件上的执行状态转移 |
| **USB FSM determinism** | USB 协议的状态机（FSM）是确定性的——给定相同的输入和设备状态，行为可预测 |
| **TrustZone** | ARM 的可信执行环境（TEE）——隔离安全敏感代码于普通 OS 之外 |

## 背景与动机

### 问题
- TrustZone 通过 Secure I/O 隔离设备访问以保护敏感数据
- 但 USB 外设**完全不被支持**——它们是最多样化的外设类别
- 现有方案无法实用：
  - 手动重写 USB 驱动到 TEE：USB 协议极度复杂（多设备类、vendors 实现差异大）
  - 直接运行完整 Linux USB 驱动在 TEE 中：TEE 的受限环境无法支持复杂的 Linux 驱动栈
  - DMA 高速交互 + TEE 隔离模型的冲突

### 核心洞察
> Linux USB 驱动在**具体硬件 + 具体工作负载**下的执行路径是可预测的。USB 协议的 FSM 确定性意味着给定设备状态，驱动行为可以被特化（specialize）为一个精简版本——去除了通用驱动中的所有冷路径和错误处理分支。

µUSB 不需要理解 USB 协议的所有复杂细节——只需要录制一次完整驱动在实际硬件上的执行，然后 "lift and replay"。

## 方案介绍

### Record → Lift → Replay

**1. Record**
- 在开发机器上运行完整 Linux USB 驱动
- Mutational recorder 以轻量级方式录制 USB 驱动在工作负载下的执行过程
- 关键：不是录制所有代码路径，而是录制**具体设备+工作负载**的路径

**2. Lift**
- 从录制的执行 trace 中静态分析提取核心逻辑
- 将通用驱动代码特化（specialize）到具体设备和操作
- 生成 "USB Driver Template"——足够小以放入 TEE 内部

**3. Replay**
- µUSB 在 TrustZone 内回放特化后的驱动模板
- 在 TEE 隔离环境中直接驱动 USB 设备
- 初次实现 in-TEE apps 对 USB 外设的访问

### 关键技术

- **Mutational recorder**：不录制所有指令，而是录制 FSM 的关键状态转移——降低录制开销
- **Program analysis for specialization**：静态分析执行 trace，识别出具体设备和操作所需的精确代码路径
- **In-vivo execution**：录制过程直接在实际硬件上运行——不需要设备模拟/仿真

## 整体评估

### 真正的新颖性

1. **首次通过执行 trace 推导 TEE 内可用驱动的方案**：不同于传统"手动重写"或"全量移植"的两种不可行方式
2. **Kernel specialization insight**：USB 驱动的大部分代码是通用框架和罕见错误处理——具体硬件+工作负载下实际需要的代码远少于完整驱动
3. **"Record → Lift → Replay"范式**：将"如何将复杂驱动移入 TEE"从 engineering problem 转化为 program analysis problem

### 可复用启发

- "Record → Lift → Replay"范式适用于任何"将复杂传统代码移入受限环境"的场景——不仅是 USB→TrustZone，还包括 蓝牙→TEE、网络驱动→SmartNIC
- "Kernel specialization"可以大幅降低复杂性：通用驱动中的大部分代码在实际场景中从不执行
- USB FSM 的确定性是驱动特化的关键：协议状态机可预测→录制一个覆盖路径就足够
