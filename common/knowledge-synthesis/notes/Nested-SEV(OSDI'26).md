# Nested SEV(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-takiguchi.pdf
- **全称**: Nested SEV: Secure and Generic SEV Support for Nested Virtualization
- **作者**: Kazuki Takiguchi, Kenichi Kourai (Kyushu Institute of Technology)
- **类型**: 论文-系统 (virtualization + security + confidential computing)
- **一句话 TL;DR**: 机密VM（AMD SEV）加密VM内存和寄存器状态防止云内部威胁——但**嵌套虚拟化场景下SEV支持严重不足**。现有方案要么无法保护L1 hypervisor（仅加密L2）、要么只能支持单个L2 VM（Hecate/OpenHCL）。Nested SEV 支持**多个**SEV保护的L2 VM运行在SEV保护的L1 VM内部，提供两层信任模型（L0+L1 untrusted 或仅L0 untrusted），通过 simulation-less multiplexing + SEV context decoupling 两个核心机制实现。三种SEV变体下性能退化 0.9%-30%。

## 重要术语解释

| 术语 | 解释 |
|------|------|
| **SEV** (Secure Encrypted Virtualization) | AMD的机密VM技术——透明加密VM内存和CPU寄存器状态+完整性保护 |
| **L0/L1 hypervisor/L2 VM** | 嵌套虚拟化的三层：L0=host hypervisor, L1=guest hypervisor, L2=guest VM |
| **SEV virtualization** | Nested SEV机制1：每个L2 VM使用独立于L1 VM的SEV context（不同加密密钥）——同时保护对抗L0和L1 |
| **SEV passthrough** | Nested SEV机制2：L2 VM与L1 VM共享SEV context——保护对抗L0但信任L1 hypervisor |
| **Emulation-less multiplexing** | 不仿真AMD-SP，而是将L1和L2 VM的SEV上下文**复用**到物理AMD-SP上——安全且高效 |
| **SEV context decoupling** | 将SEV上下文从L1 hypervisor解耦——使每个L2 VM拥有独立的加密密钥和完整性保护 |

## 背景与动机

### 问题
- AMD SEV 被广泛采用（AWS/GCP/Azure 的机密VM）
- 但 SEV 的嵌套虚拟化支持严重不足：
  - Microsoft 的补丁：仅加密 L2 VM，无法保护 L1 hypervisor → L0 可攻击 L1
  - Hecate/OpenHCL：保护 L1+L2 但仅支持**单个** L2 VM——不支持通用嵌套虚拟化的多 VM 需求
- 嵌套虚拟化在云中被广泛使用：虚拟云、测试环境、VM-in-VM 部署

### 核心挑战
- 如何在 L1 VM 内部同时保护 L1 hypervisor 和多个 L2 VM——无需仿真 AMD-SP（仿真开销太大）
- 如何支持两种不同的信任模型（L1 可信 vs L1 不可信）
- 如何管理多个独立的 SEV context（每 L2 VM 一个）而不泄漏安全边界

## 方案介绍

### 两个核心机制

**1. Emulation-less multiplexing**
- 不在不可信的 L0 hypervisor 中仿真 AMD-SP
- 将 L1 VM 和多个 L2 VM 的 SEV context **直接复用**到物理 AMD-SP
- 安全地管理 context switch——确保 L2 VM 间、L2-L1 间的加密密钥不泄漏

**2. SEV context decoupling**
- 每个 L2 VM 拥有独立的 SEV context（加密密钥、完整性元数据）
- 与 L1 VM 的 SEV context 分离
- 支持 SEV virtualization（完全解耦）和 SEV passthrough（与 L1 共享）两种模式

### 两种信任模型

| 模型 | 机制 | L0 可见性 | L1 可见性 |
|------|------|---------|---------|
| L0 + L1 untrusted | SEV virtualization (独立 context) | 加密保护 | 加密保护 |
| Only L0 untrusted | SEV passthrough (共享 L1 context) | 加密保护 | 明文访问（授权） |

## 证据与评估

| 指标 | 结果 |
|------|------|
| 性能退化 | 平均 **0.9%-30%**（三种 SEV 变体） |
| 实现 | 三种不同类型 hypervisor |
| 支持的 L2 VM 数 | **多个**（vs 现有方案仅单 VM） |

## 整体评估

### 真正的新颖性

1. **首个支持通用多 L2 VM 嵌套 SEV**：之前方案要么单 VM、要么无 L1 保护——Nested SEV 覆盖了缺失的通用场景
2. **Emulation-less multiplexing** 是一个实用 engineering 选择：不仿真 AMD-SP（避免性能惩罚和实现复杂性），而是安全地复用物理硬件
3. **两种信任模型覆盖真实部署需求**：L1 trusted（passthrough）+ L1 untrusted（virtualization）

### 可复用启发

- "复用物理硬件而非仿真"是嵌套安全虚拟化的核心性能优化——AMD-SP 仿真不可行，物理复用是关键
- Context decoupling 是嵌套系统安全的关键原则：每个嵌套层应有独立的加密上下文和安全边界
- 嵌套 SEV 填补了机密计算 + 嵌套虚拟化的交叉空白——这两个趋势各自在增长但此前互不支持
