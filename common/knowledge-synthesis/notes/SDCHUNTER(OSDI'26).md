# SDCHUNTER(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-zheng.pdf
- **类型**: 论文-运维系统 (Operational Systems)
- **一句话 TL;DR**: ByteDance 生产集群 GPU SDC（静默数据损坏）诊断系统——23 块缺陷 GPU 特征化 + 分两阶段分层重放诊断，40 次 SDC 事件中诊断时间从数天降至 1 小时内。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| SDC (Silent Data Corruption) | 无错误信号的意外数据更改——bit flip、计算错误、无 crash 无 DUE | GPU 最危险的故障模式——与软件 bug 无法区分 |
| SDC-defective GPU | 含有间歇性硬件缺陷、会反复在特定条件下产生 SDC 的 GPU | 根源是硬件、manifestation 是训练异常 |
| Crash / DUE | 程序崩溃（segfault）/ 检测到的不可恢复错误 | 有即时反馈——工程师可以定位。SDC 没有 |
| Homogeneous replay | 将 DP 维度拆分为两个逻辑 replica，输入完全相同，输出应为 bit-wise identical | Phase 1——快速定位异常到某个 parallel group |
| Full-state comparison | 对可疑 group + 健康 reference group 做确定性地重放、收集所有 layer-wise tensor signatures | Phase 2——精确定位到具体 GPU |
| Training determinism | 固定 RNG seeds + 确定性的 GPU kernel + 标准化通信顺序 | SDCHUNTER 的前提——否则跨 replica 对比无意义 |
| Synthetic microbenchmark miss rate | 标准的 DCGMI/GEMM stress test 漏检率 >60% | 本文的关键发现——通用 benchmark 无法检测 SDC GPU |
| DP group / PP boundary | Data Parallel 复制的模型副本 / Pipeline Parallel 的 stage 边界 | 分层诊断的空间维度 |

## 背景与动机

在数万 GPU 的 LLM 训练集群中，低概率硬件故障变得不可避免。Meta 报告 16,000 GPU 训练每 2.78 小时发生硬件故障（1.4% 为 GPU SDC），Google 观测到每 1-2 周一次 TPU SDC，ByteDance 三个月内记录 6,096 次隐式错误。

**SDC 的特殊危害**：与 crash/DUE 不同，SDC 不产生错误信号——表现为 "unexpected CUDA error"、"NaN in loss"、shape mismatch 等，与软件 bug 完全相同。**工程师通常花数天到数周调试代码，最终才发现是硬件问题。**

**行业标准方案失败**：DCGMI 等合成 stress test 漏检 >60%。

## 23 块 SDC 缺陷 GPU 的特征化发现

1. **SDC 不限于新硬件**——老化是更常见的原因，需要持续全生命周期监控
2. **SDC 高度数据依赖和计算单元特定**——通过通用 stress test 的 GPU 在特定训练输入下失败
3. **ECC 和热保护无法捕获**——这些是 logic-level bit flip，不是 memory error 或过热

## 核心方案：SDCHUNTER

### Phase 1: 轻量级分层定位（Homogeneous Replay）

- 沿 DP 维度拆分集群为两个逻辑 replica
- 注入相同的 input batch → 输出应为 bit-wise identical
- **仅在 PP 边界** hash tensors → 跨 DP 组对比 → 找到发散 stage
- 开销：**~3% runtime** + 几个额外训练步
- 结果：数小时内将异常定位到特定 parallel group

### Phase 2: 精确设备定位（Full-State Comparison）

- 在可疑 group + 健康 reference group 上确定性重放出问题的 iteration
- 收集所有中间 tensor 的 layer-wise signatures
- 通过差量分析找到第一个发散的 tensor 和 kernel
- 映射回缺陷 GPU
- 结果：1 小时内给出硬件可操作的决策

### 关键使能技术：Training Determinism

消除三类非确定性：
- 固定 RNG seeds
- 强制确定性 GPU kernel（禁用非确定性 cuDNN 算法）
- 标准化 AllReduce 中的通信/规约顺序

**代价**：step time 差异 <0.01%，debug 时间减少 70%。

## 证据与评估

- **部署规模**：ByteDance 生产环境，管理大规模 GPU 集群
- **已处理 40 次 SDC 事件**
- **诊断时间**：从数天降至 1 小时内
- **解耦恢复和诊断**：训练在 1 小时内恢复（隔离故障 stage 后），缺陷 GPU 定位和确认在 1 小时内完成（离线）

## 整体评估

### 真正的新意
1. **首次大规模生产 GPU SDC 特征化**：23 块真实缺陷 GPU 的分析，揭示 " benchmark 漏检 >60%"、"数据依赖"、"老化更常见" 三个关键发现
2. **训练确定性作为诊断基础**：以 <0.01% 代价获取 bit-wise determinism
3. **分层诊断**：先 DP 层面快速缩小范围（Phase 1），再精确到具体 device（Phase 2），平衡速度和精度

### 优点
- **生产验证**——40 次真实事件
- **解耦恢复和诊断**——训练不因诊断而长期中断
- **务实的方法**——不做全状态监控（太慢），也不只依赖合成 benchmark（漏检太多）

### 局限
- 依赖 DP 维度存在（非所有训练配置都有 DP）
- Deterministic kernel 对某些算子可能不支持
- 仅定位 GPU，不区分 CPU SDC vs GPU SDC（虽然后者是主要来源）

### 可复用启发
- **"生产数据的特征化"是可信系统研究的基础**：23 块真实缺陷 GPU 的分析远比"我们模拟了 SDC"有说服力
- **"解耦恢复和诊断"是 OSDI Operations 类论文的核心智慧**：不要求诊断定位到具体设备才开始恢复——先隔离到 group 恢复训练，离线再做精确定位
- **"确定性训练的代价极低但 debug 收益极高"**：<0.01% throughput loss → 70% debug time reduction——这笔交易在任何大规模训练集群上都值得
- 来源：SDCHUNTER(OSDI'26)
