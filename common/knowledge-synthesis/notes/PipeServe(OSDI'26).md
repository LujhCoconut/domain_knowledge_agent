# Pipeline Parallelism Revisited(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-hwang.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 重新评估流水线并行在 LLM serving 中的价值——动态 chunk size + delay scheduling 消除 pipeline bubbles，在 PCIe 互联的 commodity GPU 上比张量并行更优。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| Tensor Parallelism (TP) | 按矩阵列切分到多 GPU，每层部分计算 + all-reduce | NVLink GPU 的标配——但 PCIe 上通信成为瓶颈 |
| Pipeline Parallelism (PP) | 按模型深度切分，microbatch 流水线通过各 stage | 通信量远小于 TP——但 online serving 下 pipeline bubbles 严重 |
| Chunked-prefill | 将长 prefill 分割为固定大小 chunk | 减小 prefill 引起的 stage 间不平衡 |
| Greedy chunk sizing | 动态填充 chunk 到最大允许大小 | 减少固定小 chunk 的吞吐损失 |
| Predictive chunk sizing | 基于未来请求预测最优 chunk 大小 | 前瞻性优化——比 greedy 更智能 |
| Delay scheduling | 延迟 decode 请求的调度以平衡 stage 负载 | 进一步消除 decode-heavy 场景的 pipeline bubbles |
| Pipeline bubble | 某 stage 等待上游或下游完成而产生的 GPU 空闲周期 | 核心消除目标 |

## 核心问题

TP 已成为 LLM serving 标配——但仅在 NVLink GPU 上有效。大多数 commodity GPU（PCIe 互联）上 TP 的 all-reduce 通信成为瓶颈。PP 通信量远小于 TP，理论上更高吞吐——但 **online serving 下 pipeline bubbles 严重**：请求到达时间不确定 + 输入长度可变→各 microbatch 计算量差异大→stage 间等待。

## 关键洞察

1. **"PP 的通信优势在 PCIe GPU 上被低估，但 bubbles 问题被低估"**：PP 每步仅传 activation（小），远小于 TP 的 all-reduce（大）。但 online workload 的动态性使固定调度产生大量 bubbles。
2. **"动态 chunk 大小 = 用更少 bubbles 实现同吞吐"**：Greedy 填充 chunk 到最大允许→减少碎片。Predictive 利用未来请求信息→更智能。
3. **"Delay scheduling 重平衡 decode 负载"**：延迟部分 decode 请求→将过载 stage 的工作移到后续 microbatch→进一步消除 bubbles。

- 来源：Pipeline Parallelism Revisited(OSDI'26)

### 实践启发
- **"PP 在 PCIe GPU 上值得重新评估"**：类似 Helmsman "clustering strikes back"——硬件条件变化改变了旧 trade-off
- **"动态调度 > 静态 pipeline schedule"**：online serving 需要 adaptive scheduling——固定 schedule 无法处理负载变化
