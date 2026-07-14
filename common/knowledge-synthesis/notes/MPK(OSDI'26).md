# MPK(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-cheng.pdf
- **类型**: 论文-编译器/系统
- **一句话 TL;DR**: 首个将多 GPU 模型推理自动转换为单个 mega-kernel 的编译器+运行时——SM 级任务图 + 去中心化调度 + 跨算子软件流水线，比现有 kernel-per-operator 系统 latency 低 up to 1.7×，接近硬件极限。

## 核心问题

现有 LLM 推理系统采用 kernel-per-operator 执行模型——每个算子一个 GPU kernel。三个限制：(1) GPU 隐式 barrier 阻止跨 kernel 软件流水线 (2) 依赖只在算子粒度表达→无法做细粒度 compute-comm overlap (3) 数百个 kernel launch 开销→依赖于 CUDA Graphs 但 Graphs 是静态的→动态 workload 灵活性差。

## 关键洞察

1. **"SM 级任务图替代算子级 DAG"**：依赖在**单个 SM 粒度**表达——每个 SM 独立调度→消除 kernel barrier→实现跨算子流水线+细粒度 overlap
2. **"Mega-kernel = 单一 persistent kernel"**：整个推理作为一个 kernel 运行→消除 kernel launch 开销→去中心化 SM 调度不需要 global barrier
3. **"编译器自动 mega-kernelize"**：开发者不需要手动实现 persistent kernel——MPK 编译器自动从 tensor program 生成

- 来源：MPK(OSDI'26)

### 实践启发
- **"SM 级去中心化调度是 mega-kernel 的关键"**：类似 Ambulance 的 "protocol-rigged racing"——用细粒度本地决策替代全局同步
- **"Kernel barrier 是最被低估的性能上限"**：implicit barrier 阻止了几乎所有跨算子优化
