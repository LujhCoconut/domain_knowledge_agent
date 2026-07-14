# BALBOA(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-heer.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 开源的 100Gbps RoCEv2 RDMA 卸载引擎（FPGA SmartNIC）——性能匹配商用 ASIC，同时完全可定制传输层，支持加密/DPI/推荐系统预处理卸载。

## 核心问题

商用 RDMA NIC 是黑盒——传输层不可修改（安全策略、拥塞控制、应用逻辑卸载都无法定制）。FPGA SmartNIC 可编程但性能低、协议不完整、缺少 CRC/重传等关键组件。学术研究界缺乏一个**既高性能又完全可编程**的 RDMA 平台。

## 方案: BALBOA

- **Decoupled state architecture**：解决 FPGA 内存和时序瓶颈
- **Streaming control-data separation**：控制路径和数据路径的流式分离
- **100G + 数百 QPs** + RoCEv2 完全兼容 + CRC + 重传逻辑
- 性能匹配 ASIC，同时**传输层完全可定制**
- 两个 case study：加密+深度包检测（infra）、推荐系统预处理卸载（application）

## 可复用启发
- **"Decouple state architecture + streaming separation"是 FPGA 卸载高性能 RDMA 的关键**：与 UCCL-Tran 的 "data/control path separation" 形成互补——BALBOA 在硬件层解耦，UCCL-Tran 在软件层解耦
- 来源：BALBOA(OSDI'26)
