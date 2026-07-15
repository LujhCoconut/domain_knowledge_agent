# Nixie(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-xu-yechen.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 消费者 GPU 的透明时间复用——每次只让一个应用的 working set 完整驻留 GPU 内存（evict/reload），利用双向 PCIe 带宽 + MLFQ 调度优先交互式应用，vs UVM 延迟降 3.8×、pinned memory 降 66.8%。

## 核心问题

消费者 GPU (RTX 4090/5090) 同时运行多个 ML 应用（LLM + diffusion + 代码补全）。每个 model 的 working set 几乎饱和 GPU 内存→同时运行超出容量。UVM 的 demand paging 假设 working set 可共存→严重 thrashing→吞吐崩溃+延迟尖峰。应用级 swap (llama-swap/Ollama) 限于单应用→无法跨应用协调。

## 关键洞察

1. **"Temporal multiplexing 替代 spatial multiplexing"**：不试图让多个模型同时驻留 GPU→每次只给一个应用完整显存→用完 evict/reload 下一个。利用 PCIe 双向带宽做快速切换。
2. **"MLFQ-inspired 调度自动识别交互 vs 批处理"**：类似 CPU 调度——交互式应用（代码补全）自动获得高优先级→减少延迟；后台批处理自动降级→不影响交互。
3. **"不需要应用或驱动修改"**：透明截获 GPU memory allocation + kernel launch→对 llama.cpp/SGLang/ComfyUI 全透明。

- 来源：Nixie(OSDI'26)

### 实践启发
- **"Consumer GPU = single-tenant datacenter GPU 的反面"**：consumer 场景是 single-user、heterogeneous、高速切换。大多数 GPU sharing 研究假设 datacenter 多租户→不适用
- **"Temporal multiplexing 在 consumer GPU 上比 UVM 更优"**：explicit swap > demand paging——当 working set >> GPU memory 时，知道"何时换入换出"比"按需 page fault"更高效
