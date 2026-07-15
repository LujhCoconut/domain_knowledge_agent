# Mimesys(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-kim-donghyun.pdf
- **类型**: 论文-系统/测试
- **一句话 TL;DR**: 扩散模型将资源使用 trace 反向映射到可执行 stressor 组合——state-aware conditioning 捕获时间动态 + execution-driven alignment 用反馈替代 ground-truth labels，trace 相似度比基线高 5.5×，contention 下性能复现准确度高 2.6×。

## 核心问题

测试应用在真实资源争抢下的行为需要生产 workload——但因隐私/产权无法获取。现有替代方案：(1) 简单 stressor 无法捕获时间动态和多资源交互 (2) benchmark suite 覆盖有限 (3) per-app profiling 太昂贵。**Can we reverse-engineer executable workloads from resource usage traces?**

## 关键洞察

1. **"Diffusion model 学习 trace→stressor composition 的逆映射"**：不是合成 trace（已有方式）而是合成可执行 workload 来生成这些 trace。这是从 trace 到程序的 infer——比 trace 生成更难。
2. **"State-aware conditioning"**：生成以目标 trace + 先前系统状态为条件→捕获时间依赖关系。不是生成单个点的 resource usage，而是生成一个符合系统状态转移的序列。
3. **"Execution-driven alignment"**：直接用执行反馈对齐模型到真实应用模式——不需要 ground-truth labels。类似 RLHF 但应用于 workload synthesis。
