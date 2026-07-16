# Latte(FAST'26)

- **来源**: https://www.usenix.org/system/files/fast26-yang.pdf, FAST '26 (24th USENIX Conference on File and Storage Technologies), February 24–26, 2026, Santa Clara, CA
- **作者**: Leping Yang (SJTU), Yanbo Zhou (Alibaba), Gong Zeng (Alibaba), Li Zhang (Alibaba), Saisai Zhang (Alibaba), Ruilin Wu (Alibaba), Chaoyang Sun (Alibaba), Shiyi Luo (Alibaba), Wenrui Li (Alibaba), Keqiang Niu (Alibaba), Xiaolu Zhang (Alibaba), Junping Wu (Alibaba), Jiaji Zhu (Alibaba), Jiesheng Wu (Alibaba), Mariusz Barczak (Solidigm), Wayne Gao (Solidigm), Ruiming Lu (SJTU), Erci Xu (SJTU*), Guangtao Xue (SJTU)
- **一句话 TL;DR**: 阿里云三代本地存储栈的演进回顾（Espresso→Doppio→Ristretto）+ 提出本地-云盘混合存储 Latte，利用 ML 调度实现近物理性能+高可用+低成本（EBSX 的 1/5-1/10 价格）。
- **资料类型**: 论文-系统（工业经验+PoC）

---

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| Local Storage / Ephemeral Storage | 物理直连计算服务器的 SSD，通过虚拟化暴露为 VM 的虚拟磁盘 | 本文的核心研究对象 |
| SPDK | Storage Performance Development Kit，Intel 开源的用户态存储栈 | Espresso 的基础框架 |
| vhost-user | KVM 虚拟化中用于用户态 virtio 处理的进程 | Espresso 数据面的核心组件 |
| SR-IOV | Single Root I/O Virtualization，将一个 PCIe 设备虚拟化为多个 VF | Doppio/Ristretto 硬件虚拟化的基础 |
| DPU | Data Processing Unit，专用数据处理单元（本文中=ASIC 卡） | Doppio 的核心硬件 |
| ASIC | Application-Specific Integrated Circuit，专用集成电路 | Doppio 的计算载体 |
| SoC | System-on-Chip（本文中=ARM Cortex-A72, 4核, 64GB DRAM） | Ristretto 的灵活计算载体 |
| MSI | Message Signaled Interrupts，硬件中断 | Doppio/Ristretto 绕过软件中断的机制 |
| EBS / EBSX | Elastic Block Storage，阿里云弹性块存储；EBSX=高性能版（PMem+100Gbps） | Latte 的远程存储后端 |
| CSAL | Solidigm Append Cache，基于 SPDK 的存储加速框架 | Latte 的实现基础 |
| S3-FIFO | 三队列 FIFO 缓存淘汰算法 | Latte 缓存管理策略 |
| L2P | Logical-to-Physical address mapping | Latte 中追踪数据位置的核心结构 |
| VD | Virtual Disk | 租户可见的虚拟磁盘 |

---

## 背景与动机

### 本地存储在云中的地位

- AWS (I4i instances)、Azure (Lsv3-series)、Alibaba 均提供本地存储服务
- 本地存储通常是直连 SSD，性能接近物理盘（延迟仅差几 µs）
- 典型场景：CDN 缓存、大数据分析的中间结果、AI 训练 checkpoint

### 核心矛盾

1. SSD 硬件快速演进：IOPS 从 500K→1.5M（3×），吞吐从 3GB/s→6GB/s（2×）——但软件栈跟不上
2. 本地存储固有缺陷：弱可用性（单盘故障 → 小时级服务不可用）、弱弹性（容量受单 SSD 限制）、弱可访问性（物理绑定 → 区域部署受限）
3. 高性能 EBS（如 EBSX）可解决上述问题但价格是本地盘的 ~20×

---

## 三代本地存储栈

### 第一代：Espresso (SPDK-based, 2017)

**架构**：将存储栈从内核态移到用户态，利用 SPDK + vhost-user + polling mode + per-core 专有线程。

**关键变更 vs 内核栈**：
- 消除三类 context switch：VM_Exits（guest↔host）、system calls、interrupts
- 软件开销降低 **82.35%**
- 单机 12× PCIe Gen3 NVMe SSD → 38.4 GB/s 吞吐 + 5,760K IOPS

**三个软件局限 (SWL_1-3)**：
- SWL_1: 不支撑裸金属实例（host CPU 核被 SPDK 线程独占）
- SWL_2: CPU 利用效率低（P99 实际利用率 < 60%，但因突发 I/O 不可预测无法混部）
- SWL_3: 无法完全消除 context switch（I/O 完成后 eventfd 通知 VM 仍需 VM_Exit → 5-12µs 额外延迟）

**部署规模**：数千台物理服务器（2017-至今）

### 第二代：Doppio (ASIC DPU Offloading, 2019)

**架构**：使用商用 ASIC-based DPU（128KB SRAM, DMA engine, 16× PCIe Gen3 lanes），每 DPU 管理 2 块 NVMe SSD。DPU 将 SSD namespace 注册为 VF 并直通给 VM。

**关键收益**：
- 零 host CPU 使用（bare-metal ready，解决 SWL_1-2）
- SR-IOV + 硬件中断（MSI）替代软件中断（缓解 SWL_3）→ 接近物理性能

**两个硬件局限 (HWL_1-2)**：
- HWL_1: 跟不上 SSD 演进——ASIC 迭代慢于 SSD 代际更新，单 DPU 最多 1.3M IOPS（Gen4 SSD 可达 1.5M+）
- HWL_2: 固定硬件逻辑无法支持云新兴特性（LVM、ZNS）

**部署规模**：数千节点（2019-2021）

### 第三代：Ristretto (ASIC+SoC Co-design, 2023)

**架构**：PCIe 扩展卡上有 ASIC + ARM SoC（4× Cortex-A72 @ 2.50GHz, 64GB DRAM），32× PCIe Gen4 lanes。ASIC 模拟 NVMe 控制器（>1000 VF）+ DMA 路由；SoC 运行 SPDK + block abstraction layer 提供灵活云特性（LVM、FTL for ZNS）。

**关键创新**：
- ASIC → 快速路径（NVMe command 封装、DMA 路由、MSI 注入）
- SoC → 灵活路径（block-level I/O 处理、LVM、host-side FTL）
- 多队列并行：每个块设备分配匹配 VM NVMe 队列数的虚拟队列

**性能**：
- 单 VD: 900K IOPS (read), 6.7 GB/s throughput
- 8 VD 合计: 7.2M IOPS, 48 GB/s throughput
- 相比 Doppio: 80% per-VD IOPS 提升，支持云特性

**仍存三个本地盘局限 (LDL_1-3)**：
- LDL_1: 可用性不足（单盘故障 → 小时级不可用，需用户自行跨节点迁移数据）
- LDL_2: 弹性不足（容量受单盘限制，LLM checkpoint/KV cache 场景需弹性伸缩）
- LDL_3: 可访问性受限（仅在有 1K+ 盘需求的大客户区域部署，否则利用率太低）

**部署规模**：数千节点（2023-至今）

---

## Latte: 本地-云盘混合存储（未来方向）

### 动机

Ristretto 的三大局限（可用性/弹性/可访问性）恰是 EBS 的固有优势。但 EBSX 价格是本地盘的 20×。**思路：不放弃本地盘，而是用本地盘做高性能缓存 + 标准 EBS 做可靠后端——综合性能接近 EBSX，成本仅 1/5-1/10。**

### 架构设计

基于 CSAL (Solidigm Append Cache) 框架，用 Ristretto 替代 Optane 作为前端缓存，用标准 EBS 替代 QLC SSD 作为后端。

**三个定制化改进**：

1. **ML-based I/O Dispatcher（写入路径）**：
   - 模型：Linear SVM（边界学习 + 200ns 推理延迟，可忽略）
   - 输入：滑动窗口的 cache/backend 延迟、I/O size、QD（5×6 → 30 个权重，< 1KB）
   - 输出：二分类（forward to cache vs backend）
   - 模型重训练：每 60s 统计延迟方差 > 阈值（10%）→ 用最近 trace 重训练，~5s 完成

2. **S3-FIFO 缓存管理（读取路径）**：
   - 三队列结构（candidate queue → main cache → ghost queue）
   - 首次 read miss → 记录到 candidate queue（仅元数据）
   - 第二次访问才 promote 到 cache → 过滤 "one-hit-wonder"（占 trace 的 72%）
   - 缓存命中率 > 82%（真实在线 trace）

3. **Append-only write ordering**：
   - 写入缓存和后端刷新均走 append-only 模式
   - 两者顺序在 compaction 期间保持一致 → 避免 write-back 的 out-of-order 和 inconsistency

### 关键数据（7.2-7.4 评估）

| 指标 | Ristretto | EBSX | Latte (75% hit) |
|------|-----------|------|-----------------|
| Read IOPS | 949K | ~800K | >1M (利用双路径) |
| Read BW | 6.7 GB/s | 6.0 GB/s | 8.9 GB/s (双路径) |
| Write BW | ~6.5 GB/s | ~6.0 GB/s | 7.8 GB/s |
| 月度价格 (4TB) | 1× (基准) | 19× | 2.1-4.0× (auto-scale) |

**MySQL SysBench**：Latte 在 write-only 场景甚至超越 Ristretto（利用 ML dispatch + bypass 双带宽）。

**Trace Replay**（三个生产 trace，各 1-2.5TB）：读命中率 82.8-90.23%，延迟显著低于标准 EBS，写延迟接近本地盘。

---

## 整体评估

### 真正的新意

1. **工业经验论文的稀缺价值**：三代本地存储的完整演进（2017-2023）——包括具体的 CPU 利用率、context switch 测量、DPU 瓶颈量化——这种跨越多年的生产数据极为罕见
2. **"用本地盘做缓存+EBS 做持久层"的组合定价模型**：不是简单的 tiered storage 变体，而是**商业可行性驱动的架构创新**——关键在于 auto-scale IOPS 使价格从 13× 降至 2.1-4.0×
3. **ASIC+SoC co-design 的"快路径+慢路径"分工**在存储领域的应用

### 优点

- 每个设计决策都有量化数据支撑（82.35% 软件开销降低、60% P99 CPU 利用率、ASIC 仅 1/20 的 SoC 成本等）
- 诚实地列出了每一代的局限，不回避失败（如 Doppio 的 PCIe Gen3 通道瓶颈）
- Latte 的成本分析是实用的——不是单纯的性能比较，而是性能/价格综合

### 局限与假设

- Latte 目前是 PoC（未生产部署），所有数据来自实验环境
- QoS 问题未解决：一个本地盘被多个 Latte 实例共享时，突发 I/O 竞争如何隔离？
- ML dispatcher 的泛化性未知：linear SVM 在极端 workload 下的行为未充分测试
- 写缓存模式下的数据丢失风险（unflushed data on disk crash）——虽然给出 O_DIRECT/O_SYNC write-through 选项但损害性能

### 适用条件

- 需要高性能但又能接受本地盘故障风险的场景（CDN、大数据中间结果、AI checkpoint）
- 对价格敏感但又不愿牺牲太多性能的用户
- 有足够 EBS 基础设施的云厂商

### 可复用启发

1. **"Context switch 是存储栈性能的第一杀手"**：从内核→用户态→硬件 offload 的主线就是消除 context switch——VM_Exit → 系统调用 → 中断 → 软件中断——每一步消除都带来可测量的性能提升
2. **"ASIC 做快路径，SoC 做灵活路径"是硬件 offload 的通用模式**：不仅适用于存储（网络 SmartNIC、安全 enclave 都类似）
3. **"ML-based per-I/O dispatching 用轻量级模型（SVM, 200ns）替代启发式规则"**：模型简单到可以 per-I/O 执行——这是关键设计选择
4. **"S3-FIFO 过滤 one-hit-wonder"**：72% 的对象只被访问一次——candidate queue 机制用极低成本避免了缓存污染
5. **"Append-only 保持写顺序"**：两个独立路径的一致性由统一的 append-only 语义保证——而非复杂的分布式事务
6. **"价格是系统设计的一等公民"**：Latte 的 auto-scale IOPS 将价格从 13× 降到 2.1-4.0×——没有这一价格优化，架构再优雅也无法落地

### 讨论问题

- 如果未来的 CXL 3.0+ 共享内存使 disaggregated storage 的延迟降到 1-2µs，本地存储的 "near-physical performance" 优势还存在吗？
- ASIC+SoC co-design 在 FPGA 替代方案面前的经济性如何？FPGA 兼具 ASIC 的性能和 SoC 的灵活性，但功耗和 CapEx 更高——文中提到但未量化
- Latte 的 ML dispatcher 如果被攻击者投毒（污染 I/O pattern），是否会导致性能退化甚至 DoS？
