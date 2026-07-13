# mwait-sched(OSDI'26)

- **来源**: OSDI '26 (Operational Systems Track), osdi26-wang-yun.pdf
- **全称**: What Are You (M)Waiting For: The Hidden Cost of Idle in the Hyperscale Cloud
- **作者**: Yun Wang (SJTU), Xingguo Jia, Ben Luo, Kenan Liu, Shengdong Dai, Jingdong Han, Weihao Chen (Alibaba), Yicheng Gu, Xingzi Yu (SJTU), Yibin Shen, Jiesheng Wu (Alibaba), Zhengwei Qi*, Haibing Guan (SJTU)
- **类型**: 论文-系统 (Operational Systems — cloud infrastructure)
- **一句话 TL;DR**: `mwait-passthrough` — 将 guest 的硬件 idle 直接透传到底层 — 在 1:1 场景下完美（消除 VM exit），但在**超卖场景下灾难性地失效**：hypervisor 无法观察到 mwait idleness，导致 idle vCPU 霸占 pCPU 不放，引发 steal time 飙升、tail latency 退化 +3×、跨区域 SLO 告警。mwait-sched 用确定性 timer 仿真 + 细粒度 idle-interval classification + 可扩展多地址 mwait-proxy 解决。9 个 workload 下 P99 latency **-30~50%**，steal ratio **-30~40%**，生产部署在 Alibaba 3.2M pCPU 的集群中。

## 核心问题

`mwait-passthrough` 的双面性：
- **1:1 场景**: 完美 — guest 直接发起硬件 idle → 零 VM exit → bare-metal-like latency
- **超卖场景**: 灾难 — hypervisor 看不到 vCPU 的 mwait idleness → vCPU 永不 yield pCPU → idle vCPU 垄断核心 → 同物理核心上的其他 vCPU 被饿死

**生产数据** (Figure 1):
- 三个区域平均 CPU 利用率仅 ~5-10% — 但超卖被限制在 ~1% — 为什么？
- 因为 mwait-passthrough 在更高超卖比下产生**大量 steal events** 和 **SLO 告警**
- 即使同核心上有 idle vCPU 在 mwait，colocated tail latency 仍**升高 3×**

## 方案: mwait-sched

三个组件：

| 组件 | 机制 |
|------|------|
| **Deterministic timer-based emulation** | 用定时器精确模拟 mwait 的 idle 时长语义，而不丢失 hypervisor 对 idle 的可见性 |
| **Fine-grained idle-interval classification** | 分类 idle 间隔为短期（spin-wait style）vs 长期（deep sleep）→ 不同策略 |
| **Multi-address mwait-proxy** | 可扩展的 mwait 地址代理，恢复 idle visibility 而不引入频繁 VM exits |

## 证据与评估

| 指标 | 改善 |
|------|------|
| P99 latency (9 workloads) | **-30~50%** |
| Steal ratio | **-30~40%** |
| 高竞争 steal 事件 | 显著减少 |
| 部署规模 | Alibaba ~**3.2M pCPUs** |

## 可复用启发

- "passthrough" 优化在 1:1 场景下是 win，但在超卖场景下需要小心 — 核心问题是 **hypervisor visibility 的丧失**
- Steal time 不一定是"被其他活跃 VM 抢"，"被 idle VM 占着 pCPU 不放"是另一个被忽视的来源
- 用可扩展代理 + 定时器仿真来恢复可见性，是替换硬件 passthrough 的实用中间路径
