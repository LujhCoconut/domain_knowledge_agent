# LifeLine(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-huang-jiacheng.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 对齐对象生存期与页面生存期——lifetime-based graph partitioning + lifetime-aligned GC + near-zero-copy 页重映射替代对象级复制。Android Runtime 实现，GC copy volume -57.4%，GC time -22.7%。

## 核心问题

Android ART 的 copying GC 在 compact 阶段物理移动对象消耗大量内存带宽→导致帧率下降和用户可感知卡顿。OS 支持的页重映射（page remapping——修改页表而非复制数据）可以零拷贝移动内存，但现有 GC 无法利用，因为**对象生存期和页面生存期不匹配**——同一页内混合活着和死了的对象，无法整页 remap 或释放。Generational GC 只提供粗粒度区分。

## 关键洞察

1. **"Lifetime-based graph partitioning"**：监控引用更新将对象图分为生存期相关性强的子图→类似年龄分组。不是 coarse-grained young/old 分代，而是对象级的精细生存期关联。
2. **"Lifetime-aligned GC = 将同寿命对象打包到同一页"**：使每页几乎全是活对象或全是死对象→bimodal per-page liveness→释放时大部分页可直接整页回收（zero-copy remap），仅少量混合页需要对象级复制。
3. **"Near-zero-copy GC"**：对 mostly-live 页做页重映射（修改页表，不复制数据），仅从 mostly-dead 页复制少数幸存对象→合作的 OS 机制。

- 来源：LifeLine(OSDI'26)
