# Ambulance(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-giridharan.pdf
- **类型**: 论文-协议
- **一句话 TL;DR**: Ambulance 通过 **protocol-rigged racing**（协议操控竞速）替代 timeout 检测 BFT 慢节点——replica 之间竞速而非与时钟竞速，正常情况匹配 PBFT 延迟（3 message delays），慢节点时比 hedging 快 1.7-3.1×。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| Slowdown | 节点仍然存活且正确，但响应速度大幅低于正常水平 | BFT 协议的最大实际威胁——timeout 难以检测 |
| Protocol-rigged racing | Replica 之间通过协议步骤竞速（leader 步骤少、非 leader 步骤多），而非 race against the clock | 核心技术创新——满足 cooperative + productive 两个要求的 slowdown 检测 |
| Cooperative | 并发 proposal 不互相破坏——正确 replicas 一起推进而非互斥 | 理想 slowdown 检测的第一个要求 |
| Productive | 竞速期间的工作可以直接加速 commit——不空等 | 理想 slowdown 检测的第二个要求 |
| Proposal lane | 每个 replica 有自己的 "车道" 提交 proposal——leader lane 更快 | Racing 的实现机制 |
| Non-equivocation phase | 保证恶意 replica 不能产生冲突 commit 的阶段 | Ambulance 将其作为竞速本身——所有 replica 本就需要执行 |
| Race cutoff | Leader 不需要第一个完成，只需在 cutoff 前完成就算赢 | 偏置竞速——最大化 leader 赢面同时允许快速恢复 |
| Recovery path | Replica 认为 leader 输掉竞速后的三阶段恢复：选值→持久化→随机选 lane commit | 无 leader 时达成共识 |
| 3 message delays | Ambulance 正常情况下的延迟 | 与 PBFT 持平——latency-optimal |
| 9.5/10.5 message delays | Leader 慢时的预期延迟 | vs ParBFT2 的 22 message delays |

## 背景与动机

生产 BFT 部署面临的核心威胁不是 crash 而是 **slowdown**（慢节点）——网络配置错误、部分硬件故障、GC 暂停、磁盘 I/O 竞争等。现有三种 slowdown 检测机制各有问题：

| 机制 | 问题 |
|------|------|
| **Timeout** | 太激进→误判 leader + 昂贵的 leader 选举；太保守→系统等数秒甚至 30 秒（Diem） |
| **Cooperative/异步** | 所有 replica 都 proposal → 高通用 case 延迟和低吞吐 |
| **Hedging** (ParBFT2) | Staggered delay schedule——仍需等待 hedging delay + 协调开销大（22 message delays） |

**根本问题**：Timeout 让 leader 和时钟竞速；Hedging 用时间偏置竞速但仍需等时钟。时钟是阻塞的、非生产性的。

## 核心创新：Protocol-Rigged Racing

**Replica 之间用协议步骤竞速，而非与时钟竞速。**

### 三个关键设计

**1. 协议偏置**（leader 自然更快）：
- Leader：PBFT 的两步 non-equivocation（quadratic message exchange）
- 其他 replica：三步线性消息交换
- → 正常 leader 总是赢

**2. Cutoff 机制**（进一步偏置 leader）：
- Leader 不需要第一个完成，只需在 cutoff 前完成
- Cutoff 设计为最大化 leader 赢面 + 最小化 false negative

**3. 竞速就是 non-equivocation phase**：
- 所有 replica 本来就需执行 non-equivocation 来 commit
- 竞速期间的工作**直接可用于 commit**（productive!）
- 不需要额外的"检测"步骤

### Recovery Path

如果 replica 认为 leader 输了：

1. **Recover**：恢复可能已 commit 的 leader proposal，或自己的 lane proposal
2. **Persist**：race exclusion（可选）+ 传统持久化
3. **Random lane select**：随机选一个 lane commit（防止网络对手偏置）

### 性能对比

| 协议 | Normal case | Slowdown 恢复 |
|------|-------------|---------------|
| PBFT (timeout) | 3 msg delays | 等 timeout（秒级） |
| ParBFT2 (hedging) | ~4 msg delays | 22 msg delays + hedging delay |
| SMVBA (异步) | 高延迟 | 10 msg delays |
| **Ambulance** | **3 msg delays** | **9.5-10.5 msg delays** |

## 证据与评估

- **实现**：Rust，已部署在分布式信任公司（Sei Labs）生产环境
- **对比**：Autobahn (SOTA timeout-based)、ParBFT2 (SOTA hedging-based)

### 关键结果

| 指标 | 结果 |
|------|------|
| Normal case 延迟 | 与 Autobahn **持平**（3 msg delays） |
| Slowdown (1-2s) 峰值延迟 | 比 Autobahn 低 **1.6-3.0×** |
| 严重 slowdown | 比 Autobahn 低 **up to 10.8×** |
| 吞吐 | 比 ParBFT2 高 **1.3×** |
| Normal case 延迟 | 比 ParBFT2 低 **1.9×** |
| Slowdown 峰值延迟 | 比 ParBFT2 低 **1.7-3.1×** |

## 整体评估

### 真正的新意
1. **Protocol-rigged racing 是新的 slowdown 检测范式**：超越了 timeout（与时钟竞速）和 hedging（时钟偏置竞速但仍需等时钟），首次实现 cooperative + productive 同时满足
2. **"用 non-equivocation phase 作为竞速"**：让竞速期间的工作直接有用——所有 replica 无论如何都需要执行这一步
3. **Proposal lane + random selection**：解决无 leader 时的共识收敛

### 优点
- **正常情况零代价**：匹配 latency-optimal PBFT（3 msg delays）
- **慢节点时无空等**：replicas 的竞速工作直接可用于 commit
- **已生产部署**（Sei Labs）
- 异步网络模型（无 synchrony 假设）

### 局限与假设
- **n = 3f+1** 标准 BFT 假设
- **PKI + threshold signatures** 的信任设置
- Recovery path 的复杂性（race exclusion phase 等 corner case）

### 可复用启发
- **"用协议步骤偏置竞速"是通用设计模式**：leader 做更少步骤、非 leader 做更多步骤 → leader 自然更快 → 不需要时钟来区分快慢
- **"竞速的工作 = 必须做的工作"**：将检测机制嵌入已有协议步骤中，而非增加额外的检测逻辑
- **"Cooperative + Productive"是好的 slowdown 检测的充要条件**：这两个要求可以用于评估任何 proposed 机制
- 来源：Ambulance(OSDI'26)
