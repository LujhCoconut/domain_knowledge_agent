# MAC(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-lee.pdf
- **全称**: MAC: Metadata Acceleration for Sustainable Performance in Big-Data Systems with CXL DRAM
- **系统名**: MAC (Metadata Acceleration for CXL — 在 CXL DRAM 中加速内核元数据管理)
- **作者**: Dusol Lee (SNU), Yan Sun, Houxiang Ji, Vinit Gupta, Austin Antony Cruz (UIUC), Inhyuk Choi (SNU), Nam Sung Kim (UIUC), Jihong Kim (SNU)
- **类型**: 论文-系统 (OS/硬件协同设计 + NMP)
- **一句话 TL;DR**: 大容量 CXL DRAM 系统中，内核元数据（page descriptors + Xarray）溢到 CXL 后，后台内存回收 (kswapd) 效率下降 42%，迫使应用触发前台回收 → 尾延迟飙升 2.8×。MAC 在 CXL DRAM 内用 NMP 加速器直接处理元数据遍历，尾延迟降低 **98%**。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **Page descriptor** | 每 4KB 物理页一个 64B 元数据结构（flag, refcount, LRU 信息等） | 占物理内存 1.6%，回收时必须遍历检测可回收性 |
| **Xarray** | Linux 内核用于索引 page cache 的基数树结构（584B/node, 64 entries/node） | 回收时需从 root 遍历到 leaf，将页从 cache 中移除 (store shadow) |
| **kswapd** | 每个 NUMA node 一个的后台页回收内核线程 | 元数据在 CXL → kswapd 效率 -42% → 触发前台回收 |
| **Foreground reclamation** | 应用线程在 alloc 时发现 free pages < low watermark → 自行回收 | 在应用 critical path 上 → 尾延迟飙升 |
| **NMP** (Near-Memory Processing) | CXL DRAM 控制器内的计算单元（如 ARM core）直接处理 CXL 本地数据 | MAC 的核心：在数据所在处（CXL）就地处理元数据 |
| **MACbuf** | 在 CXL DRAM 中预保留的 per-core 共享缓冲区 | CPU 与 NMP 轻量级异步通信通道 |
| **MACcmd** | 向预留地址范围写入的 CXL.mem 写操作被 packet filter 解析为 "NMP 启动" 命令 | 无需修改 CXL 协议！用标准 CXL.mem write 触发加速 |
| **BIsnp** (Back Invalidation Snoop) | CXL 3.x 协议中 device→host cacheline invalidation | Xarray 被 NMP 修改后需 invalidate host 缓存 → BIP over 并行为关键优化 |
| **BIsnpInvBlks** (Block Invalidation Snoop) | CXL 3.x 中单消息覆盖 4 个连续 cacheline 的批量 invalidation | 减少 4× 协议消息数 |
| **clwb** (CacheLine WriteBack) | x86 指令，将修改了的 cacheline 异步写回 | host 写 Xarray 后需写回，让 NMP 看到最新数据 |

## 背景与动机

### 问题
- CXL DRAM 容量可达 DDR 的 4-8×（成本 <50%），但延迟高 2.4×
- 内核元数据（page descriptors + Xarray）随系统内存线性增长，总量可达 DDR 容量的 **24-40%**
- 在内存压力下，这些元数据会溢出到慢速 CXL DRAM

### 连锁反应 (core finding)
```
元数据在 CXL DRAM (slow)
  → kswapd 后台回收效率 -42% (访问 CXL 延迟)
  → free pages 不足
  → 应用线程被迫做前台回收 (on critical path)
  → foreground reclamation +6.5×
  → p99.99 尾延迟 +2.8×
```

**关键数据** (Figure 2): 2.4× 元数据访问延迟 → p99.99 latency 2.6-2.8×; 根本原因是 foreground reclamation 次数增加 6.5×。现代超大规模应用（RocksDB、PostgreSQL、Neo4j）要求 p99.99 读延迟仅数 ms → 无法接受。

### 微架构 breakdown (Figure 3)
- page descriptor traversal: CXL 中慢 3.6×（超过单纯 2.4× 延迟差异 → 说明有更深层的效率损失）
- Xarray traversal: CXL 中慢 3.9×
- kswapd 单次循环的 Xarray 管理开销 (xarray_mgmt) 从 DDR-only 的 ~30µs 涨到 CXL 的 ~200µs
- sched (核抢占): CXL 锁持有时间更长 → 更容易被抢占 → 额外的调度延迟尖刺

### 元数据溢出的数值
- RocksDB YCSB: 1.8 TiB DB, 120 GiB 内存 (24G DDR + 96G CXL) → Xarray 3.7 GiB + page descriptors 2 GiB = **5.7 GiB metadata**
- PostgreSQL TPC-B: 1 TiB → 5.3 GiB metadata
- 1:4 DDR:CXL 配置下，metadata 总大小 ≈ DDR 容量的 24%; 1:8 时 ≈ 40%

### 为何 metadata 适合 NMP offload
1. **操作简单且重复**: page descriptor flag check = bitmask; Xarray walk = arithmetic + shift + dereference
2. **kernel direct-map (__pa())**: 虚拟→物理地址转换无需查页表，一个减法即可 → NMP 可以直接用物理地址访问
3. **每次 recycle 批量处理**: minimum 32 pages/batch → 适合多加速器并行
4. **Xarray walk 期间无结构变更**（node allocation/deallocation 不会发生）→ 可安全并行

### 我的分析
这是 OSDI '26 中一篇独特的硬件/软件协同设计论文——它和 M5(ASPLOS'25) 一样将逻辑推入 CXL 设备侧，但 M5 做的是"tracking hot pages"，MAC 做的是"accelerating metadata reclamation"。深层洞察是：**CXL 不仅仅是容量扩展，大容量 CXL 创造了新的元数据管理瓶颈——元数据本身的访问延迟变成了系统瓶颈。** 这个"元数据的元数据"问题在体系结构设计中常被忽视。

## 方案介绍

### 整体架构 (Figure 4)

```
Host CPU (applications + kswapd)
   ├── Offloader: 收集 metadata 信息 → MACbuf → 发 MACcmd
   └── 等待 NMP 完成 → 执行 unmapping/writeback/DISK I/O
CXL DRAM
   ├── Packet filter: 匹配 MACcmd write → 解析命令
   ├── Controller: 调度加速器
   ├── Accelerators (最多 32 个): 遍历 page descriptors / Xarray walk
   ├── MACbuf: per-core 1024B 共享缓冲区
   └── Metadata (page descriptors + Xarrays) 全部放在 CXL DRAM
```

### 关键创新 1: 无新协议的轻量级 NMP 启动 (§4.2)

**MACcmd**: 不是新的 CXL 协议——**就是一个标准 CXL.mem write** 到预注册的 MACbuf 地址范围。
- Host core 写 MACcmd → packet filter 识别 → parse (operation type, core ID, buffer size) → 触发加速器
- 完全兼容现有 CXL 协议，无需 CPU 硬件修改

**MACbuf**: boot time 为每个 core 预分配 1024B dedicated buffer
- 内装: Xarray head pointers, target page indices, shadow values, page descriptor addresses
- 每 core 一个足够（因为 Linux 禁用了 page reclaim 期间的 core preemption）

### 关键创新 2: 分阶段 offload + host-accelerator 协作 (§4.3)

**Stage 1 — Page descriptor traversal** (Figure 6, steps 3-5 ):
1. Host isolate 32 个 victim page pointers → 收集物理地址 → 写入 MACbuf → 发 MACcmd
2. CXL 加速器并行遍历 descriptors，检查 flag bits (valid/dirty/active/referenced) → 分类为 reclaimable vs non-reclaimable
3. Host memcpy 取回结果 (<0.5µs)

**Stage 2 — Xarray walk** (steps 6-9 ):
1. Host 对 reclaimable pages 获取 Xarray locks → 构造 (Xarray_head, target_offset) pairs → MACbuf → MACcmd
2. CXL 加速器并行遍历 Xarray → 将 target slot 写为 shadow value (invalidate pointer)
3. 完成后 host 释放 locks，更新统计

**Host 并发优化**: 在 CXL 做 Xarray walk 时，host 同时做:
- mapped pages → unmap (rmap)
- dirty pages → 启动 writeback I/O

### 关键创新 3: 并行 Xarray Walk + BIsnp 重叠 (§4.5)

**BIsnp 开销问题**: 每次 Xarray walk 后需要 invalidate host 端的 target cacheline（device 修改了 Xarray 内容）
- 单个 BIsnp ≈ 500ns
- 32 pages × 500ns = **16µs** — 超过了 32 次 Xarray walk 自身的 12.8µs

**解决方案 (Figure 8)**:
1. **Overlap BIsnp with next walk**: NMP 做完一次 walk 后立即发 BIsnp + 同时开始下一个 walk → 像流水线一样重叠
2. **BIsnpInvBlks (CXL 3.x)**: 单次批量 invalidate 4 个连续 cacheline → 消息数 -4×
3. **多加速器并行 Walk**: 32 页分给 16 个加速器 (2 pages/accel) + 分给 8 个 BIsnpInvBlks 组 → 2-3µs (vs serial 16µs)
4. **Data sync overhead**: controller 追踪多个加速器的 completion status (shared atomic variable) → ~1µs overhead

**综合加速比**: 55% Xarray walk overhead reduction

### 关键创新 4: 一致性管理 (§4.4, Figure 7)

**Host→CXL 方向** (page insertion):
- Host 写 Xarray → clwb (异步 cache writeback)
- 每 query 约 1-3 clwb，每人 30ns → 仅 0.06% query lifetime overhead
- 实测在 workload 稳定阶段 clwb overhead negligible

**CXL→Host 方向** (page eviction by NMP):
- NMP 修改 Xarray → BIsnp invalidate host cacheline
- 每 batch 32 pages → 32 BIsnp
- 需要 BIsnp optimization (§4.5) 来保证效率

### 硬件原型 (FPGA)

- Intel Agilex 7 I-series FPGA
- 当前硬件不支持 device-biased BIsnp → 用 host-biased CXL.cache write 替代（write 总是经 host root complex 做 coherence）
- NMP 加速器 state machine 镜像软件逻辑
- Device-biased reads (跳过 coherence checks) 加速非更新型访问

## 证据与评估

### 测试环境
- **CPU**: Intel Xeon 6710E (双路, 64 cores each, 96 MiB LLC)
- **内存**: Socket 0: 2×32GB DDR5; Socket 1: 2-8×32GB DDR5 (仿真 CXL)
- **延迟**: 本地 118ns, 远程 270ns (2.3×, 匹配 CXL 特性)
- **仿真方案**: Socket 1 as CXL device (33 cores: 1 controller + 32 accelerators), Intel CAT 限制 CXL 侧 LLC 为 8 MiB
- **对比**: Baseline (元数据可溢到 CXL), Baseline-P (强制 pin metadata 在 DDR), MAC-S (1 controller+4 accel), MAC-P (1 controller+32 accel)
- **Workloads**: RocksDB YCSB (2.5 TiB/2.0 TiB), PostgreSQL OLTP (2.0 TiB), Neo4j LDBC SNB (1 TiB), LMDB mmap (1.7 TiB)

### 关键结果

| 实验 | 结果 | 要点 |
|------|------|------|
| RocksDB YCSB, 1:2 DDR:CXL | MAC-P **p99.99 -98%** vs Baseline; MAC-S **-97%** | 主要收益来自消除 foreground reclamation |
| RocksDB 各 DDR:CXL 配比 | MAC-P/MAC-S 在所有配比下 (1:1, 1:2, 1:4) 均显著优于 Baseline | 容量越大，改善越明显 |
| Xarray spillover (Table 2) | baseline: 1:4 时 68% Xarray 在 CXL → kswapd 慢 | MAC 故意将全部 metadata 放在 CXL (容量充裕) → 用 NMP 加速 |
| Page reclamation 分解 (Fig 12) | MAC-P: Xarray walk -80%, page descriptor traversal -58%, kswapd free page generation +36% | 前台回收 -66% at 1:2 |
| vs Baseline-P (pin in DDR) | MAC-P p99.99 仍低 22% | Baseline-P 虽减少 CXL 访问，但 slab allocation overhead (+150-300×) 导致新瓶颈 |
| PostgreSQL OLTP | 相似趋势 | 扩到更多 workload 类型 |
| Neo4j graph processing | 相似趋势 | IS/IC 两种 workload |
| FPGA 原型 | page descriptor traversal + Xarray walk 准确计时 | 预测加速比接近仿真结果 |

### 为什么 Baseline-P (pin in DDR) 不是解

虽然 Baseline-P 减少了 CXL 延迟，但在高内存压力下出现了新问题：slab allocation latency 从 2-4µs 涨到 10-600µs。因为所有 Xarray node 分配都被强制到 DDR 的 slab pool → metadata 和应用数据争抢同一池，slab 分配器开销爆炸。

**这进一步验证了 MAC "去 CXL" 的决策**: 不是为了避开 CXL，而是接受 metadata 在 CXL 并加速本地的管理。

## 整体评估

### 真正的新意
1. **识别了"大容量 CXL 的元数据瓶颈"这一新问题**: 以前的工作（PACT/TMO/CAMP）都在关注"如何把应用数据放在 CXL"，但忽略了内核元数据本身的 footprint 和延迟影响
2. **利用 kernel direct-map 让 NMP 无需 MMU**: 这是系统设计与硬件设计的精巧交叉点——利用了 Linux 内核地址空间的特性（__pa() 只需减法）消除了通常 NMP 方案需要的大开销地址转换
3. **用标准 CXL.mem write 作为 offload 命令通道**: 不依赖新 CXL 协议 → 兼容现有硬件

### 优点
- **清晰的问题链**: "metadata in CXL → kswapd slow → foreground reclamation → tail latency spike" — 每一步都有数据支撑
- **完备的实现**: 软件仿真 + FPGA 原型双重验证
- **发现了一个反直觉的结果**: Baseline-P (pin in DDR) 反而在某些场景下不如 MAC——因为 slab contention 的新瓶颈
- **多 workload 验证**: RocksDB, PostgreSQL, Neo4j, LMDB — 涵盖 KV store, RDBMS, graph DB, mmap DB
- **利用硬件趋势**: CXL 3.x BIsnpInvBlks + 多核 CXL 控制器 (ARM cores) 使 NMP 越来越 practical

### 局限
1. **BIsnp 依赖 CXL 3.x**: 当前硬件不支持 device→host invalidation → 用 host-biased write 替代，性能与真正的 BIsnp 可能有差距
2. **仅加速 page reclaim**: 其他内核元数据密集操作（如 page fault handling、memory cgroup accounting）未涉及
3. **MACcmd packet filter 需要 CXL 控制器支持**: 虽不需要 CPU 修改，但需要在 CXL controller/FPGA 中添加简单逻辑
4. **仅适用于有 CXL DRAM 的系统**: 纯 DDR 或仅 CXL 的情况不适用
5. **Xarray lock 仍是串行瓶颈**: Xarray lock 在 host 端 → 如果大量并发 reclaim，lock contention 可能限制 NMP 并行度
6. **电源/面积开销未评估**: NMP 加速器的额外功耗和芯片面积

### 与 M5 和 PACT 的关系

三篇论文来自同一实验室（Nam Sung Kim, UIUC & SNU 合作线），形成 CXL 研究的三层视图：

| 论文 | 问题 | 方法 | CXL 层 |
|------|------|------|--------|
| M5(ASPLOS'25) | 应用数据 hotness 追踪不准 | CXL controller HPT/HWT 硬件追踪 | 应用数据 |
| **MAC(OSDI'26)** | **内核元数据访问成为 CXL 瓶颈** | **CXL NMP 加速 metadata traversal** | **内核元数据** |
| PACT(ASPLOS'26) | Per-page criticality 量化 | PAC 指标 + 软件迁移策略 | 应用数据 (软件) |

### 可复用启发

1. **"元数据的元数据"问题**: 系统规模增长 → metadata 本身成为瓶颈。这在分布式系统、数据库、文件系统中是普遍现象，需要 design for metadata scalability
2. **Kernel direct-map 的好处**: Linux 内核将全部物理内存线性映射到虚拟地址空间的特性（__pa() 只需减法）对 NMP 方案是巨大的简化。设计 OS 新特性时考虑 NMP 友好性
3. **"简单+重复"是 NMP 的最佳 match**: page descriptor 的 bitmask check 和 Xarray 的 arithmetic walk 不需要复杂控制流 → 适合 state machine 实现
4. **CXL.mem write 作为通用 offload 触发**: 不需要新协议 → 降低 adoption barrier。适用于任何需要在 CXL 设备侧触发操作的场景
5. **Foreground vs Background reclaim 的 cascading failure**: kswapd 效率下降不是直接损害性能，而是通过"迫使 foreground reclaim"来间接影响——这种"cascading"型性能退化需要更深入的 root cause analysis
6. **Slab allocation overhead 是 Baseline-P 的 hidden bottleneck**: "把元数据移到 DDR"看起来是 obvious fix，但引发了 slab pool contention——系统设计中的 second-order effect 需要仔细权衡
