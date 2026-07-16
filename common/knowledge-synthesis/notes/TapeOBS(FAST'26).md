# TapeOBS(FAST'26)

- **来源**: https://www.usenix.org/system/files/fast26-wang.pdf, FAST '26, February 24–26, 2026, Santa Clara, CA
- **作者**: Qing Wang (Tsinghua), Fan Yang, Qiang Liu, Geng Xiao (Huawei Cloud), Yongpeng Chen, Hao Lan (Tsinghua), Leiming Chen, Bangzhu Chen, Chenrui Liu, Pingchang Bai, Bin Huang, Zigan Luo, Mingyu Xie, Yu Wang (Huawei Cloud), Youyou Lu (Tsinghua), Huatao Wu (Huawei Cloud*), Jiwu Shu (Tsinghua & Minjiang University*)
- **一句话 TL;DR**: 华为云基于磁带的归档存储服务 TapeOBS——用全异步磁带池+HDD 缓冲池+批量EC+专用驱动器+按生存期分组写入+读请求重排序，实现磁带存储的近满带宽利用，TCO 比 HDD 方案低 4.95×。
- **资料类型**: 论文-系统（工业部署经验）

---

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| Tape Library | 容纳上千盘磁带+少量驱动器+一个机械臂的存储单元 | 基本部署单元（本文配 1000 tapes + 4 drives） |
| Tape Drive | 读写磁带头，磁带库中仅 4 个 | 核心瓶颈资源（每 drive 360MB/s） |
| Drive Thrashing | 驱动器频繁在不同磁带间切换（~80s/次切换，有效带宽减半） | 需消除的核心性能问题 |
| PLog | Persistent Log，华为云存储基础设施中的 append-only 基本存储单元，EC 复制 | TapeOBS 在磁带和 HDD 上统一使用的存储抽象 |
| Sub-PLog | PLog 在单盘磁带上的分片 | EC 条带的一个 chunk |
| MDC | Metadata Controller，管理磁带池拓扑信息和 partition view | 控制面关键组件 |
| Partition View | 将 plog-id 按 hash 映射到 EC group（一组跨磁带库的磁带） | 数据放置的核心数据结构 |
| b-EC | Batched Erasure Coding，批量纠删码——服务层聚合同一批次的多对象到一个 PLog append | 减少每对象跨磁带库数量的关键设计 |
| DataBrain | 调度非实时任务的控制面组件 | 执行 restore 重排序 + 生存期分组 + GC 调度 |
| VDB | Virtual Database，磁带库本地 SSD 上的 KV store（MetaStore + DataStore） | 消除磁带的随机元数据访问 |
| MetaStore | VDB 中存储 sub-PLog 元数据的 KV store | 查找物理位置无需接触磁带 |
| DataStore | VDB 中缓冲 sub-PLog 数据切片的 KV store | 写缓冲吸收数据，flush 时写入磁带 |
| TLS | Tape Library Scheduler，磁带库调度器 | 读排序 + 流控 |
| TLM | Tape Library Manager，磁带库管理器 | 封装机械臂+驱动器操作 |
| LDEC | Low-Density Erasure Coding，华为自研 MDS array code (XOR+Galois) | 12+2 配置，存储冗余 1.17 |
| Wrap | 磁带上横向排列的数百条物理轨道，相邻 wrap 方向相反 | 影响磁头寻道的物理约束 |
| Dedicated Drives | 将 4 个驱动静态分配：2 写 + 1 读 + 1 内部操作 | 消除混合负载导致的 drive thrashing |

---

## 背景与动机

### 磁带技术现状

- LTO-10 (2025.5): 30TB 容量, 400MB/s; IBM TS1170 (2023): 50TB, 400MB/s
- 磁带支持加密 (AES)、压缩 (LTO 宣称 2.5:1)、分区（独立可写 append point）
- 现代磁带 append-only（类似 SMR HDD，瓦式叠写→原地更新破坏相邻数据）
- 磁带技术 roadmap: 2024-2034 年 cartridge 容量年均增长 32%

### 为什么选磁带而非 HDD 做归档

| 维度 | 磁带 vs HDD |
|------|------------|
| CapEx | **2.68× 更低** |
| OpEx (含能耗) | **16.11× 更低**（磁带仅在读写时耗电，存储槽中零功耗） |
| TCO (10年, 100PB初始+50%年增长) | **4.95× 更低** |
| 寿命 | 10 年 vs 5 年 |
| CO₂e 排放 | 显著更低 |
| 物理密度 | 节省 44% 机房空间 |

### 磁带的核心挑战

磁带库的硬件特征与分布式存储的需求直接冲突：

1. **低 drive-to-tape 比**：1000 盘磁带但仅 4 个驱动器 → 驱动器是稀缺瓶颈资源
2. **装载延迟极高**：更换磁带需 ~80s（退带 + 机械臂移动 + 装载 + 寻道 → 有效带宽可降一半）
3. **随机读代价大**：磁带随机读需要 wind/rewind → seek time 显著

---

## 方案介绍

### 整体架构

```
用户 → Service Layer (OBS APIs, 认证, 流控)
     → Index Layer (Object ID → ⟨plog-id, offset, size⟩ 映射，LSM-Tree)
     → Persistence Layer:
         ├── HDD Pool (容量≈磁带池的 4%，临时 staging area)
         │     └── 复用华为云成熟 HDD-based OBS，EC 保障高可用
         ├── Tape Pool (14 tape rack × 10PB = 140PB per pool)
         │     ├── Rack = 1 head server + 1 tape library (1000 tapes, 4 drives)
         │     ├── Head server: 2×12核, 128GB DRAM, 2×3TB NVMe SSD
         │     ├── 14 racks 共享 2 个 ToR 交换机（25Gbps NIC）
         │     └── Local Storage Engine: VDB + TLS + TLM
         └── MDC (元数据控制，心跳检测，健康管理)
     → DataBrain (非实时调度: restore重排序, 生存期分组flush, GC)
```

### 三条设计原则

1. **最小化 tape library 内的 drive thrashing**（专用驱动器 + 批量 EC）
2. **避免磁带内随机读**（SSD 元数据缓存 + 读请求排序）
3. **使磁带池读写全异步**（HDD 池作为持久写缓冲 + DataBrain 批量调度）

### 关键设计

#### 1. Dedicated Drives（专用驱动器）

将 4 个驱动器静态分配：2 写 + 1 读 + 1 内部（consistency checking, EC repair, GC）。

**原因**：写是 append-only→一个磁带写满才切换→无 thrashing。内部操作长时间聚焦同一磁带→无 thrashing。读是用户触发→非确定性→不可避免需要切换→但隔离到 1 个 drive。

**写驱动固定**：MDC 保证每个 tape library 只有 2 个活跃 partition→每个写驱动 append 到固定磁带直到满。

**磁带库满后**：2 个写驱动转 1 读 + 1 内部。

#### 2. Batched Erasure Coding (b-EC)

**问题**：传统 intra-object EC 使每个对象跨度 m 盘磁带→读一个对象需要 m 个驱动器→大量 drive thrashing。

**方案**：服务层先聚合多个对象到内存（如 5 个对象共 1.5GB），创建新 PLog，单次 append 写满密封。对象在 EC stripe 内横向切割→小对象仅存在于 1-2 盘磁带上。

**效果** (12+2 EC)：大多数对象仅需 1-2 个驱动器即可读取，大幅减少 drive switching。

**代价**：降级读时重建对象需读取 m×S 数据（而非 S）。但由于降级读频率低，可接受。

#### 3. 全异步磁带池 + 批量调度

**写入路径**：
- 用户 write → HDD Pool（快速确认）→ DataBrain 按生存期（3 个月粒度）分组 → 同组对象批量 flush 到同一盘磁带 → append-only log-structured
- **效果**：同磁带上的对象大概率同时被删除→GC 时整盘磁带可直接回收，无需读写有效数据

**读取路径（Restore）**：
- 用户 restore 请求（小时级 SLA）→ DataBrain 收集同一 ddl 的任务 → 按 pt-id 分组 → 按 ⟨plog-id, offset⟩ 排序 → 逐组下发到 tape pool
- **效果**：每个磁带库收到的请求有物理局部性→减少 drive thrashing + 减少 seek

**Write buffer 作用**：HDD 池聚合带宽 > 磁带池→吸收突发写入。但更重要的是，如果没有 HDD 作为持久写缓冲，按生存期分组写入磁带是不可能的——因为有限的驱动器数量和 80s 装载时间阻止了为每个生存期组维护"随时可写"的磁带。

**容量水位线**：HDD 池维持 75% 水位→25% headroom 可吸收用户突发 + 磁带库故障时的额外写入（24h 内用户写入 < HDD 池的 4%→提供数十小时维修窗口）。

#### 4. Tape-tailored Local Storage Engine

**VDB (Virtual Database)**：利用 head server 上 2 块 NVMe SSD 构建固定-size KV store
- **MetaStore**: key=plog-id, value=256B 元数据（位置、状态）。10PB 磁带库仅需 <50GB SSD 空间
- **DataStore**: key=⟨plog-id, offset⟩, value=1MB 数据切片。缓冲写入数据。

**崩溃一致性**：固定大小 key/value → key 写入原子（<4KB）。4KB 数据带 DIF（含 plog-id + offset + checksum）→ 值可验证。扫描 key array 即可重建内存 hash table。

**Metadata Partition on Tape**：每盘磁带满后，从 MetaStore dump 元数据到磁带的 metadata partition。SSD 故障时从磁带的 metadata partition 重建，而非扫描磁带上所有 4KB 数据的 DIF。

**TLS (Tape Library Scheduler)**：
- **读排序**：将同一磁带上的 sub-PLog 按物理位置和 wrap 方向分两队，每队内按位置排序，先处理一个方向再处理另一个→减少 seek time
- **流控**：周期性读取驱动缓冲大小→估算驱动速度 DS→限速提交请求到 DS→避免驱动误判主机速度而切换到低速模式（性能退化 168MB/s→正常 336MB/s）

---

## 证据与评估

### 生产环境配置

- 部署规模：`<200` 个 tape library，每个 140PB（14 rack × 10PB）
- EC 配置：12+2，存储冗余 1.17
- 已存数百 PB 裸用户数据（2024 正式商用）
- 灰度发布：2022 年底开始，2024 正式上线

### Workload 特征

| 特征 | 数据 |
|------|------|
| 对象大小分布 | 高度偏斜：<500MB 对象占 93.81% 容量，50-100MB 占 69.95% |
| 写操作占比 | 最大客户 A: 99.999888% 写, 0.000112% 读, 0% 删除 |
| 读操作 | 5 个最大客户中，2 个从未读，最高仅 0.674776% |
| 删除 | 几乎全部由自动过期而非显式操作触发 |

### 生产性能（24h 窗口）

| 指标 | 数值 |
|------|------|
| HDD 池利用率 | 71.625%-71.675%（稳定） |
| 磁带池日均写入 | 118.81 Kops/min ≈ 831.67 GB/min（7MB stripe） |
| 磁带池写入延迟 | 中位数 18.51ms, P99 27.75ms（网络 ~10ms + SSD ~1-4ms + EC + checksum） |
| 磁带池读取 | 极低（<5.85 Kops/min） |
| 磁带池写入稳定性 | 22/24 小时在 7052-7469 Kops/h 之间 |

### 故障分析（1.25 年，<200 tape library）

| 故障类型 | 次数 | 影响 |
|----------|------|------|
| 驱动软件 bug | 4/17 | 性能退化但不影响可用性 |
| 驱动故障 | 4/17 | 写驱动→写入吞吐降；读驱动→降级读；内部→需维修 |
| 驱动不识别磁带 | 4/17 | 类似驱动故障 |
| 驱动找不到 | 1/17 | 类似驱动故障 |
| 机械臂卡住 | 2/17 | 整个 library 不可写→降级读+HDD 吸收写入 |
| 头服务器断连 | 2/17 | 同机械臂卡住 |

**关键容错设计**：HDD 池 25% headroom 可吸收 24h+ 的用户写入→磁带库完全不可用时仍有充分维修时间。

---

## 整体评估

### 真正的新意

1. **"全异步磁带池"不是简单的 staging 层——它使得批量调度（生存期分组 + 读重排序）成为可能**：有限驱动器数（每库仅 4 个）意味着同步模式下无法做任何 smart placement。HDD 缓冲池不仅是性能优化，更是**使调度策略可行的架构前提**。

2. **b-EC 用极小的工程代价（服务层聚合 + PLog offset 转换）实现了 inter-object EC 的效果**：不改持久层，不打破分层边界，只需服务层做一次批量 append——这让小对象不再跨度所有 m 盘磁带。

3. **驱动器和磁带的物理约束被精确建模并转化为软件优化**：wrap 方向感知的读排序、流控对齐驱动缓冲区速度、按生存期分组使 GC 几乎零开销。

### 优点

- 每个设计决策都有"磁带物理特性→软件优化"的完整推理链
- 生产数据详实：24h 实时吞吐、P99 延迟、故障分类——工业论文的黄金标准
- 诚实地给出了架构选择的原因（如为什么不用磁带自带的压缩——用户数据已加密）
- 故障分析部分特别有价值——1.25 年的真实 data point

### 局限与假设

- 归档 workload 极端写重读轻（最高仅 0.67% 读，多数客户 0 读）——这个假设限制了通用性
- 未讨论多 AZ 部署策略（目前单 AZ）
- b-EC 对降级读的影响（恢复需读 S×m 数据）虽有讨论但未量化为性能数字
- HDD 池的 GC 周期性触发会产生读尖峰——这是否会成为瓶颈未深入讨论
- 磁带库 ≤200 台规模——在此规模下故障率低（17 次/1.25 年），但更大规模下故障模式可能不同

### 适用条件

- 归档类 workload（写为主，读极少，小时级 SLA 可接受）
- 有磁带硬件供应链优势的云厂商
- 单个 tape library 1000 tapes 配 4 drives 是当前 tape 硬件的典型配置

### 可复用启发

1. **"物理约束→软件优化"的完整推理链**：驱动器数少→专用分派消除 thrashing；装载慢→批量调度减少切换；磁带有方向性→wrap 感知排序。每一项都是"先理解硬件的物理限制，再设计软件如何与之对齐"。

2. **"全异步 = 可调度"的新视角**：不是"异步为了不阻塞"，而是"异步创造了批量调度的可能"。类似的——DGC 的异步 GC 标记、Bodega 的 roster leases——异步不仅隐藏延迟，更打开了全局优化的窗口。

3. **"Staging buffer 不仅是性能层，更是调度可行性的架构前提"**：如果没有 HDD 持久缓冲，按生存期分组写入磁带是物理上不可行的（无法为每个生存期组维护可写磁带）。缓冲池的语义从"缓存"升格为"调度基础设施"。

4. **"Inter-object EC 用服务层 batch 替代持久层改造"**：当系统分层不允许跨层语义泄露时，在上层做 batch 可以实现下层 EC 无法做到的 inter-object striping——保持分层干净 + 实现跨对象优化。

5. **"Dedicated drives 是硬件资源静态分配的胜利"**：4 个 drive，2-1-1 分配——没有动态调度、没有抢占、没有优先级队列。有时最简单的分配方案就是最好的，尤其是当负载特征明确可预测时。

### 讨论问题

- 如果未来客户 workload 的读比例显著增加（如 AI 训练需要频繁读取归档的旧 checkpoint），当前的 1 个 read drive 设计是否足够？
- TapeOBS 的专用驱动器设计在更大的 tape library（如 Diamondback 1584 盘配更多 drive）中如何调整？
- HDD 池 GC 的周期性读尖峰是否会与用户 restore 请求竞争→是否需要为 GC 也设置驱动器隔离？
