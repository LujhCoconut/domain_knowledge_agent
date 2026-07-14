# Duhu(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-men.pdf
- **全称**: Duhu: Shared Disaggregated Memory for Distributed Data Processing Frameworks
- **作者**: Qiutong Men, Tao Wang (NYU), Jongryool Kim, Hane Yie (SK hynix), Emmanuel Amaro (Microsoft), Marcos K. Aguilera (NVIDIA), Aurojit Panda (NYU)
- **类型**: 论文-系统 (distributed systems + CXL shared memory)
- **一句话 TL;DR**: 现有分布式数据处理框架（Ray/Spark）要求每个节点在本地内存中**复制**中间对象（pass-by-value）→浪费内存、网络和 CPU。CXL 共享解聚内存（SDM）使 pass-by-reference 成为可能：多节点直接通过 load-store 访问同一份数据。但 SDM 不提供全局缓存一致性。Duhu 通过不可变对象 + non-temporal writes + 元数据分区所有权 + Duhu-Channel 低延迟 RPC，消除了 pass-by-value 的复制开销而不需要全局一致性。Shuffle 作业完成时间提升最高 **3.39×**，单个 shuffle stage 最高 **3.59-13.81×**。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **Duhu** | SDM-based pass-by-reference 对象存储——替代 DDF 中传统的 pass-by-value 复制 |
| **Pass-by-value** | 当前 DDF 的默认范式：节点在访问前必须将对象复制到本地内存 |
| **Pass-by-reference** | Duhu 的范式：多节点通过 CXL load-store 直接访问 SDM 中的同一份对象 |
| **SDM** (Shared Disaggregated Memory) | CXL/OpenCAPI 连接的共享内存池——多节点可同时访问 |
| **Non-temporal writes** | 写入时绕过 CPU 缓存——确保 SDM 中的对象是始终一致的版本 |
| **Cache coherence tax** | CXL 3.0 支持全局一致性，但按比例增加的开销限制了可扩展性——Duhu 回避 |
| **Duhu-Channel** | 基于 SDM + 网络信号的 low-latency RPC 机制——用于元数据操作的节点间通信 |
| **FlexShuffle** | 由 Duhu 的 pass-by-reference 语义解锁的新 shuffle 方法——仅重组元数据，无物理数据传输 |

## 背景与动机

### 问题
- DDF（Ray、Spark 等）中的中间数据是不可变对象——被写一次，被消费一次或多次
- 当前所有框架使用**pass-by-value**：每个节点在访问前将对象复制到本地内存
- 这导致：内存浪费（同一对象多份副本）、CPU 开销（序列化/反序列化）、网络开销（传输）、带宽开销
- Pass-by-reference（多节点直接访问共享内存中的同一份对象）在理论上可消除所有这些开销

### 为什么 SDM 不能直接被 DDF 使用
- 新兴的 CXL-based SDM 集群提供**弱一致性**（无全局缓存一致性）
- CXL 3.0 虽支持全局缓存一致性，但有 **coherence tax**（按比例增加，限制可扩展性）
- Duhu 的定位：在**不依赖全局缓存一致性**的前提下，使用 SDM 实现 pass-by-reference

## 方案介绍

### Duhu 的五个关键设计

**1. 不可变对象 + Non-temporal writes 消除数据访问一致性需求**
- 对象是不可变的（只写一次）
- 写入时使用 non-temporal writes 直接写入 SDM（绕过 CPU 缓存）
- 读取前 flush 对应 cache lines —— 确保 reader 看到一致版本

**2. 元数据分区所有权消除跨节点竞争**
- 将 SDM 划分为段，每个段有一个 owner 节点负责排序和执行元数据操作
- 元数据是易变的（访问模式变化），但对象数据是不可变的——通过分离处理来降低协调开销

**3. Duhu-Channel：基于 SDM 的低延迟 RPC**
- 元数据操作需要节点间通信
- Duhu-Channel 使用 SDM 传输 RPC 请求/响应 + 网络信号通知对方
- 比传统网络 RPC 延迟更低

**4. Reference counting 替代垃圾回收**
- Pass-by-reference 场景中，传统 per-node GC 不安全（因为多节点共享同一份数据）
- Duhu 追踪哪些节点引用了对象，仅在安全时释放

**5. FlexShuffle**
- 由 Duhu 的 pass-by-reference 语义解锁的新型 shuffle 方法
- 将 shuffle 的物理数据移动替换为仅重组元数据——无数据传输

## 证据与评估

| 指标 | 结果 |
|------|------|
| Shuffle JCT 提升 | 最高 **3.39×** |
| 单 shuffle stage 提升 | **3.59-13.81×** |
| TPC-H (Modin on Ray) | **1.08×** |
| 测试床 | 4 节点 + CXL-attached 内存池（SK hynix 原型） |

## 整体评估

### 真正的新意
1. **首次在无硬件缓存一致性的 SDM 上实现 pass-by-reference 的 DDF 对象存储**：用不可变对象 + non-temporal writes + flush-before-read 消除了对硬件一致性的需求
2. **元数据/数据分离处理**：元数据需要协调（易变且低频访问），数据不需要（不可变且高频访问）——分工避免了不必要的开销
3. **FlexShuffle** 展示了 pass-by-reference 的 transformative 可能性：shuffle 从"移动数据"变为"重组指针"

### 可复用启发
- "不可变性 + non-temporal writes" 是绕开缓存一致性问题的通用模式——适用于任何共享内存场景
- 元数据（需一致性）+ 数据（无需一致性）的分离设计是共享系统的重要架构模式
- Pass-by-reference 在分布式计算中的潜力不仅是优化现有操作，还可能**fundamentally 改变某些操作的实现方式**（如 FlexShuffle 将数据传输变为元数据重组）
