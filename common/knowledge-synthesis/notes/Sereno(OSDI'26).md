# Sereno(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-xin.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 移动端 LLM 推理的内存带宽不对称干扰——NPU 继承 ISP 的硬件级内存优先级使 LLM 霸占带宽→前台 jank +153%。Sereno 复用 speculative decoding 的 yield point 做抢占式执行，动态让出带宽，jank -92.6%，LLM 吞吐 +67.9%。

## 核心问题

移动 SoC 的统一内存架构中 NPU 继承 ISP 的高内存优先级（传统保护媒体任务的硬件设计）→ LLM 推理无意中获得了 dominant 带宽→前台 UI 渲染的帧率被严重破坏（jank rate +153%），但 LLM 本身吞吐几乎不受影响（仅 -1.01%/1.64%）——严重的**不对称干扰**。

## 关键洞察

1. **"Asymmetric interference from legacy hardware prioritization"**：根本原因不是软件调度——NPU 的硬件级内存优先级是为视频录制等实时媒体任务设计的→在系统资源仲裁中无意中让 LLM 推理压倒了前台 UI。
2. **"Speculative decoding = fine-grained preemption points"**：推测解码中每个 token speculation 步骤提供天然的 yield 点→检测内存争抢→动态让出带宽给前台→不丢失推理进度（重放 last tokens 即可恢复）。
3. **"不修改硬件解决硬件级问题"**：通过软件层面的带宽感知抢占→在现有移动 SoC 上工作。

- 来源：Sereno(OSDI'26)
