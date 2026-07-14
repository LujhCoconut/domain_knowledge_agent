# Oxbow(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-kim-jongyul.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: Oxbow 是协调式多组件文件系统架构——kernel read path + user-level write path + CSD offload journaling + shared-ownership metadata，同时在性能/内核互操作/CPU开销/开发速度四个维度上达到最优。

## 核心问题

存储硬件超过 14GB/s，传统 kernel-centric 架构成为瓶颈。但现有三个方向各有利弊：user-level FS 快但丢失 page cache/sendfile 等内核服务；kernel FS 功能全但 CPU-bound；CSD FS 省 CPU 但 PCIe 延迟 + 弱 device CPU。**没有一个架构能同时满足四个目标**。

## 方案：四组件协调

| 组件 | 职责 |
|------|------|
| **oxLib** (user library) | 应用感知的快速 I/O 接口 |
| **H-Server** (trusted user-level) | 核心 FS 逻辑 |
| **illuFS** (kernel shim) | VFS/page cache/sendfile 集成 |
| **D-Server** (CSD device-side) | 后台 journaling + checkpointing |

### 三个协调机制

1. **Semi-kernel-bypassing I/O**: Reads 走 kernel page-fault path（复用 page cache + readahead）；Writes bypass kernel 直接从 user→device
2. **Shared-ownership metadata**: inode 属性按写入者分区——每个属性只有一个 writer（oxLib 管 size/mtime，kernel 管 uid/gid）→ 消除同步瓶颈
3. **Split Journaling**: Host-device journaling——fsync 与后台 commit 解耦，利用 staging areas + DMA snapshot

## 可复用启发
- **"不对称 bypass"比"全 bypass"或"全 kernel"更优**：读和写的 kernel 价值不对称——不是非要二选一
- **"按写者分区共享状态"消除同步**：每个属性只有一个 writer——不需要锁/同步
- 来源：Oxbow(OSDI'26)
