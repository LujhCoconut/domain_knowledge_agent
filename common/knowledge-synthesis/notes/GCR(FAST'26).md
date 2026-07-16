# GCR(FAST'26)

- **来源**: https://www.usenix.org/system/files/fast26-zeng.pdf, FAST '26
- **作者**: Shaoxun Zeng, Tingxu Ren, Jiwu Shu, Youyou Lu (Tsinghua)
- **一句话 TL;DR**: GPU 系统级 C/R 中间件——hybrid C/R(控制状态走 driver-integrated + 数据 buffer 走 interception-based) + 增量 checkpointing(CPU shadow execution + dirty template 轻量脏识别), checkpoint 延迟 -72.1% vs cuda-ckpt, restore -87.1%, 开销 <1%, 增量 checkpoint size -86.6%。

## 核心问题

GPU C/R 是弹性扩缩、任务切换、容错的基础原语。但现有两类方案各有致命缺陷：
- **Driver-integrated (cuda-ckpt)**: 零开销但数据 buffer 带宽仅 12% PCIe limit(3.0GB/s vs 25GB/s 理论)→C/R 延迟高
- **Interception-based (PhOS)**: 数据拷贝带宽高(24.3GB/s) 但控制状态序列化慢(3.5-9.2×) + API 拦截开销 8.7%(峰值49.6%)

**两者都不能同时做到**：低延迟 + 低运行时开销 + 增量 checkpointing(现有方案缺脏识别或开销太大<12%)

## 方案设计

### 1. Hybrid C/R: Control/Data Separation

- 仅拦截 `cudaMalloc`/`cudaFree`→分离控制状态和数据 buffer
- **控制状态** → driver-integrated C/R (零开销, 序列化快)
- **数据 buffer** → interception-based C/R (高带宽异步拷贝 24.3GB/s)
- **地址一致性**: 解耦虚拟/物理内存→checkpoint 前保存 GPU 页表→restore 时任意分配物理内存重映射到保存的虚拟地址

### 2. Incremental Checkpointing: CPU Shadow Execution + Dirty Templates

- 现有脏识别: 要么粗粒度(整 buffer mark dirty), 要么细粒度但开销大(PhOS 12% slowdown, 5.3× GPU slowdown)
- GCR: **kernel 在 CPU 上 shadow 执行**→并行于 GPU→移出 GPU 关键路径
- **Dirty template**: 符号执行 kernel→提取 store 指令→生成 dirty 地址/长度的表达式(以 kernel 参数为变量)→CPU 仅做微秒级计算(14µs) 且 <1MB 内存→精确定位到 instruction 级别

## 关键数据

| 指标 | GCR vs cuda-ckpt | vs PhOS |
|------|-----------------|---------|
| Checkpoint 延迟 | **-72.1%** | **-63.6%** |
| Restore 延迟 | **-54.2%** | **-87.1%** |
| 正常执行开销 | <1% | vs PhOS 8.7% |
| 增量 checkpoint size | **-86.6%** | — |
| 增量 checkpoint 延迟 | **-43.8%** | — |

## 可复用启发

1. **"Control/data 分离 = 两种 C/R 范式的最优组合"**: 不是选 driver 还是 interception→用 driver 处理小的控制状态(序列化效率高), 用 interception 处理大的数据 buffer(带宽高)。核心洞察：两种操作有截然不同的瓶颈, 需要不同的优化策略。

2. **"虚拟/物理地址解耦 → restore 无需固定物理地址"**: checkpoint 时仅保存虚拟地址(页表) → restore 时重新分配任意物理内存→remap。类似 InfiniDefrag 的"GPA 已是虚拟层→不需要 compaction, 只需 remap"。

3. **"CPU shadow execution + dirty template = 离线生成表达式→在线极轻求值"**: 不需要实际执行 kernel 的计算→仅执行 store 指令的地址计算→通过符号执行生成"地址和长度 = f(kernel_arguments)"→CPU 上只需微秒。是 dirty page tracking 的编译辅助方案。

4. **"增量 checkpointing 的前提是精确脏识别→但脏识别不能成为 GPU 执行的瓶颈"**: 移出关键路径(CPU shadow 并行)+ 极轻量化(模板化→微秒级)。

---

**已归档到**: `performance/gpu-ai-performance/`
