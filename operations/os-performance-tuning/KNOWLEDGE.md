# OS Performance Tuning & Code Optimization

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| LLM 驱动的大规模代码优化 | fleet-wide profiling, embedding-based localization, anti-pattern mining, multi-stage verification | ECO(OSDI'26) |

---

## LLM 驱动的大规模生产代码优化

### 核心问题
LLM 优化代码在 benchmark 上已被证明可行，但直接应用于生产环境的百万/十亿行代码面临两个**非 ML 系统**挑战：如何找到"值得优化且 LLM 能优化"的高价值目标（opportunity localization），以及如何确保 LLM 生成的代码不引发生产事故（reliability）。

### 关键洞察

1. **"大海捞针"式的目标定位**：不是对每行代码跑 LLM → 用 fleet-wide continuous profiling 找热点 + embedding-based semantic search 匹配 anti-pattern 词典 → 精确定位 0.01% 高价值优化候选
2. **多阶段验证链**：自动测试 + LLM self-review + 部署后监控 → 99.5% commits 无回滚
3. **LLM 推理成本 vs fleet-wide 节省**：推理成本可忽略不计（比 fleet-wide CPU/energy 节省小几个量级）
4. **代码优化中的人类审查**：960 个人类评估作为质量基准，而非仅看 pass@k 或 benchmark 分数
- 来源：ECO(OSDI'26)

### 实践启发
- "不是每一个 LLM 解决的问题都是 ML 问题"——opportunity localization 和 verification pipeline 是纯系统设计挑战
- Fleet profiling + embedding search + anti-pattern dictionary 是"大海捞针"型代码优化的通用模式
- 大型团队的代码优化需要人类评估基准（960 edits），而非仅看 LLM eval metrics
- 6,400+ commits / 25,000+ lines 数字表明大规模代码优化已从"demo"进入"production"阶段
