# AEGIS(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-lei.pdf
- **类型**: 论文-运维系统
- **一句话 TL;DR**: ByteDance 的在线 GPU SDC 检测框架——cSensor-cVerifier 两阶段解耦 + 混合精度算法校验 + 自等价冗余检测，3500 万 GPU 小时中检测 18 次 SDC / 13 块缺陷 GPU，仅 0.86% 开销。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| cSensor-cVerifier | Sensor 在线轻量感知→离线可延迟验证的两阶段抽象 | 核心架构解耦——将 SDC 检测从 ad hoc detector 变成系统接口 |
| Mixed-precision checksum | 利用 GPU tensor core 的高精度累加（如 FP32 accumulate in FP16 matmul）做 checksum | 将 SDC 信号从浮点误差噪声中区分出来 |
| Self-equivalence | LLM 训练中天然存在的冗余计算——FlashAttention 反向重算前向中间值、activation recomputation | 零额外计算开销的 SDC 检测——比较两次执行结果 |
| Verification context | cSensor 捕获的最小化输入/输出 slice，供 cVerifier 重放验证 | 最小化在线开销——仅记录必要切片 |
| Pipeline bubble | 流水线并行的空闲间隙 | cVerifier 利用 bubble 执行重放验证，不增加训练时间 |
| Algorithmic detection (attention) | 利用 softmax 的行归一化性质：`sum(softmax(x)_i) = 1` | 低开销检测 attention 中的 SDC |
| Permanent SDC | 由 GPU 硬件缺陷导致的、在同一设备上复发 | 本研究关键发现——所有检测到的 SDC 都是 permanent（非 transient） |
| Non-deterministic SDC | 同一程序的 SDC 表现不固定 | 所有 observed SDC 都非确定——使诊断更难 |

## 背景与动机

SDC 在 LLM 训练中导致模型质量下降甚至失败（10K GPU 任务中可观测到梯度范数和 loss 尖峰），但：
- **罕见**：低概率硬件故障
- **静默**：NaN/inf 检测等框架报警会漏掉
- **低精度训练的挑战**：FP8/BF16 下 checksum mismatch 可能仅是正常浮点误差——无法区分 SDC 和 numerical noise

现有三类方案的不足：
- **离线诊断** (DCGMI)：中断训练，仅覆盖有限测试负载
- **重放验证** (SDCHUNTER approach)：强但需大量重复计算
- **算法在线检测** (ABFT)：FP8/BF16 下 checksum 不匹配被浮点误差主导→大量假阳性或代价高昂的误触发验证

## 核心方案：AEGIS

### cSensor-cVerifier 抽象

```
cSensor (online, critical path)
  → 轻量感知，记录 checksum + 最小验证上下文
  → 在状态被覆盖前发出验证任务

cVerifier (offline, pipeline bubbles)
  → 消费验证任务，重放+bitwise 确认
  → 利用 PP bubbles 执行（不增加训练时间）
```

### 两类检测方法

**1. 混合精度算法检测**

| 目标 | 方法 | 关键洞察 |
|------|------|----------|
| Matmul | 高精度累加 checksum（FP32 accumulate） | GPU tensor core 的高精度累加使 SDC 信号 >> 浮点误差 |
| Attention | 利用 softmax 行归一化：每行概率和 = 1 | 代数恒等式——低开销、独立于精度 |

cSensor 记录 checksums + 输入/输出 slice；cVerifier 重用重放+bitwise 比较。

**2. 自等价确定检测**

利用 LLM 训练中天然重复的计算：
- **Operator 级**：FlashAttention 反向重算前向中间值
- **Framework 级**：Activation recomputation（checkpointing）

cSensor 记录两份执行的紧凑指纹；cVerifier 交叉比对→不一致 = SDC。

### 关键发现（3500 万 GPU 小时）

1. **大多数 SDC 静默地破坏训练正确性**——框架 NaN/inf 检测未能报警
2. **所有 SDC 都是非确定的**——同一程序的相同输入下表现不同
3. **所有检测到的 SDC 都是 permanent**——源自 GPU 硬件缺陷，在同一设备上复发
4. 仅 **0.86%** 性能开销（~10K GPU 训练任务）

## 证据与评估

- **3500 万 GPU 小时**生产部署
- **18 次真实 SDC 事件** / **13 块缺陷 GPU**
- 部署后仅 1 次额外 SDC 通过其他方法被检测到（周期性任务重放）
- 0.86% 性能开销

## 与 SDCHUNTER 的关系

| | SDCHUNTER | AEGIS |
|------|-----------|-------|
| 目标 | **诊断**定位缺陷 GPU | **在线检测**发现 SDC |
| 触发方式 | 异常后诊断（reactive） | 训练中持续感知（proactive） |
| 方法 | 分层确定重放（Phase 1+2） | cSensor-cVerifier + 算法/自等价检测 |
| 同一团队 | ByteDance Seed | ByteDance Seed |

两个系统组合形成"检测→诊断"完整链路：AEGIS 在线发现 SDC→SDCHUNTER 定位缺陷 GPU。

## 可复用启发

- **"cSensor-cVerifier 解耦是异步验证的通用模式"**：将时间敏感的感知和代价高的确认分离——适用于任何"在线轻量+离线精确"的检测场景
- **"利用硬件高精度累加区分信号和噪声"**：GPU tensor core 的 FP32 accumulate 是 SDC 检测的免费午餐——浮点误差远小于 SDC 造成的偏差
- **"自等价是零成本的检测信号"**：activation recomputation 和 FlashAttention 反向重算本来就是必须要做的——只是比较两次结果而已
- 来源：AEGIS(OSDI'26)
