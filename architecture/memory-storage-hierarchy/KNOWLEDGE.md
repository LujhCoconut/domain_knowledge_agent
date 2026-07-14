# Memory & Storage Hierarchy

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 泛化缓存一致性 (GCP) | disaggregated shared memory, lock synchronization, wait queues, variable-size cache lines, coherence protocol extension | Soul/GCP(OSDI'26) |
| 共享解聚内存对象存储 (Duhu) |CXL, pass-by-reference, immutable objects, non-temporal writes, cache coherence avoidance | Duhu(OSDI'26) |

---

## 泛化缓存一致性 (GCP)

### 核心问题
机架级计算-内存解耦中，inter-compute 链路延迟是 NUMA 的 50-500×（5-10µs vs 20-100ns）。在此延迟下，layered approach（锁算法叠加在缓存一致性之上）产生**冗余 inter-cache 通信**——每个锁操作需要多次 coherence 消息往返。即使是性能最好的锁算法，在解耦共享内存上性能退化高达 **1000×**。

### 关键洞察

1. **"同步是缓存一致性在时间和空间上的泛化"**：时间泛化 = 等待队列替代 spin-retry；空间泛化 = 可变大小缓存行适配锁结构
2. **等待队列 at coherence layer**：锁不可获取时 core 直接注册到 coherence 协议队列 → 锁释放时 coherence 通知下一个等待者——消除 spin-retry 的重复往返
3. **Model checking 验证 GCP 正确性**：在 protocol 级提供形式化保证
4. **1-2 个数量级更快的应用性能，< 8% 存储开销**：无需修改应用代码
- 来源：Soul/GCP(OSDI'26)

### 实践启发
- "不要在上层打补丁，在下层改协议"：锁瓶颈转移到 coherence protocol 层——与其优化锁算法，不如改 coherence 协议
- 等待队列替代轮询适用于任何 distributed coordination 中的重复重试场景
- 最低限度的 protocol 扩展 > 全新的 lock 算法——GCP 是对现有 coherence 协议的 minimally invasive 扩展

---

## 共享解聚内存对象存储 (Duhu)

### 核心问题
分布式数据处理框架（Ray/Spark）使用 pass-by-value：每个节点在访问前将中间对象**复制**到本地内存——造成内存、网络和 CPU 的多重浪费。CXL SDM 使 pass-by-reference（多节点直接访问共享内存中的同一份对象）成为可能——但 SDM 不提供全局缓存一致性，而 CXL 3.0 的一致性支持带有 coherence tax（按比例增加，限制可扩展性）。

### 关键洞察

1. **"不可变性 + non-temporal writes" 绕开缓存一致性**：中间对象是不可变的（只写一次）→ 创建时用 non-temporal writes → 读取前 flush cache lines → 无需硬件一致性
2. **元数据/数据分离处理**：元数据需要节点间协调（易变、低频访问）→ 分区所有权；对象数据不需要一致性（不可变、高频访问）→ 直接 load-store
3. **Duhu-Channel**：基于 SDM + 网络信号的 low-latency RPC——元数据操作的通信延迟比传统网络 RPC 更低
4. **Pass-by-reference 不仅优化现有操作，还能**fundamentally**改变操作实现**：FlexShuffle 将数据传输变为元数据重组，shuffle stage 最高 13.81× 加速
- 来源：Duhu(OSDI'26)

### 实践启发
- "不可变性 + non-temporal writes + flush-before-read" 是绕开缓存一致性的通用模式——适用于任何共享不可变数据的场景
- 元数据（需协调）+ 数据（无需协调）的分离是共享系统的核心架构模式
- Pass-by-reference 的价值远超"减少复制"：它可能**改变操作的基础实现方式**（数据搬移→指针重定向）
