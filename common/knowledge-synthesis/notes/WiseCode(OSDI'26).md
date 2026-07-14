# WiseCode(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-cai.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 首个实用的宽条带矢量纠删码——template-unfold 结构避免 sub-packetization 爆炸 + repetition-minimized 系数搜索 + 两阶段编解码，~100 宽条带、1.04-1.06× 存储开销，修复吞吐比 Google UCLRCs 高 1.41-2.18×。

## 核心问题

宽条带纠删码（n≈100）在极低存储冗余下提供高可靠性，但矢量码（理论上同时在 repair traffic 和 storage overhead 上最优）面对三个可扩展性障碍：(1) sub-packetization 爆炸（Clay code n=104 需 α=426）(2) 系数搜索成本过高 (3) 编解码算法复杂度过高。

## 方案

1. **Template-unfold 结构**：避免 sub-packetization 随 n 指数增长
2. **Repetition-minimized 系数搜索**：大幅降低搜索成本
3. **两阶段编解码算法**：高效处理宽条带

## 评估

- Ceph 集成，~100 宽条带，1.04-1.06× 存储 overhead
- 修复吞吐比 Google UCLRCs 高 **1.41-2.18×**（同等存储开销下）
- 在 2% 更低存储开销下仍保持更高吞吐

## 可复用启发
- 来源：WiseCode(OSDI'26)
