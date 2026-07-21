# BeaconGNN(HPCA'24)

- **来源**: 2024 IEEE International Symposium on High-Performance Computer Architecture (HPCA)
- **作者**: Yuyue Wang (UCLA), Xiurui Pan (PKU), Yuda An (PKU), Jie Zhang† (PKU), Glenn Reinman† (UCLA)
- **URL**: https://web.cs.ucla.edu/~yuyue/assets/files/beaconGNN.pdf
- **一句话 TL;DR**: 在 SSD 的多级存储层次（die/channel/controller）上分别部署近数据处理引擎，配合 DirectGraph 格式支持乱序 GNN 邻域采样，将大规模 GNN 全流程卸载到 ULL flash 存储内执行，吞吐 11.6× SOTA ISC、能效 4× 提升。
- **资料类型**: 论文-系统（HPCA'24）

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| ISC (In-Storage Computing) | 利用 SSD 内嵌处理器/FPGA/ASIC 直接在存储内部处理数据 | 核心方法——将 GNN 数据准备+计算卸载到 SSD |
| ULL Flash (Ultra-Low Latency Flash) | 读延迟仅 3µs 的新型闪存（如 Samsung Z-NAND） | 关键硬件使能——传统 NAND ~100µs，ULL 使 NDP 在 flash die 成为可能 |
| DirectGraph | 将 flash 物理地址直接嵌入图结构的数据格式 | 消除 LBA→PPA 地址翻译，支持乱序跨 hop 采样 |
| Neighbor Sampling | GNN 训练中从目标节点出发按 hop 随机采样邻居 | GNN 数据准备阶段的核心操作 |
| GNN Message Passing | 多层汇聚邻居 embedding 更新节点表示 | GNN 计算阶段，适合加速器并行 |
| ONFI | Open NAND Flash Interface，闪存芯片通信标准 | BeaconGNN 扩展 ONFI 命令支持 die-level 采样 |
| Spatial Accelerator | 由 1D vector array + 2D systolic array 组成的加速器 | 挂在 SSD 内部总线上执行 GNN 聚合+GEMM |

## 背景与动机

### GNN 任务的 I/O 瓶颈

GNN 任务分两阶段：
1. **数据准备**：多跳邻域采样 → 从 feature table 取特征向量
2. **GNN 计算**：K 层 message passing（聚合+更新）

工业级图数据（如推荐系统）可达 TB 级，超出单机内存，只能放在 SSD 中。数据准备阶段产生大量 host↔SSD PCIe 传输，成为瓶颈。

### 现有 ISC 方案的三重局限

| 挑战 | 根因 | 影响 |
|------|------|------|
| **Challenge 1: Hop-by-hop 串行屏障** | 每跳采样完成后需 host 做地址翻译（node id→LBA→PPA）才能开始下一跳 | flash die 大量空闲等待，利用低 |
| **Challenge 2: Page-granular 通道传输浪费** | GNN 采样/特征检索只用到 page 中少量数据，但整个 4KB page 都要通过 channel 传输 | 增加活跃 die 从 1→8 仅 49% 吞吐提升，却 7.7× 延迟 |
| **Challenge 3: Firmware 调度的处理瓶颈** | 嵌入式核 poll flash 状态+管理请求队列+DMA 数据传输→处理能力跟不上 flash I/O 速度 | backend I/O throughput 受限于弱核 |

**我的分析**: 三个挑战的层次不同——C1 是软件协议层（地址翻译层级太多），C2 是数据传输粒度层（page 粒度 vs 有用数据粒度），C3 是硬件调度层（嵌入式核 vs 专用逻辑）。这个分层分类是有价值的——说明需要多层次协同解决。

## 问题定义

**要解决什么**: 将大规模 GNN 的全流程（邻域采样+特征检索+embedding 计算）高效卸载到 SSD 内部执行，消除 PCIe 传输瓶颈，并充分利用 ULL flash 的低延迟特性。

**现有工作为什么不够**:
- GList (ATC'21): 只卸载 feature table 操作，不处理 graph structure
- SmartSage (ISCA'22): 只卸载 neighbor sampling，不处理 feature table
- 两者都不是全流程卸载，且都基于传统高延迟 SSD 设计，无法适配 ULL flash

## 方案介绍

### 方案概述

BeaconGNN 采用**软件-硬件协同设计**，核心包含四个组件：

```
Host (minimal)                SSD
┌──────────┐     ┌─────────────────────────────────────┐
│ GNN App  │     │  Firmware (GNN Engine)              │
│ metadata │     │  ┌──────────┐    ┌───────────────┐  │
│ + targets│────▶│  │Spatial   │◀───│ SSD DRAM      │  │
└──────────┘     │  │Accel.    │    │ (buffer)      │  │
                 │  └──────────┘    └───────┬───────┘  │
                 │                          │          │
                 │  ┌───────────────────────┴───────┐  │
                 │  │ Flash Interface Controller    │  │
                 │  │  ┌─────────────────────────┐  │  │
                 │  │  │ Channel-level Router    │  │  │
                 │  │  │ (parse+route commands)  │  │  │
                 │  │  └───────┬─────────────────┘  │  │
                 │  │          │                     │  │
                 │  └──────────┼─────────────────────┘  │
                 │     ┌───────┴──────────┐             │
                 │     │   Channel 1..N   │             │
                 │     │ ┌──┐ ┌──┐  ┌──┐ │             │
                 │     │ │D0│ │D1│..│Dn│ │             │
                 │     │ │S │ │S │  │S │ │ ← Die-level │
                 │     │ └──┘ └──┘  └──┘ │   Samplers  │
                 │     └─────────────────┘             │
                 └─────────────────────────────────────┘
```

### 关键模块

#### 1. DirectGraph 数据格式

**核心思想**: 将 flash 物理地址直接嵌入图数据中，消除 node id→LBA→PPA 的多级地址翻译。

- 每个节点存一个 primary section（含 feature vector + neighbor list），放不下时扩展 secondary section
- 低度节点多个 primary section 压缩到同一 page
- Neighbor index → 4 字节物理地址（28-bit page + 4-bit section offset）
- 物理块 level 的 bitmap（N_block bits）管理，绕过 FTL

**消除地址翻译的效果**: host 只提供目标节点的 primary section 地址 → 后续所有寻址在 SSD 内部完成，不需要 host 参与。

#### 2. Die-level Sampler

在 flash die 的控制电路（data register / cache register 之间）增加采样逻辑：
- **Section Iterator**: 遍历 page 找到目标 section
- **Vector Retriever**: 将 feature vector 从 cache register 传到 data register
- **Node Sampler**: 用 TRNG (True Random Number Generator) 模运算随机采样邻居
- **Command Generator**: 为采样到的邻居生成新的采样命令（下一跳）

**关键**: 采样后的输出是**新的采样命令 + feature vectors**，而不是整个 page。这直接解决了 Challenge 2（page-granular 传输浪费）。

#### 3. Channel-level Command Router

在 flash interface controller 中增加：
- **Dispatch Queues**: 每个 channel 为每个 die 各维护一个命令队列
- **Round-robin Command Issuer**: 检测 die idle → 自动发命令
- **Data Stream Parser**: 从 channel bus 上解析采样结果流→分类为"新采样命令"和"特征向量"
- **Crossbar**: 将采样命令路由到目标 channel

**关键**: 这消除了 firmware 在数据准备路径上的参与（Challenge 3），实现硬件自动化 flash I/O 处理。

#### 4. Bus-attached Spatial Accelerator

挂在 SSD 内部总线上的专用加速器：
- **1D vector array**: 特征聚合
- **2D systolic array**: GEMM-based 特征更新
- **Shared SRAM buffer**: 灵活支持不同数据分区

### 系统支持

- **Firmware GNN Engine**: 将当前 mini-batch 的数据准备与上一 batch 的计算流水线化
- **DirectGraph 构造**: 两阶段——(1) mapping-based metadata collection（计算每 section 空间需求）→ (2) 序列化写入 SSD（host buffer 构造 page → flush）
- **安全隔离**: DirectGraph block 在 FTL 中标记不可用；采样命令写入地址被 firmware 验证；die-level section header 检查
- **可靠性**: SLC Z-NAND 极低 RBER + data scrubbing + wear leveling（P/E 偏差超阈值时迁移 DirectGraph）
- **ONFI 扩展**: 新增两个命令——全局 GNN 配置、采样操作

## 证据与评估

### 测试环境

- **模拟器**: Python 事件驱动周期精确模拟器（参考 SimpleSSD + MQSim）
- **加速器建模**: ScaleSim-2.0 (systolic array)
- **面积/功耗**: Verilog 综合 (openPDK 40nm) + McPAT + CACTI-7.0
- **SSD 配置**: 4 ARM Cortex-A9, PCIe 4.0 ×4, DDR4-3200 1GB, 16ch×4die×2plane, 4KB page, ULL flash 3µs read
- **数据集**: Reddit (37M nodes), Amazon (266M), Movielens (22M), OGBN (179M), PPI (9M) — 均按 SmartSage 方法 scale up
- **GNN 模型**: 3-hop subgraph, 3 neighbors/hop, vector sum aggregation, 128-dim FP16

### 对比系统

| 系统 | 描述 |
|------|------|
| CC (CPU-centric) | Host CPU 采样 + 独立 DNN 加速器，PCIe 传输 |
| SmartSage | 仅 offload neighbor sampling |
| GList | 仅 offload feature table 操作 |
| BG-1 (BeaconGNN-1.0) | SmartSage + GList 组合，无进一步优化 |
| BG-DG | BG-1 + DirectGraph |
| BG-SP | BG-1 + die-level sampler |
| BG-DGSP | BG-1 + DirectGraph + die-level sampler |
| BG-2 (BeaconGNN-2.0) | BG-DGSP + channel-level router（完整设计）|

### 主要实验结果

#### 吞吐 (Figure 14)

- SmartSage: 2.11× CC (average)
- GList: 1.42× CC
- BG-1 (组合): 2.35× CC — 简单组合收益不大
- BG-DG: marginal over BG-1 — **page 传输高延迟压制了 out-of-order 的收益**
- BG-SP: **5.47× over BG-1** — die-level sampling 是最大单因子贡献
- BG-DGSP: 20% over BG-SP — out-of-order 在有 SP 后才能发挥
- BG-2: 41% over BG-DGSP, **21.70× CC overall**

**数据解读**: 优化的顺序很重要——先消除 page-granular 传输瓶颈（SP），再叠加乱序采样（DG），最后消除 firmware 处理瓶颈（router）。每个后续优化在前一个优化释放瓶颈后才有效果。

#### Flash 资源利用率 (Figure 15)

- BG-SP: 三个显著的低利用率谷值（对应 hop 间 barrier）
- BG-DGSP: 谷值消失，但总体利用率仍低（vs 总资源）
- BG-2: channel/die 利用率 +76%，采样延迟 -78%

#### Command 延迟分解 (Figure 17)

- BG-1/BG-DG: `wait_before_flash` + `wait_after_flash` 占 command 生命周期的绝大部分
- BG-SP/BG-DGSP: 等待时间显著减少，但因 ready commands 增加→`wait_before_flash` 积累
- BG-2: wait time -68% vs BG-DGSP

#### Sensitivity 分析 (Figure 18)

关键发现：
- **Batch size**: BG-2 扩展性最好，无穷趋近（测试范围 32-256 内无明显饱和）
- **Channel bandwidth**: BG-2 在 >800 MB/s 后 plateau（flash die 吞吐饱和）
- **Core count (1→8)**: BG-2 完全不受影响（firmware 已从 data path 移除）
- **Channel count (4→32)**: BG-2 在 16ch 后线性扩展停止（DRAM bandwidth 成为瓶颈）
- **Die/channel (2→16)**: BG-2 在 16 die/channel 后 plateau（channel bandwidth 饱和）
- **Page size (2KB→16KB)**: BG-2 基本不敏感

**数据解读**: BG-2 的瓶颈从 "firmware 处理" 转移到 "物理资源（DRAM BW / channel BW / die 数）"——说明软件/固件 overhead 已被有效消除。

#### 能效 (Figure 19)

- CC: 57% 能量消耗在 PCIe 传输
- BG-1/BG-DG: 75% 能量消耗在 DRAM 间的 page 传输
- BG-2: 4.25× BG-1 能效, 9.86× CC 能效
- 总功耗 13.4W（远低于 PCIe 75W 限制）

#### 传统 SSD (20µs read latency)

- BG-2 vs BG-DGSP: 几乎无差别
- 说明：传统高延迟 SSD 下 firmware 处理能力足够，channel-level router 不需要

**数据解读**: ULL flash 是使得 firmware 成为瓶颈的必要条件——新技术 (ULL) 创造了新的瓶颈 (firmware)，进而创造了新优化的机会 (channel router)。

### DirectGraph 存储膨胀

| Dataset | Raw size (GB) | Inflate ratio |
|---------|--------------|---------------|
| reddit | 242.6 | 2.8% |
| amazon | 397.2 | 4.1% |
| movielens | 221.8 | 3.5% |
| OGBN | 30.02 | 32.3% |
| PPI | 37.1 | 3.5% |

OGBN 膨胀大→低平均度(28)→section 短→page 内空余多。但大规模图的 Densification law →平均度随节点数增长 → 大型图空间浪费小。

## 整体评估

### 真正的新意

1. **多层次 NDP 的分工设计**: die-level (数据减少) / channel-level (控制自动化) / controller-level (计算) ——每一层承担不同角色，不是简单堆叠
2. **DirectGraph 消除地址翻译**: 物理地址嵌入图的 idea 虽然简单，但打破了 GNN ISC 中的核心约束（hop-by-hop 串行），是一个关键的"解除约束"型设计
3. **ULL flash 改变了瓶颈结构**: 传统 SSD 下 firmware 不是瓶颈 → ULL 下 firmware 成为瓶颈 → channel router 才有价值。这个"新技术→新瓶颈→新优化"的逻辑链是完整的

### 优点

- **清晰的挑战→方案对应**: 三个 challenge → 三个解决方案(DirectGraph/Die Sampler/Channel Router)
- **消融实验充分**: 从 BG-1 → BG-DG → BG-SP → BG-DGSP → BG-2 的渐进式对比
- **Sensitivity 分析全面**: 覆盖 batch size/channel BW/core count/channel count/die count/page size
- **传统 SSD 对比**: 证明 BG-2 的部分优化是 ULL-specific 的

### 缺点

- **模拟而非真实硬件**: 全 Python cycle-accurate 模拟器，无 FPGA/ASIC 原型验证
- **GNN 模型简单**: 只用 vector sum aggregation + single perception layer，未测试复杂模型 (GAT/GIN/GraphSAGE 多变体)
- **数据集局限**: 全部来自 PyTorch Geometric + scale-up，无真实工业图数据
- **功耗估算基于 synthesis**: 只有 die-level/channel-level 逻辑有 Verilog 综合，accelerator 用 analytical model
- **单 SSD 限制**: 未评估多 SSD 扩展场景（Discussion 中提到但未实验）

### 局限与假设

- **图静态假设**: DirectGraph 依赖"GNN 数据长期不变"的假设——频繁更新的图需要重新构造 DirectGraph
- **ULL flash 依赖**: 部分优化 (channel router) 仅在 ULL 下有效
- **SLC Z-NAND 特殊性**: 可靠性假设依赖 SLC 极低 RBER

### 适用条件

- 图数据 > 单机内存 (百 GB–TB 级)
- 图数据相对静态（更新频次低）
- 使用 ULL flash 的 SSD（如 Samsung Z-NAND / Kioxia XL-FLASH）
- GNN 使用 mini-batch + neighbor sampling 训练方式

### 可复用启发

1. **"多级 NDP = 多级瓶颈消除"**: 不是在一处做大 NDP，而是在每一级做最合适的——die 做数据局部减少（采样）、channel 做控制自动化（路由）、controller 做计算卸载（聚合）
2. **"消除约束比加速操作更重要"**: DirectGraph 打破了 hop-by-hop 串行的约束——其价值不在于让单跳采样更快，而在于允许跨跳并行
3. **"新技术→新瓶颈→新优化机会"**: ULL flash 将瓶颈从 "flash read" 转移到 "firmware process"，创造了 channel router 的机会
4. **"Microarchitecture 优化要考虑物理约束"**: Die sampler 面积 <0.1% die area, channel router 1.26% controller area——用极小的硬件代价换取大幅提升
5. **"Page-granular 通道传输是 flash ISC 的隐藏瓶颈"**: 之前 ISC 工作关注 compute offload，但忽略了"数据从 flash 到 controller 的传输效率"

### Discussion 中值得关注的扩展方向

- **Flash-to-accelerator direct I/O**: 当前架构中 flash data → DRAM → accelerator，DRAM BW 成为瓶颈
- **Computational storage arrays**: 多 BeaconGNN SSD 通过 P2P 互联协同
- **GNN query (inference)**: 小 batch 推理延迟优化——host-SSD 通信一轮即可完成

## R4 对抗审视 (简版)

- **最脆弱的 claim**: "up to 11.6× throughput"——这是 vs BG-1（naive组合），而非 vs 最优 baseline。vs CC 是 21.7×，但 CC 是故意设计的弱 baseline
- **实验遗漏**: 无复杂 GNN 模型测试 (GAT with attention、heterogeneous GNN)、无动态图更新场景、无多 SSD 实验
- **过度声明风险**: "Large-Scale" 在标题中——但最大数据集 Amazon 仅 397GB，实际工业级图可达数十 TB
- **假设敏感性**: 如果图不是静态的（DirectGraph 构造开销不可忽略），BG-2 的优势会大打折扣
- **整体可信度**: medium——设计空间探索扎实，但缺乏真实硬件验证
