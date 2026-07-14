# Blowfish(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-zhang-yulong.pdf
- **全称**: Blowfish: Elastic Virtual Machine Memory for Disaggregated Memory
- **作者**: Yulong Zhang (ICT CAS & UCAS), Yilong Luo, Diyu Zhou (PKU), Quan Chen (SJTU), Mosong Zhou, Lei Zhu, Senbo Fu, Qian Peng (Huawei Cloud), Huimin Cui, Xiaobing Feng, Chenxi Wang* (ICT CAS), Tao Xie (PKU)
- **类型**: 论文-系统 (virtualization + disaggregated memory + cloud infrastructure)
- **一句话 TL;DR**: 现有 VM 内存超卖机制（balloon + swap）在冷内存回收上存在根本问题：THP 下页追踪开销大、页表频繁 remapping 导致吞吐下降。而且 swap to disk 延迟是毫秒级→VM 访问已回收冷内存时 SLO 被破坏。Blowfish 利用分离式内存（far memory over RDMA/CXL）实现 **µs 级**冷内存回收和恢复：基于半虚拟化的轻量 guest-level THP-aware 热度追踪 + hypervisor 直通跨 VM 回收路径。比 SOTA HyperAlloc 回收快 **2.48×**、恢复快 **2.14×**，在 5% 性能退化内回收比提升 **1.6-6.1×**。超过 50% 数据中心内存闲置→分离式内存再分配潜力巨大。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **Blowfish** | 基于分离式内存的弹性 VM 内存超卖框架 |
| **Far memory** | 远端服务器的空闲内存——通过 RDMA/CXL 在 µs 级访问——Blowfish 用作二级"swap"介质 |
| **THP** (Transparent Huge Page) | Linux 的透明大页——2MB 粒度 | 使 per-4KB 访问追踪失效——是现有方案的首要瓶颈 |
| **Paravirtualization-based hotness tracker** | guest 内的轻量热度追踪器——THP 感知，通过半虚拟化将冷页信息暴露给 hypervisor |
| **Cross-layer cold memory path** | hypervisor 直接回收和重新分配跨 VM 的物理内存——绕过 guest 页表修改和 IO 页表修改 |
| **Memory overcommitment** | 云服务商向 VM 分配比物理内存更多的"逻辑"内存——提高资源利用率 |
| **HyperAlloc** | SOTA 基线：VM 内存超卖系统 |

## 背景与动机

### 问题
- **超过 50% 的数据中心内存闲置**（由于 VM 放置的 bin-packing 效率问题）
- 但现有内存超卖机制在冷内存回收上有三个相互关联的问题：
  1. **THP 下的页追踪**：透明大页（2MB）掩盖了 4KB 级别的访问信号→追踪"哪个页是冷的"需要打破 THP→开销大
  2. **频繁页表 remapping**：回收和恢复冷内存需要不断修改 guest 页表和 IO 页表→CPU 开销主导
  3. **Swap to disk 是毫秒级**：访问已回收冷内存时→page fault→分配→swap back→毫秒延迟→SLO 违反
- 分离式内存的 **µs 级访问延迟**使冷内存可以作为"far memory"被透明地换出，但**现有软件栈的 overhead（3.4-6.8×）**成了新瓶颈

### Blowfish 的答案
软件栈优化以匹配硬件速度：µs 级的冷内存回收+恢复需要 µs 级的软件路径。

## 方案介绍

### 四个组件

**1. Lightweight guest-level THP-aware hotness tracker**
- 基于半虚拟化：在 guest 内核中运行轻量级追踪器
- THP 感知：在不打破 THP 的前提下追踪 4KB 页面的访问
- 将冷页信息暴露给 hypervisor

**2. Hypervisor-level dedicated cross-layer cold memory path**
- Hypervisor 直接从 guest 回收物理内存并跨 VM 重新分配
- 绕过 guest 页表修改和 IO 页表修改（传统方案的主要软件开销来源）
- 利用 guest 的丰富语义识别冷内存 + 利用 hypervisor 的全局视角进行跨 VM 重分配

**3. Far memory over RDMA/CXL**
- 冷内存通过高速互联（RDMA/CXL）换出到远端服务器的空闲内存
- µs 级延迟 vs swap to disk 的 ms 级延迟

**4. Fast restoration path**
- 访问已回收页时，从 far memory 直接恢复到本地内存
- 与回收路径对称的优化：绕过传统 swap-in 的页表重建

## 证据与评估

| 指标 | 结果 |
|------|------|
| 回收速度 vs HyperAlloc | **2.48×** 更快 |
| 恢复速度 vs HyperAlloc | **2.14×** 更快 |
| 回收比提升 | **1.6-6.1×**（在 5% 性能退化内） |
| 软件 overhead | 现有方案 3.4-6.8× higher，Blowfish 消除 |

## 整体评估

### 真正的新意
1. **半虚拟化 + hypervisor 直通路径**：guest 拥有程序语义（知道哪些页是冷的）但缺乏全局视角，hypervisor 拥有全局视角但缺乏语义。Blowfish 结合两者
2. **在不打破 THP 的前提下追踪 4KB 热度**：这是 THP 场景下内存超卖的核心难题，Blowfish 的 THP-aware tracker 首次解决
3. **"硬件速度已来，软件栈没跟上"的故事线**：disaggregated memory 的 µs 延迟使得 cold memory swapping 可行——但现有软件栈的 3.4-6.8× overhead 需要一个完整的重新设计

### 可复用启发
- "语义在 guest，控制在 hypervisor"的半虚拟化分工模式是 VM 内存管理的通用优化策略
- THP 在内存超卖场景下是一个被忽视的瓶颈——2MB 粒度掩盖了 fine-grained access pattern
- "硬件就绪→软件瓶颈暴露→软件栈重新设计"是 disaggregated memory 方向的普遍模式（类似 RamRyder、Duhu 等）
