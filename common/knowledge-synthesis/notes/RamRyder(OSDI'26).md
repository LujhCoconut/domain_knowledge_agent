# RamRyder(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-zhou-yanbo.pdf
- **全称**: Break on Through to the Other Side: Pooling Memory Elastically with RamRyder
- **系统名**: RamRyder (RAM + Ryder = 内存骑手)
- **作者**: Yanbo Zhou (UC San Diego), Erci Xu* (SJTU), Dongjoo Seo, Adam Manzanares (Samsung Semiconductor), Steven Swanson (UC San Diego)
- **开源**: https://github.com/ramryder-project/ramryder
- **类型**: 论文-系统 (cloud memory management + virtualization)
- **一句话 TL;DR**: 第一个在**软件层面**实现内存带宽和容量（基本）独立分配的云 VM 系统——通过接管 BIOS/UEFI 配置将内存通道暴露给软件管理，用 channel partitioning 替代硬件全通道交错，实现 VM 间带宽隔离 + CXL 弹性扩展。集群层面容量利用率 +28.6%、带宽利用率 +43.2%，性能接近独占硬件。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **DRAM mapping** | 物理地址到 DIMM/通道/rank/bank 的硬件映射 | 核心问题：硬件 all-ways interleaving 导致所有 VM 共享全部通道→无隔离 |
| **Channel partitioning** | 通过 BIOS/UEFI 禁用通道交错，将每个通道的物理地址线性暴露 | RamRyder 的基础：让 OS 可以控制 page-to-channel 映射 |
| **C-NUMA (Channel-NUMA)** | 将每个内存通道抽象为 guest OS 中的一个 NUMA node | Channel 虚拟化抽象 |
| **S-NUMA (Server-NUMA)** | 多个 C-NUMA 组成的 server-level NUMA node | 保留现有 NUMA 原语的兼容层 |
| **Channel-weighted interleaving** | 按各 sNode 的带宽加权比例在 DIMM 和 CXL 通道间交错分配页面 | 利用 CXL 额外带宽的关键策略 |
| **Channel hot-plug/unplug** | 运行时动态添加/移除内存通道（不改变总容量） | 动态带宽调整机制 |
| **Spatial over-provisioning** | 为独占硬件而过度订阅（至少半个 socket）→ 内存带宽闲置 | 根因之一 |
| **Temporal over-provisioning** | 为峰值负载预留资源 → 非峰值时段浪费 | 根因之二 |
| **All-ways interleaving** | 硬件将连续物理地址按 cache-line 粒度交错到所有通道 | 现状：最大化带宽但无隔离 |
| **One-way interleaving** | 每个通道独立管理自己的地址空间 | RamRyder 通过 BIOS 实现的配置 |

## 背景与动机

### 问题
- 云计算中 CPU、存储、网络均可弹性分配，但**内存容量和带宽的分配仍然僵化**
- 云厂商按固定比例（如 2:1, 4:1, 8:1 GB/vCPU）提供内存，带宽与容量绑定，无法独立分配
- Azure trace 显示 **45% VM 在一半时间内内存容量 untouched**（已有大量研究），但带宽更严重：
  - **90% 服务器平均带宽利用率 < 44.5%**
  - **90% 服务器峰值带宽利用率 < 82.2%**

### 两个根因

**Spatial over-provisioning**: 用户为满足性能 QoS 要求独占硬件（至少半个 socket、独占内存通道和 LLC），导致即使容量需求不高也锁定了全部带宽

**Temporal over-provisioning**: 内存资源在 VM 创建时确定且不变 → 用户按峰值配置 → 低谷时大量容量+带宽闲置

**关键观察**: 容量和带宽的利用率的时空模式是解耦的（Figure 3）——同一台服务器上容量可能接近满但带宽空闲，或反之。这为独立管理二者创造了条件。

### 为什么现有方案不行

| 方案 | 代表 | 局限 |
|------|------|------|
| Memory pooling (CXL) | Pond, TPP, Memtis | 只管理容量，不管带宽 |
| Hardware throttling | Intel MBA, AMD QoS | L2-LLC 间插延迟 → 不精确、不线性、浪费 CPU cycle |
| Software throttling | Canvas, Spirit | 仅适用于 RDMA 远程内存（软件在存取路径上），不适用于 load/store 的本地内存 |
| Indirect (fewer cores, lower freq) | — | 损害其他 VM 指标 |

**核心洞察**: 带宽与可用通道数**线性**相关（Figure 5），通道是带宽的 natural allocation unit。现有的 all-ways interleaving 让所有 VM 共享所有通道 → 无法隔离 → 无法独立分配带宽。

### 我的分析
这是 OSDI '26 中唯一一篇聚焦传统云基础设施（非 LLM）的论文。它和前面 5 篇 LLM 论文形成鲜明对比——LLM 论文都在 GPU 上做优化，RamRyder 回到了 CPU + DRAM + CXL 的经典服务器场景。其核心贡献在于**将内存通道从硬件固化的"实现细节"提升为 OS 可管理的一等资源**，这类似于当年虚拟内存将物理页框从硬件细节中抽象出来的思路。

## 方案介绍

### 整体架构 (Figure 6)

```
Guest Kernel (Linux)
  ├── S-NUMA abstraction (server-level topology)
  ├── C-NUMA abstraction (per-channel)
  ├── Channel-weighted interleaving (cross-tier)
  └── Page-to-channel allocation policies
Hypervisor (QEMU)
  ├── Channel virtualization (GPM→channel mapping)
  └── ACPI topology exposure
Resource Manager (user-space daemon)
  ├── Per-channel DAX device chunk management
  ├── Bandwidth monitoring (perf counters)
  └── Channel allocation / hot-plug decisions
Hardware (BIOS/UEFI reconfigured)
  ├── One-way interleaving (channels partitioned)
  └── CXL devices as separate zNUMA nodes
```

### 关键创新 1: 软件定义的内存通道管理 (§4.1, §5.1)

**Memory Topology Provisioning** (Figure 10):
1. **BIOS/UEFI 重配置**：禁用硬件 all-ways interleaving → 每个通道的物理地址空间线性暴露（one-way interleaving）
2. **区域检测**：根据每通道 DIMM 容量计算对应的物理地址范围，跳过 memory holes
3. **DAX 预留**：每通道的内存区域通过 `memmap` 参数预留为 DAX device（host OS 保留 10GB）

**Channel 虚拟化**：
- Resource Manager 将每个 DAX device 切分为 128MB chunks
- QEMU 从不同 DAX devices（即不同通道）的 chunks 构造 NUMA nodes
- 通过 ACPI table 将物理拓扑（socket/zNUMA + DAX index）暴露给 guest

**Channel 抽象**（Figure 7b）：
- **C-NUMA (cNode)**: 一个内存通道 = guest OS 中的一个 NUMA node
- **S-NUMA (sNode)**: 同 socket 的 cNode 组 = 保留 server-level NUMA 语义
- Guest kernel 维护 sNode ↔ cNode 映射，只向用户暴露 sNode

**页面分配策略**：
- Step 1: 选择 sNode（标准 NUMA-aware policy）
- Step 2: 在 sNode 内跨 cNode 均匀交错分配（channel interleaving → 模拟硬件交错）
- 开销：128 线程时仅 3.6% overhead vs 硬件交错；单线程时最大 7.4%（2KB stride）

### 关键创新 2: 带宽和容量的独立扩展 (§4.2)

**Channel selection**: 根据带宽和容量需求独立决定用多少 CXL 通道
- **带宽扩展** (Figure 8a): Guest 内存跨多个 CXL 通道映射 → 用 channel-weighted interleaving 利用额外 CXL 带宽
- **容量扩展** (Figure 8b): Guest 内存映射到有未用容量的通道 → 用 Linux memory tiering 将热页留在 DIMM、冷页移到 CXL

**Channel-weighted interleaving**: 按 sNode 的最大带宽加权比例跨 tier 分配页面
- 例: sNode-0 有 3 DIMM channels (36 GB/s each = 108 GB/s), sNode-1 有 1 CXL channel (27 GB/s) → 权重比 108:27 = 8:3 → 每 8 页从 sNode-0 后跟 3 页从 sNode-1

**互补工作负载配对**: 将 "容量重+带宽轻" 和 "容量轻+带宽重" 的 VM 放在相同 CXL 通道上 → 消除碎片

### 关键创新 3: 动态带宽调整 (§4.3)

**Channel hot-plug/unplug** (Figure 9):
1. 分配额外 GPM 映射到新 CXL 通道（容量 = X/(N+1)，其中 X = 原容量，N = 原通道数）
2. Guest kernel 构造新 cNode 加入已有 sNode
3. **Page redistribution**: 通过清除 present bits + lazy migration 将页面重新分布到所有通道
4. 从原有通道回收等量容量（hot-unplug memory blocks）

**开销**:
- Channel hot-plug/unplug: 数微秒（可忽略）
- Page redistribution: 取决于页面数和迁移速率 → 典型 ~2.2s (1.82 GB/s migration rate, ~40% pages moved)
- 延迟无明显尖刺（lazy migration 平滑过渡）
- 对瞬时短 burst 可能来不及反应（至少需要 1s 收集 perf counter → 不适合 <1s 的极短突发）

## 证据与评估

### 测试环境
- **硬件**: AMD EPYC Zen 5 (128 logical cores, 8 CPU dies), 8×32GB DDR5 DIMM, 4×256GB Samsung CXL 2.0
- **VM 配置**: 4 VMs (2 小 + 2 大), 匹配 AWS/Alibaba compute-optimized 比例
- **Host OS**: Debian, Linux 6.15
- **对比**: Ideal (独占硬件), Shared (默认共置), HW-Throttle (Intel MBA / AMD QoS)

### 关键结果

| 实验 | 结果 | 要点 |
|------|------|------|
| 小 VM 读延迟 (Fig 12a) | Shared 中延迟 +78.5%，带宽 -41.2%；RamRyder 在 5% 内接近 Ideal | 小 VM 最易受大 VM 干扰 |
| 大 VM 读延迟 (Fig 12c) | RamRyder 延迟比 Shared 低 42.7% | 通道隔离消除竞争 |
| Memcached + Redis YCSB | RamRyder tail latency 在 5% 内接近 Ideal；Shared/HW-Throttle 最高 +42.7% | 延迟敏感型应用受益最大 |
| STREAM + Graph | RamRyder 吞吐 <5% 接近 Ideal；Shared 吞吐 -37.3%、时间 +58.8% | 带宽密集型应用关联受益 |
| 集群级利用率 (Fig 15) | 容量均值 +28.6% (P30)；带宽均值 +43.2% (P90) | 互补工作负载整合效果 |
| HW-Throttle 失效 (Fig 12a/12c) | 小 VM 延迟反而增加 → 证明了 throttle 的不精确性 | 插延迟不能替代通道隔离 |
| LLC vs Channel 隔离 (Fig 17) | Channel isolation 贡献远大于 LLC isolation | 主要竞争源是通道而非缓存 |
| 动态带宽调整 (Fig 20) | 分配 2.2s，回收 1.1s，延迟平滑无尖刺 | Lazy migration 有效 |
| SW interleaving overhead (Fig 19) | 128 线程 avg 3.6%，单线程 avg 5.1%，max 7.4% | 开销可接受 |
| 动态负载敏感度 (Fig 21) | 持续变化能追上，瞬时 burst <1s 可能错过 | 适合渐进式负载 |

### 为什么 RamRyder 能工作

1. **通道是最自然的带宽分配单元**：带宽随通道数线性增长（DIMM 和 CXL 都遵循此规律）
2. **通道级物理隔离 > 延迟插入**：HW throttling 不精确且反效果（小 VM 延迟增加），因为它是"惩罚所有人"而非"隔离少数"
3. **容量和带宽的解耦**：利用 CXL 提供弹性容量（tiering policy）和弹性带宽（channel-weighted interleaving），二者独立配置
4. **现有 NUMA 原语的兼容**：S-NUMA/C-NUMA 抽象让 guest OS 无需知道"通道"这一新概念，只需继续用现有的 NUMA-aware 内存分配

## 整体评估

### 真正的新意
1. **将内存通道从硬件细节提升为 OS 可管理的一等资源**：在此之前，通道由硬件全权控制（all-ways interleaving 在 BIOS 时固化且不可运行时更改）。RamRyder 通过在 BIOS 层禁用交错 + DAX 预留 + QEMU NUMA 虚拟化，让通道成为可分配、可热插拔的软件抽象
2. **解耦容量和带宽分配**：云厂商的固定 vCPU:内存 比例意味着带宽和容量被绑定。RamRyder 首次让这两个维度在（近似）独立的情况下被分配——DIMM 提供保证带宽，CXL 提供弹性容量和/或额外带宽
3. **Channel-weighted interleaving**：跨 tier 的带权页面交错是一种新型的 page allocation policy，结合了 NUMA locality 和 memory tiering 的优点

### 优点
- **硬件无需修改**：仅在 BIOS/UEFI 配置 + DAX 预留层面操作，commodity server 可运行
- **精确的带宽控制**：相比 HW throttling 的不精确和非线性，通道数 ∝ 带宽是物理定律
- **性能接近独占硬件**：延迟和吞吐均在 Ideal 的 5% 以内
- **开源**：完整实现，包括 BIOS 工具链 + QEMU 修改 + guest kernel 修改
- **集群层面收益显著**：28.6% 容量 + 43.2% 带宽利用率提升，无需额外硬件投入

### 局限
1. **需要 guest kernel 修改**：S-NUMA/C-NUMA 抽象需要修改 Linux 内核。作者预计这将成为标准 OS 接口，但短期内是 adoption barrier
2. **通道粒度对极小型 VM 仍然偏粗**：每通道最小 1 个 DIMM（32-128GB），单个 VM 需求可能远低于此 → 需要将多个小 VM 放在同一通道（辅以 HW throttling）
3. **动态带宽调整的响应时间**：>1s 的 perf counter 采样 + page redistribution 的秒级延迟 → 不适合亚秒级 burst
4. **CXL 设备当前仅单通道**: 测试中的 CXL 2.0 设备内部只有 1 个 DDR5 通道 → 未来多通道 CXL 设备需要厂商暴露内部交错策略
5. **全读和混合读写下 CXL 通道的性能**：CXL 通道带宽低于 DIMM 通道（~27 GB/s vs ~36 GB/s per channel），channel-weighted interleaving 权重需要正确反映这一点
6. **仅限于单主机**: 当前设计是单 host server，扩展到 CXL switch 多主机场景需要额外协调

### 与本知识库 CXL 论文的关系

RamRyder 的 CXL 使用方式与前面几篇不同：

| 论文 | CXL 用途 | 粒度 |
|------|---------|------|
| PACT | CXL 作为 slow memory tier（page migration） | Page |
| TMO | PSI 驱动的 offloading 决策 | cgroup |
| CAMP | 预测 CXL 造成的 slowdown | Workload |
| M5 | CXL controller 硬件追踪 hot pages | Page+Word |
| **RamRyder** | **CXL 作为弹性带宽 + 容量资源池，通过通道管理独立分配** | **Channel** |

RamRyder 的视角比前面几篇更高——不是在"如何用好 CXL"层面，而是在"如何将 CXL 作为云资源管理框架的一部分"层面。它和 Prism(OSDI'26) 形成有趣的对比：Prism 用 memory ballooning 在 GPU 上做弹性内存，RamRyder 用 channel management 在 CPU 上做弹性内存。二者共享同一个哲学：**将内存从固定配置变为弹性资源**。

### 可复用启发

1. **"通道是带宽的自然单位"**：这个观察简洁而有力。任何需要对共享总线/互连进行带宽隔离的场景都可以考虑类似的"partition the lanes"方案（如 PCIe lanes、NVLink lanes、network queues）

2. **硬件 all-ways interleaving 是一把双刃剑**：它最大化单应用带宽，但消除了一切隔离可能。RamRyder 选择牺牲部分峰值带宽（平均 3.6% overhead）换取弹性 + 隔离。这是经典的"峰值 vs 利用率" tradeoff

3. **S-NUMA/C-NUMA 的双层抽象模式**：将新的硬件维度（通道）映射到已有 OS 概念（NUMA node）上，同时保留原始 topology 供兼容。这种"new primitive → wrapper on existing abstraction"的设计模式可推广到其他系统扩展

4. **独立管理容量和带宽**：这个思想在云计算各层都成立——不仅是内存，存储（IOPS vs capacity）、网络（throughput vs connections）也存在类似的"绑定"问题

5. **DAX device + QEMU NUMA + ACPI → 软件定义内存拓扑**：这套组合（BIOS 配置区域 → DAX 预留 → QEMU NUMA 虚拟化 → ACPI 暴露 → guest kernel NUMA 识别）形成了一条完整的"软件定义硬件拓扑"链路，可复用于其他需要 expose hardware topology to guest 的场景

6. **Lazy migration 对弹性分配至关重要**：RamRyder 不是"分配通道后立即迁移所有页"，而是"先改 policy→lazy refault→逐步重分布"。这个 lazy 策略使动态带宽调整在延迟上几乎 invisible
