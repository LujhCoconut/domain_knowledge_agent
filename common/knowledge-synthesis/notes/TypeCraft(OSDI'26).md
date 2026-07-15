# TypeCraft(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-li-zecheng.pdf
- **类型**: 论文-系统/性能工具
- **一句话 TL;DR**: 轻量级高分辨率数据类型 profiler——将每个内存访问指令注释上其数据类型和字段。集成到 Linux perf 和 Google 数据中心 profiler。Linux 内核优化（字段重排、pointer chasing 消除）获得显著性能提升。

## 核心问题

Google 数据中心 40-60% CPU cycle 用于等待内存。现有 perf 工具（Linux perf、VTune、SCALENE）提供 code-centric（hot functions）和 data-centric（hot allocations）视图，但**缺少连接两者的桥梁**——不知道一个 hot cache miss 对应的到底是什么数据类型的什么字段。现有分析提供 "这行代码 cache miss 很多"，但不提供 "因为 struct task_struct 的 clock 字段跨越了两个 cache line"。

## 关键洞察

1. **"Type-centric profiling——不是只看代码或数据，而是看数据类型的访问模式"**：TypeCraft 注释每个内存指令与其关联的 type+field→performance profile 可以按 type 和 field 聚合。类似 Merlin "per-object characterization" 和 LifeLine "object-page lifetime alignment"——更细粒度的语义感知。
2. **"DWARF debug info→perf annotations——bridge debugging and profiling worlds"**：处理 DWARF 在优化后二进制上的质量退化（AutoFDO/LTO/BOLT 严重破坏 DWARF 精度）。TypeCraft 修正这些退化以获得高准确度类型解析。
3. **"轻量级 + 数据中心 profiler 集成"**：不增加在线数据采集负担→适合持续生产 profiling。Linux perf 上游化→可作为数据中心标准 profiler 的一部分。

- 来源：TypeCraft(OSDI'26)
