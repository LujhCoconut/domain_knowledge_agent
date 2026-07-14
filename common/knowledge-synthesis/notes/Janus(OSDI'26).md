# Janus(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-lai.pdf
- **全称**: Janus: Cross-World, Cooperative Nested Virtualization for Secure Containers
- **作者**: Jiangshan Lai (Ant Group), Hang Huang (Alibaba Cloud & HUST), Quan Xu, Zhen Ren (Alibaba Cloud), Jia Rao, Hui Lu (UT Arlington), + Alibaba Cloud + Ant Group + HUST 联合团队
- **类型**: 论文-系统 (virtualization + cloud infrastructure + security)
- **一句话 TL;DR**: 安全容器（Kata Containers）在云 VM 上部署产生**不可避免的嵌套虚拟化**——CPU 虚拟化和三级页表管理在两层 hypervisor 之间纠缠，跨 world 同步开销、三级页表遍历成为主要瓶颈。Janus 将 CPU 虚拟化和内存虚拟化**干净地分离**：guest hypervisor 负责所有 guest world switch（通过 lightweight switcher），host hypervisor 负责所有内存翻译——消除中间页表（shadow/nested page tables），将 host 从 CPU 事件的关键路径上移除。平均性能提升显著，跨混合内存访问工作负载。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **Janus** | 跨 world 协同嵌套虚拟化架构——分离 CPU 和内存虚拟化职责 |
| **Secure container** | Kata Containers 等——每个容器运行在轻量级虚拟机（microVM）内部，提供硬件级隔离 |
| **Nested virtualization** | 安全容器 + 云 VM = 两层虚拟化（host hypervisor + guest hypervisor） |
| **EPTP** (Extended Page Table Pointer) | Intel VMX 功能——VMFUNC 指令用于无陷阱地在 EPT 之间切换 |
| **VMFUNC-based EPTP switching** | Janus 的关键技术：在 guest 和 nested-guest 地址空间之间进行无 trap 过渡 |
| **Shadow-root** | 保护 world-switch 集成的机制——允许直接更新 nested-guest 页表的同时保持隔离 |
| **In-guest virtualization exception** | 允许 guest hypervisor 只用**一次轻量级 host 交互**解决二级 fault |
| **Cross-world synchronization** | 传统设计的关键瓶颈：每次 VM transition 需要同步两层 hypervisor 之间的状态 |

## 背景与动机

### 问题
- Secure container（Kata Containers）在裸金属上部署缺乏弹性（启动慢、静态过度订阅）
- 云 VM 提供了弹性——但 Kata Containers on cloud VM = **嵌套虚拟化**
- 传统嵌套虚拟化设计将 CPU 虚拟化和内存虚拟化**纠缠在两层 hypervisor 之间**：
  - 三级页表管理（host EPT → guest EPT → nested-guest page table）
  - 需要频繁的跨 world 同步（每次 VM transition 需要 host 介入）
  - 中间页表（shadow/nested page tables）的管理开销

### 核心洞察
> CPU 虚拟化和内存虚拟化的关注点可以**干净分离**。Guest hypervisor 最了解 CPU 调度；host hypervisor 最了解物理内存。让两者在各自最擅长的领域工作，消除纠缠点。

## 方案介绍

### Janus 三个关键技术

**1. VMFUNC-based EPTP switching**
- 利用 Intel VMFUNC 指令在 guest 和 nested-guest 地址空间之间进行**无陷阱**过渡
- 不再需要 host/VMM 参与每次 VM transition
- Guest hypervisor 完成所有 guest world switch——通过 lightweight switcher

**2. Shadow-root 机制**
- 保护 world-switch 集成的完整性——防止 nested-guest 在过渡期间的攻击
- 允许**直接更新** nested-guest 的页表（不像传统设计需要通过两层页表映射）
- 消除中间 shadow/nested page tables

**3. In-guest virtualization exception handling**
- 二级 fault（由 guest OS 触发，需要 guest hypervisor 处理的 page fault）在 guest hypervisor 内解决
- 仅在最后需要**一次轻量级 host 交互**——而非传统的多次来回

## 证据与评估

| 指标 | 结果 |
|------|------|
| 整体性能 | **显著优于**传统嵌套虚拟化（Janus vs baseline 嵌套设计） |
| 关键改进 | 消除跨 world 同步、消除中间页表 |

## 整体评估

### 真正的新颖性

1. **首次将嵌套虚拟化中的 CPU 和内存虚拟化职责干净分离**：传统设计纠缠这两个关注点——Janus 把它们解耦到最合适的 layer
2. **VMFUNC 用于嵌套虚拟化的 guest-guest 过渡**：Intel VMFUNC 主要是为 in-VM 用途设计的——Janus 将它重新用于跨嵌套 guest 的过渡
3. **Shadow-root 是一个新的安全抽象**：保护 guest hypervisor 与 nested-guest 之间的交互，同时消除中间页表

### 可复用启发

- "分离关注点"是嵌套系统（不仅是虚拟化——嵌套容器、嵌套沙箱、嵌套 VMs）最强大的设计原则
- 硬件特性（VMFUNC）可以被重新用于非初始设计意图——关键在于识别其本质能力（无 trap 页表切换）
- "Remove the host from the critical path" 是嵌套虚拟化性能优化的核心原则
