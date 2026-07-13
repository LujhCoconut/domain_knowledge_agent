# System-Level Performance Tuning

系统层性能调优知识与经验，涵盖 CPU、内存子系统、内核参数、NUMA 等。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| Tiered Memory 管理 | CXL, NUMA, page migration, hotness vs criticality | PACT(ASPLOS'26) |
| 内存延迟归因 | CHA/TOR, MLP, PMU counters, PEBS, stall attribution | PACT(ASPLOS'26) |

---

## Tiered Memory 管理

### 核心问题
在 DRAM + CXL/NUMA 的 tiered memory 系统中，如何决定哪些页面放在快 tier。

### 关键洞察

1. **Hotness (access frequency) 不等于 Performance Impact**：
   - 相同访问频率的页面，stall 代价可差 65×（取决于 MLP）
   - 顺序遍历（高 MLP）可隐藏延迟，指针追踪（低 MLP）完全暴露延迟
   - 启发来自 PACT §3 (violin plots), PACT(ASPLOS'26)

2. **PAC (Per-page Access Criticality) 建模**：
   - 核心公式: `LLC-stalls = k × (LLC-misses / MLP)`
   - `k` 是 per-tier 系数（捕获延迟 + 架构开销）
   - 在 96 workloads × 3 延迟配置下，Pearson > 0.98
   - 来源: PACT §4.2, PACT(ASPLOS'26)

3. **Per-tier MLP 观测**：
   - Intel: 用 CHA 的 TOR_OCCUPANCY / TOR_OCCUPANCY_COUNTER0 计算 per-tier MLP
   - AMD (无 TOR): 用 Little's Law 近似 `MLP ≈ Latency × Bandwidth`
   - 来源: PACT §4.2.2, PACT(ASPLOS'26)

4. **MLP Phase Stability**：
   - MLP 在 tens-of-ms 尺度上保持稳定
   - 这允许在短窗口（20ms）内按访问频率比例属性 stall 到各页面
   - 来源: PACT §4.3, PACT(ASPLOS'26)

### 实践启发

- **做内存性能分析时，同时看 LLC-misses 和 MLP**，不要只看 miss rate/count
- **CHA/TOR 计数器是 per-tier 流量分析的最佳观测点**，比系统级 offcore 指标信息量大
- **20ms 是一个实用的采样窗口**：perf 不支持 sub-10ms 精确计数器，20ms 足以捕捉 MLP 动态
- **默认 PEBS 采样率 1:400** 在准确性和开销之间平衡良好
- **Eager demotion**: 早期主动降级建立 headroom，成熟后降低频率。类似 TCP 拥塞控制的思路

### 相关 Workload 特征
- **MLP 方差大的 workload**（同时有 streaming + pointer-chasing）从 criticality-driven 管理获益最大
- **纯 streaming workload**: PAC ≈ frequency，hotness-based 方法即可
- **图计算 + LLM 推理**: 典型的有 MLP 方差场景，是最佳应用领域

---

## 待补充

- CXL 延迟特性与带宽模型
- NUMA 自动平衡调优
- Hugepage / THP 在 tiered memory 中的交互
- 其他平台（ARM, RISC-V）的 PMU 等价设施
