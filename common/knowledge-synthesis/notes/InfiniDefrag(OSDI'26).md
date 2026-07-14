# InfiniDefrag(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-zeng.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 将 GPA 空间视为（几乎）无限——通过操作 GPA-HPA 映射获取连续内存，消除 guest 端内存压缩（compaction），吞吐提升 up to 2×+。

## 核心问题

虚拟化环境中大页（huge page）对性能至关重要（两态地址翻译开销），但内存碎片导致无法分配连续物理内存。现有方案——防碎片策略静态且不适应多 workload；compaction 昂贵（YCSB-Redis 吞吐 -51%, 延迟 +102%）。Guest OS 假设 GPA 空间固定有限→被迫做 compaction。

## 关键洞察

1. **"GPA 是虚拟地址——不需要 compaction，只需要 remap"**：Guest OS 以为自己管理的是物理内存，实际上 GPA 已经是被 hypervisor 再映射的虚拟层。连续 GPA 可以通过扩展 GPA 空间+更新 GPA-HPA 映射获得——不需要在 guest 端做昂贵的页迁移。
2. **"GPA 空间几乎无穷"**（57-bit address width = PB 级）→永远不会耗尽→可以无限制地分配新的连续 GPA 区域。
3. **"Memory trade"替代 compaction**：用碎片化页面换取连续内存→扩展新 GPA 区域→回收碎片→无需移动数据。

## 方案

- **Infinite Address Manager**：扩展 GPA 空间 + 回收碎片 GPA 页面
- **Host Memory Guard**：维护 GPA-HPA 映射 + 强制 HPA 使用在 VM quota 内
- **Scalability Optimizer**：扩展到多线程和多 VM

## 可复用启发
- **"多一层虚拟化 = 多一个解决碎片的机会"**：GPA 已经是虚拟层→不需要在 guest 内做 compaction。类似 Blowfish "硬件速度已来，软件栈没跟上"
- 来源：InfiniDefrag(OSDI'26)
