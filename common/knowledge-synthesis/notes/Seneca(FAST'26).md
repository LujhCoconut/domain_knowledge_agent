# Seneca(FAST'26)

- **来源**: https://www.usenix.org/system/files/fast26-desai.pdf, FAST '26
- **作者**: Omkar Desai (Syracuse), Ziyang Jiao (Huaibei Normal), Shuyi Pei (Samsung), Janki Bhimani (FIU), Bryan S. Kim (Syracuse)
- **一句话 TL;DR**: ML 训练数据加载系统——DSI pipeline 性能模型驱动最优缓存分区(MDP: encoded/decoded/augmented 三分区) + 机会主义采样(ODS: 优先服务已缓存数据)，makespan -45.23% vs PyTorch, 吞吐 3.45× vs 最佳 dataloader。

## 核心问题

ML 训练 DSI(Data Storage and Ingestion) pipeline 是 bottleneck——CPU 预处理吞吐远落后于 GPU 训练吞吐(gap 4.63-7.66×)。现有缓存方案未解决两个问题: (1) 三种数据形态(encoded/decoded/augmented)的 size/preprocessing trade-off→最优缓存配比未知; (2) 随机采样无视缓存内容→并发训练不共享收益。

## 方案设计

### MDP (Model-Driven Partitioning): 性能模型驱动三分区

DSI pipeline 数学建模: 输入硬件参数(T_GPU/T_CPU/B_PCIe/B_NIC) + 缓存参数(size/bandwidth) + 数据参数(sample size/inflation factor M) → 输出 DSI throughput = weighted sum of DSIE/DSID/DSIA/DSIS by hit probabilities。

用此模型搜索最优 xE:xD:xA 配比→预测不同配比的D 训练吞吐→选最高。

### ODS (Opportunistic Data Sampling): 优先服务已缓存数据

- 并发 job 共享 dataset 时，sampler 将已缓存 sample 替换未缓存 sample
- 保证: (1) 每个 epoch 每个 sample 仅被消费一次; (2) 序列仍表现为伪随机; (3) 跨 job 维持相同全局序列
- 效果: 多 job 并发时缓存效率叠加 (4 jobs → hit rate +11.81% from shared cache alone, ODS further improves)

## 关键数据

| 指标 | 结果 |
|------|------|
| Makespan vs PyTorch | **-45.23%** |
| DSI throughput vs next best | **+3.45×** |
| 缓存命中率 | 54% (vs MINIO no-eviction) |
| 多 job 并发 (in-house → AWS) | 吞吐 +28.97% |

## 可复用启发

1. **"三分区建模→选择最优缓存形态配比"**: encoded(高密度低ready) vs decoded vs augmented(低密度高ready)→最优配比取决于 cache size/CPU speed/storage bandwidth。性能模型化→可搜索最优而非猜测。

2. **"机会主义替换→让缓存内容引导采样而非反之"**: 传统采样→缓存被动适应; Seneca 反过来→采样"看到"缓存中有什么→优先消费已缓存数据。前提: 训练对"具体哪个 sample 先被消费"不敏感——仅需伪随机+每个 epoch 唯一。

3. **"并发共享同一 dataset→缓存 hit 叠加"**: 多 job 独立预处理→大量重复→共享缓存+ODS→job 之间互相 warm cache。

## 归档建议

已归档到 `performance/gpu-ai-performance/`。
