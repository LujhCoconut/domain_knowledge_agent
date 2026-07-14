# DPA-Store(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-schimmelpfennig.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 运行在 NVIDIA BlueField-3 DPA（Data Path Accelerator）上的有序 KV store——on-path 处理消除 OS 开销 + 无状态客户端 + learned index 树支持范围查询，33M lookup/s, 13M range/s。

## 核心问题

远程 KV store 的三难困境：高吞吐 + 范围查询 + 低复杂度。Hash-based SmartNIC offload (MICA/KV-DIRECT) 快但不支持范围查询；RDMA 分布式方案 (Sherman/ROLEX) 需要有状态客户端（故障处理复杂 + 扩展难）；HOST 端 tree traversal 产生大量 DMA round-trip。

## 方案：DPA-Store

- **DPA (Data Path Accelerator)**：BlueField-3 上的 16 核 × 16 线程 = 256 并行线程，直接嵌入网络数据路径，可直接访问 NIC buffer + NIC DRAM + DMA 到 host memory
- **Learned index tree** 存储在 DPA 内存中 → 256 线程并发遍历 → 叶子层 fetch 从 host 侧
- **Writes 缓冲在 DPA 内存，批量传输到 host**
- **计算密集的结构操作（tree rebalance）在 host 执行，事务性地缝合回 SmartNIC**
- **Read cache 直接在 NIC 上**

## 可复用启发
- **"On-path 处理消除 OS 开销"：请求不需要经过 host OS 网络栈——DPA 直接从 NIC buffer 取请求**
- **"Writes 批量异步，reads 智能缓存"的模式可推广到其他 SmartNIC/DPU KV store**
- 来源：DPA-Store(OSDI'26)
