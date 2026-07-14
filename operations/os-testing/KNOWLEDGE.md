# OS Kernel Testing & Debugging

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| CPU 调度器测试 | deterministic replay, coverage-guided fuzzing, semantic/policy bugs, scheduler characterization | kSTEP(OSDI'26) |

---

## CPU 调度器确定性测试

### 核心问题
Linux 调度器极其复杂但测试严重不足：开发者依赖长期运行负载而非系统性 corner case 测试。对 232 个真实调度器 bug 的表征揭示 73% 是静默的（无 panic）、75% 是语义错误、45% 存活超过一年。

### 关键洞察

1. **"静默 bugs 是多数"**：仅 27% 自我报告（panic/warning），大多数调度器错误表现为无 trace 的 subtle 行为偏差
2. **确定性 + 隔离 = 可调试性**：单独隔离 CPU 不够（噪声还在），单独确定性不够（OS 复杂度不可控）→ 两者组合产生 noise-free traces
3. **Coverage-guided fuzzer 在 OS 内核调度器上可行**：传统认为是禁区（太慢、太复杂）
4. **"先表征问题域，再设计工具"的研究范式**：232 bug study → 12 findings → 工具设计
- 来源：kSTEP(OSDI'26)

### 实践启发
- 表征研究本身有独立价值：定量了解"bug 到底长什么样"是工具设计的前提
- 静默 bugs（silent semantic faults）是内核子系统中被最严重低估的问题
- Coverage-guided fuzzing 与确定性重放的组合是测试复杂状态系统（尤其是 OS 内核）的通用模式
