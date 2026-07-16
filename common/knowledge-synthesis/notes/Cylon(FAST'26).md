# Cylon(FAST'26)

- **来源**: https://www.usenix.org/system/files/fast26-yoon.pdf, FAST '26
- **作者**: Dongha Yoon, Hansen Idden, Jinshu Liu, Berkay Inceisci, Sam H. Noh, Huaicheng Li (Virginia Tech)
- **一句话 TL;DR**: 基于 FEMU 的 **CXL-SSD 全系统仿真器**——Dynamic EPT Remapping (DER) 消除 cache hit VM-exit(150ns) + Shared EPT Memory 常数时间 cache 状态更新 + trap miss 路径准确 modeling NAND timing(tens-of-µs), 首个同时满足 fidelity+speed+extensibility 的 CXL-SSD 研究平台, validated against 真实 CMM-H 硬件。

## 核心问题

CXL-SSD 设计空间广阔且未定型, 但研究工具严重不足: 硬件原型(如 Samsung CMM-H)不透明(固件控制/无 policy knob); 软件模拟器太慢(trace/cache-level 无法跑真实 OS+应用); QEMU MMIO-based CXL 每次访问触发 VM-exit(~15µs)→无法区分 sub-µs hit vs tens-of-µs miss。

需要同时满足: (1) full-stack 执行(unmodified OS+应用); (2) 近裸机速度(分辨 sub-µs 和 tens-of-µs); (3) 准确设备建模(DRAM cache+NAND)。

## 方案设计

### Hybrid Access Path

| 路径 | 机制 | 延迟 |
|------|------|------|
| **Cache Hit** | EPTE Direct →直接访问 DRAM cache →无 VM-exit | 150ns |
| **Cache Miss** | EPTE Trap →VM-exit→KVM→QEMU CXL emulation→FEMU NAND timing→数据返回→插入 cache→更新 EPTE to Direct | 40µs |

### Dynamic EPT Remapping (DER)

- Hit → EPTE = Direct(指向 DRAM cache)
- Miss → EPTE = Trap(触发 VM-exit)
- Eviction → EPTE 从 Direct 切回 Trap
- **Batched invalidation**: INVEPT + INVVPID + 批量合并→避免逐条 TLB shootdown

### Shared EPT Memory

- 常数时间 cache residency 更新, 降低 miss/trap 处理 overhead

### Configurable Caching Layer

- 可插拔 eviction(LRU/MRU/...) 和 prefetching 策略
- Application-level interface →硬件-软件 co-design

## 关键数据

- Validation against real CMM-H: 复现 sub-µs hit + tens-of-µs miss
- 运行 unmodified 应用(Redis, graph analytics)
- Near bare-metal speed for full-stack execution

## 可复用启发

1. **"EPT remapping = 页面级硬件加速的 fast/slow path 切换"**: 利用 Intel EPT 的 Direct/Trap 状态→hit 直接 hardware access→miss 才 trap。类似 GCR 的 control/data 分离、RASK 的 eager/lazy B-tree——"fast path 硬件化, slow path 软件化"的通用策略

2. **"Shared EPT Memory = 消除 VM-exit 的 batch 方式"**: 不是逐条 invalidation→batch coalesce INVEPT/INVVPID。类比 DMTree 的"hit potential 三源融合"——将 expensive operation 从 per-access 变为 batched

3. **"Emulator as research platform > 硬件原型"**: Cylon 提供硬件不具备的 policy knob(可换缓存策略/可应用级 hint)→加速 CXL-SSD 设计空间探索。类似 FEMU 自身在 NVMe 研究中的角色

## 归档建议

已归档到 `architecture/memory-storage-hierarchy/` (CXL/内存层次)。
