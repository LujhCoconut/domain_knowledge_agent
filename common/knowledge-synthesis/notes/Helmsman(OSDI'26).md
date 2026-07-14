# Helmsman(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-huang-yuchen.pdf
- **类型**: 论文-运维系统 (Operational Systems)
- **一句话 TL;DR**: 小红书的 clustering-based ANNS + SSD——ANNS 专用用户态存储栈 + learned pruning + GPU 加速构建，硬件成本节省 >90%，40 台机器替代 35,000 核 + 0.35PB DRAM。

## 核心问题

Graph-based ANNS (HNSW) 在线服务必须全 DRAM 部署——内存占用 + CapEx/OpEx 爆炸。Hybrid SSD+DRAM (DiskANN) 的贪婪图遍历产生大量串行 I/O→无法满足在线 SLA。

## 方案

重新评估 **clustering-based ANNS** (SPANN)：
- 聚类无依赖→batched I/O→利用 SSD 高带宽
- **ANNS 专用用户态存储栈**→SSD 带宽利用率从 20-60% 大幅提升
- **Leveling-learned pruning**→适应变动的 top-k，避免固定策略的冗余扫描
- **GPU 加速索引构建**→十亿级索引小时级构建

## 结论

生产部署数月稳定运行，40 台机器完成此前需要 ~35,000 core + 0.35PB DRAM 的 ANNS 工作负载。

## 可复用启发
- **"Clustering vs Graph-based ANNS"的范式重评估**：SSD 硬件进步改变了旧 trade-off——clustering 的无依赖批量 I/O 恰好匹配 NVMe 高带宽特性
- **"重新审视被遗忘的方案"是系统研究的重要策略**：当硬件进步改变瓶颈时，曾被抛弃的方案可能重新变得最优
- 来源：Helmsman(OSDI'26)
