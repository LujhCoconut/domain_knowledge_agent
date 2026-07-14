# FlowANN(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-zhao.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 将图搜索的 step-level 依赖解耦为 node-level 依赖——利用 discovery-expansion 时间窗口将边获取与 GPU 计算流水线化，单 GPU 支持十亿级向量搜索，比 SOTA 快 4.08-45.7×。

## 核心问题

GPU ANNS（近似最近邻搜索）比 CPU 快 200×，但 GPU 显存有限（80-96GB），十亿 scale 的图索引需 239-334 GB。现有方案将图 offload 到 CPU 内存，但 step-level 依赖（每步必须等所有前一步邻居计算完）→ GPU stall 等边获取。

## 关键洞察: Node-level Dependency

```
Step-level:  [所有节点遍历+计算] → sync → [下一步] → GPU stall
Node-level:  每节点两个阶段: discovery (作为邻居被访问) → ...多步空窗... → expansion (被选为parent遍历自己的邻居)
```

discovery-expansion 之间有足够的时间窗口→边获取可以延迟并与后续计算流水线化。

## 方案: FlowANN

- **Tiered graph**：hot 边在 GPU，有时间窗口的边 offload 到 CPU
- **异步流水线化**：GPU 计算与 CPU→GPU 边获取重叠
- 单 GPU 十亿 scale，比 SOTA 快 **4.08-45.7×** (avg), up to **172.6×**

## 可复用启发
- **"将粗粒度全局依赖解耦为细粒度局部依赖"是并行化的经典模式**——类似 BatchGen 的 attention-MoE yield、Ambulance 的 non-equivocation as race
- 来源：FlowANN(OSDI'26)
