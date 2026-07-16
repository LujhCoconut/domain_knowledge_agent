# Xerxes(FAST'26)

- **来源**: https://www.usenix.org/system/files/fast26-an.pdf, FAST '26
- **作者**: Yuda An, Shushu Yi (PKU), Bo Mao (Xiamen U), Qiao Li (MBZUAI), Mingzhe Zhang (IIE CAS), Diyu Zhou (PKU), Ke Zhou (HUST), Nong Xiao (SYSU), Guangyu Sun, Yingwei Luo, Jie Zhang (PKU) — ChaseLab
- **一句话 TL;DR**: 面向 CXL 3.1 全特性(port-based routing + device-managed coherence + PCIe 6.0)的**全新仿真框架**——两层设计(interconnect layer 建模非树拓扑路由 + device layer 建模设备侧一致性), 填补了现有工具无法仿真 large-scale CXL fabric 的空白, 误差 0.1-10%。
- **资料类型**: 论文-系统（仿真基础设施）

## 重要术语

| 术语 | 解释 |
|------|------|
| PBR | Port-Based Routing, CXL 3.0+ 的源/目的端口路由, 支持非树 mesh/spine-leaf 拓扑 |
| DMC (HDM-DB) | Device-Managed Coherence with Back-Invalidate, 一致性管理从 host 卸载到 device DCOH agent |
| DCOH | Device Coherency Agent, 发送 BISnp/BIRsp 管理 peer cache coherence |
| VCS | Virtual CXL Switch, CXL 2.0 的虚拟交换单元 |
| vPPB | virtual PCI-to-PCI bridge |
| HDM-H/HDM-DB/HDM-D | Host coherent modes (host-managed, device-managed w/ back-invalidate, device-coherent legacy) |

## 核心问题

CXL 3.1 引入了 port-based routing (支持 4096 端点非树拓扑) + device-managed coherence, 但研究工具严重不足:
- NUMA emulation: 物理扩展性受限, 无法模拟 4096 端点
- gem5/gpgpusim: host-centric, 无灵活的非树拓扑+设备主动发起一致性请求
- BookSim/Garnet: network-centric, 不理解内存一致性语义
- MESS/CXLMemSim: behavioral (Lat-BW 曲线注入), 无法预测新拓扑/新特性的 emergent behavior, 无法建模 PBR 多路径路由和 DMC snoop 延迟

## 方案设计

### 两层架构

- **Interconnect Layer**: 灵活建模任意非树拓扑(PBR)+PCIe 6.0 full-duplex, 提供 switch/routing table/bandwidth 模型
- **Device Layer**: 实现 DCOH (device-side inclusive snoop filter + back-invalidation), 模块化可组合设计, 可嵌入已有模拟器

### 三项关键实现

1. **PBR switch**: 12-bit port ID → 4096 端点, 内部 routing table 按 source port→destination port 转发
2. **Device-side inclusive snoop filter**: BISnp/BIRsp 通道, 针对 device 接收的 cache miss 为主的特点定制
3. **PCIe bus component**: 建模 full-duplex 带宽+延迟, 考虑 read-write mixed 场景下的差异化影响

## 关键发现 (Xerxes 仿真得出的三个 observation)

1. **传统树状拓扑存在根节点瓶颈**——性能退化可能接近链式拓扑
2. **Device snoop filter 收到的主要是 cache miss**——需要针对此 pattern 定制结构(不同于 CPU 的 snoop filter)
3. **PCIe full-duplex 在读写混合负载下能显著提升带宽**——相比纯读或纯写

## 可复用启发

1. **"Behavioral simulation ≠ predictive simulation"**: Lat-BW 曲线只能复现已知硬件的性能, 不能预测新架构设计空间的 emergent behavior。对 CXL 3.1 这类新特性尚无参考硬件时, architectural-level modeling 不可或缺。类似 Cylon 的"emulator as research platform > prototype"

2. **"Interconnect + Device 两层分离 = 拓扑灵活性与设备语义解耦"**: 类似 GCR 的 control/data 分离——将路由/拓扑与设备侧一致性/缓存逻辑分开建模, 各自独立演进

3. **"Snoop filter 的优化取决于到达请求的 pattern"**: device 侧 snoop filter 收到的主要是 cache miss(而非 CPU 侧的混合 hit/miss), 这根本改变了 snoop filter 的最优结构。类似 OdinANN 的"数据结构特性决定优化方案"

## 归档

已归档到 `architecture/memory-storage-hierarchy/` (CXL 体系结构)。
