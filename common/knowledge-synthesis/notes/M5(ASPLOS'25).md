# M5(ASPLOS'25)

- **来源**: ASPLOS '25, DOI: 10.1145/3676641.3711999
- **年份**: 2025
- **作者**: Yan Sun, Jongyul Kim, Zeduo Yu, Jiyuan Zhang, Siyuan Chai (UIUC), Michael Jaemin Kim, Hwayong Nam, Jaehyun Park, Eojin Na, Jung Ho Ahn (SNU), Yifan Yuan, Ren Wang (Intel Labs), Tianyin Xu, Nam Sung Kim (UIUC)
- **类型**: 论文-系统 (硬件/软件协同设计)
- **开源**: https://github.com/ece-fast-lab/ASPLOS-2025-M5
- **一句话 TL;DR**: 将 hot-page/hot-word 追踪器嵌入 CXL 内存控制器硬件，消除 CPU 侧 profiling 开销和观察盲区，发现 CPU 驱动方案常把 warm page 误判为 hot page、且许多应用存在"稀疏热页"（仅少量 64B word 真正被频繁访问），M5 识别出 47% 更热的页面，带来 14% 更高性能。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **HPT** (Hot-Page Tracker) | 位于 CXL 控制器的硬件模块，跟踪 top-K 最热 4KB 页面 | 替代 CPU 侧 PEBS/PTE scan 等 hot page 识别 |
| **HWT** (Hot-Word Tracker) | 位于 CXL 控制器的硬件模块，跟踪 top-K 最热 64B word | 解决"稀疏热页"问题——整页迁移但仅少量 cache line 真正热 |
| **M5-Manager** | 用户态软件接口 | 组合 HPT/HWT 输出与多样化迁移策略 |
| **Sparse Hot Pages** | 页面内仅少量 64B word 被频繁访问，其余冷数据占空间 | M5 核心发现之一，导致 read amplification |
| **Read Amplification** | 将整个 4KB 页面迁移到快 tier，但只用到其中少量 bytes | 传统页迁移的浪费来源 |
| **CXL Controller** | Type 2/3 CXL 设备上的内存控制器 | M5 追踪器的运行位置（near-memory，非 host CPU） |
| **Top-K tracking** | 硬件维护 top-K 最热条目（类似 priority heap） | HPT/HWT 的核心数据结构 |

## 背景与动机

### 问题
- CXL DRAM 延迟是本地 DDR 的 2-3×，形成天然的 tiered memory
- CPU 驱动的页面迁移方案（PEBS 采样、PTE access bit 扫描、频次统计）有根本局限

### 作者的核心发现（使用 CXL 控制器侧精确 profiling）

**发现 1: Warm pages 被误判为 hot pages**
- CPU 侧观测受限于采样精度和可见性，常把中等热度页面当作热页迁移
- 浪费 fast-tier 空间和迁移带宽

**发现 2: 稀疏热页 (Sparse Hot Pages)**
- 许多应用（尤其 DLRM 推荐模型）中，一个 4KB "热页"内可能只有几个 64B embedding vector 真正被频繁访问
- 传统方案迁移整个 4KB 页面 → read amplification（冷数据占用 fast-tier 空间）

**发现 3: CPU profiling 的开销可能高于收益**
- PEBS 采样、PTE scanning、page fault handling 的 CPU 开销可能超过迁移带来的性能提升

### 我的分析
这是三篇 tiered memory 论文中最"硬件向"的一篇。TMO 是纯软件 + 现有内核接口，PACT 用标准 PMU 计数器做软件建模，而 M5 的方案要求修改 CXL 控制器硬件。这既是优点（精确度最高、零 CPU 开销），也是局限（需要新硬件支持）。它和 PACT 的 per-word 理想是互补的——PACT 想通过软件做到 per-page criticality，而 M5 通过硬件达到了 per-word 精度。

## 方案介绍

### 整体架构

```
Host CPU                    CXL Device
┌──────────┐               ┌─────────────────┐
│  App     │               │ CXL Controller  │
│  ↓       │    CXL.mem    │  ┌─────┐ ┌─────┐│
│  OS/Mgr  │←─────────────→│  │ HPT │ │ HWT ││←── CXL DRAM
│          │               │  └─────┘ └─────┘│
│ M5-Mgr   │               │  (in-hardware    │
│  (SW)    │               │   top-K trackers)│
└──────────┘               └─────────────────┘
```

### 关键创新 1: CXL Controller 侧精确 Profiling

**位置选择**: 追踪器放在 **CXL 内存控制器**内（非 host CPU 侧），优势：
- 可以精确计数每次 4KB 页和 64B word 的访问（无采样误差）
- 零 CPU 开销（host CPU 不参与 profiling）
- 透明（应用和 OS 无需修改）

**Counter 粒度**: 每个 4KB 页和每个 64B word 都有独立的访问计数器

### 关键创新 2: Hot-Page Tracker (HPT)

- **功能**: 维护 top-K 最热 4KB 页面的排序列表
- **实现**: 硬件 priority structure（类似 heap 或 sorted list）
- **输出**: 实时暴露给 M5-Manager，用于驱动页迁移决策
- **优势 vs CPU 方案**:
  - 精确计数（非采样，无 statistical bias）
  - 区分 truly hot vs warm（精确对比度优于 CPU 侧粗粒度采样）
  - 零 CPU overhead

### 关键创新 3: Hot-Word Tracker (HWT)

- **功能**: 维护 top-K 最热 64B words 的排序列表
- **核心用途**: 识别稀疏热页中的真正热数据
- **典型场景**: DLRM embedding tables —— 每个 4KB page 可能包含数十个 64B embedding vectors，但仅 2-3 个被频繁查询
- **使能的新型策略**:
  - Cache-line 粒度迁移（只迁移热的 64B）
  - 部分页面 pinning（热 word 在 fast tier，冷 word 在 slow tier）
  - 更智能的 promotion 决策（避免迁移"假热页"）

### 关键创新 4: M5-Manager

- **用户态软件层**，提供 API 组合 HPT 和 HWT 输出
- 支持灵活的策略编程：用户/OS 可以定义自己的迁移策略
- 即使使用简单策略（如"HPT top-K → promote"），也已超越最佳 CPU 驱动方案

## 证据与评估

### 测试环境
- 真实 CXL-ready 系统和设备（基于团队先前 MICRO'23 工作："Demystifying CXL Memory with Genuine CXL-Ready Systems and Devices"）
- CXL DRAM 延迟为本地 DDR 的 2-3×

### 关键结果

| 指标 | 结果 | 说明 |
|------|------|------|
| Hotter pages identified | **47%** vs best CPU-driven | HPT 精度远超 PEBS/PTE-based 方案 |
| Performance improvement | **14%** (talk: 17%) | 使用简单的 promotion 策略即可达成 |
| CPU profiling overhead | **消除** | 全部 offload 到 CXL controller |
| Read amplification | 显著减少 | HWT 识别稀疏热页，避免迁移整页中的冷数据 |

### Workload 覆盖
- 图分析（graph analytics）
- 推荐模型（DLRM，稀疏 embedding table 访问）
- In-memory 数据库（Redis）
- 通用 tiered-memory benchmark

### 与 CPU 驱动方案的对比

| 维度 | CPU-driven (PEBS/PTE) | M5 (CXL Controller) |
|------|----------------------|---------------------|
| 计数精度 | 采样（1:N） | 精确（每次访问） |
| CPU 开销 | 有（PEBS 中断、PTE scan） | 零 |
| 粒度 | 4KB page only | 4KB page + 64B word |
| 可观测 warm vs hot | 弱（粗粒度采样混淆） | 强（精确计数区分） |
| 需要硬件改动 | 否 | 是（CXL controller） |

## 整体评估

### 真正的新意
1. **首次将 per-page + per-word 访问追踪放入 CXL controller 硬件**，消除 CPU profiling 的"观察者效应"
2. **揭示"稀疏热页"问题**——per-word 追踪发现许多 4KB 热页内部只有少量 cache line 真正热，这改变了"页迁移"的基本前提
3. **Hardware/software co-design** 方式：HPT/HWT 做 tracking + M5-Manager 做 policy，分工清晰

### 优点
- 精确度最高（硬件计数无采样误差）
- 消除 profiling 开销（host CPU 零负担）
- 开放了新的策略空间（word 粒度迁移、partial page promotion）
- 开源 artifacts

### 局限
1. **需要硬件改动**: CXL controller 需要集成 HPT/HWT，无法在现有硬件上部署。虽然 CXL 控制器通常用 FPGA/ASIC 实现且可更新，但这仍是 adoption barrier
2. **Top-K 的 K 值选择**: K 决定了 tracker 的 SRAM/register 预算，根据 workload 可能需要调优
3. **仅适用于 CXL-attached memory**: 对于 NUMA、PMEM 等其他 tiered memory 场景不适用
4. **没有讨论功率/面积开销的具体数字**: 公开摘要中未给出 HPT/HWT 的 gate count、SRAM、功耗等硬件开销数据（可能在付费完整论文中有）
5. **M5-Manager 的用户编程复杂度**: 提供了灵活性但也增加了策略设计的责任

### 与 TMO(ASPLOS'22) 和 PACT(ASPLOS'26) 的对比

| 维度 | TMO(ASPLOS'22) | PACT(ASPLOS'26) | M5(ASPLOS'25) |
|------|---------------|-----------------|---------------|
| **方法** | 纯软件 | 软件 + 标准 PMU | 硬件(CXL controller) + 软件 |
| **反馈信号** | PSI (% stall) | PAC (cycles/page) | HPT/HWT (精确访问计数) |
| **粒度** | cgroup | page (4KB/2MB) | page (4KB) + word (64B) |
| **CPU 开销** | 0.05% cycles | PEBS 采样开销 | 零（全部 offload） |
| **可部署性** | 即插即用（Linux 主线） | 需要 Intel PMU | 需要新硬件 |
| **核心洞察** | 直接测生产力损失 | hotness ≠ criticality | CPU 侧观测有精度瓶颈 |
| **部署规模** | Meta 数百万台 | CloudLab 实验 | 实验环境 |

**三篇论文的演进脉络**:
1. **TMO**: "不要猜，直接测"（PSI 测 lost work）
2. **PACT**: "不要数频率，算代价"（PAC 测 per-page stall）
3. **M5**: "不要在 CPU 侧测，到内存控制器里测"（CXL controller tracking）

### 可复用启发

1. **"测量点靠近数据源"原则**: M5 将 tracking 放在 CXL controller 而非 host CPU，消除了观察开销和采样误差。这个原则可推广到其他系统设计——分布式 tracing 应该在数据流经的关键路径上做，而非事后从日志推断

2. **"稀疏热"是普遍现象**: 不仅是 DLRM embedding，数据库索引页、图存储的邻接表、KV cache 等场景下都可能存在"页内仅少量数据热"。这挑战了"page 是迁移的自然粒度"这一默认假设

3. **Top-K 硬件追踪器 vs 软件采样**: 如果应用场景对 hotness 精度要求极高且 overhead 敏感，硬件 top-K tracker 是比软件采样更优的选择——不仅更准，而且消除了统计偏差

4. **HWT 的 word 粒度 insight 可能通过软件近似**: 虽然 M5 用硬件实现 word 粒度追踪，但 Sapphire Rapids 的 PEBS per-load latency 也可以提供一定程度的指令级/地址级可见性——PACT(ASPLOS'26) §4.3.7 提到过这个方向

5. **硬件/软件协同设计的分工模式**: HPT/HWT 做数据收集（hardware excels at repetitive counting），M5-Manager 做策略决策（software excels at flexible policy）。这个分工模式可推广到其他系统设计

6. **M5 验证了 PACT 的动机**: M5 发现 CPU 方案把 warm 当 hot——这恰好印证了 PACT 的核心论点：frequency-based 方法无法准确识别真正的 critical pages
