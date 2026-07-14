# Twill(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-soi.pdf
- **类型**: 论文-编译器/系统
- **一句话 TL;DR**: 将 SWP + WS 联合优化形式化为约束求解问题——Twill 自动推导最优调度，证明 FlashAttention 手工优化在 Hopper/Blackwell 上已是最优。

## 核心问题

Tensor Core GPU 的各代架构差异巨大（数据放置、线程需求、异步执行模型变化）。每个程序在不同 GPU 代际上需要不同的最优调度→手工优化不可移植。现有方法（heuristic 编译 + human intuition）脆弱且无最优性保证。

## 关键洞察

1. **"SWP + WS 联合形式化为约束优化问题"**：软件流水线和 warp 特化不是两个独立变换——应作为单一优化问题求解。Twill 用现成的约束求解器求解→无 heuristic→保证最优。
2. **"约束求解器自动推导最优调度"**：与传统编译器的 heuristics-based 方法不同——Twill 穷举解空间（表达为约束）→解出全局最优。
3. **"证明专家手工优化已是最优"**：Twill 重新发现 FlashAttention 的 Hopper 和 Blackwell 手工调度→证明这些手工优化是不可再优化的。

- 来源：Twill(OSDI'26)

### 实践启发
- **"约束求解替代 heuristics"是编译器优化的通用方法论**：当搜索空间足够大时，heuristic 几乎必然次优。表达为约束→求解器找到全局最优
- **"跨代移植 = 重新求解"**：新 GPU 架构只需要更新约束→求解器自动产生新调度
