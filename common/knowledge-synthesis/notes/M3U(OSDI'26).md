# M3U(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-xu-yizhe.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 高端 VM 后拷贝迁移的内核内存管理可扩展性瓶颈——锁过度使用是根源。M3U 通过锁放松+预分配+解耦 fault pipeline+直通设备预传，downtime -47%、post-copy 持续 -89.6%、guest 性能 +4.1×。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| Pre-copy vs Post-copy | Pre-copy: 先传内存再切换 VM→dirty rate 太快无法收敛；Post-copy: 先切换 VM 再按需取页→必然收敛但性能差 | 高端 VM 必须用 post-copy（pre-copy 仅 81% 成功率） |
| Convergence problem | vCPU 脏页速率 > 网络传输速率→pre-copy 永远无法完成 | 12 个月 50K+ 样本分析：19% 迁移失败根因 |
| Dirty page registration | 后拷贝启动前将所有脏页标记为缺失→VM 访问时触发 page fault | **占总 downtime 57-66%**——核心瓶颈 |
| Lock contention in page reconstruction | 多任务并发重建缺失页→跨页表维护一致性→锁竞争 | 页传输吞吐仅达网络带宽的 **9.2%** |
| Userfault pipeline | Linux 的按需缺页机制 | M3U 将其解耦实现无锁并行 |
| Pre-allocation + permission flagging | 预先分配所有 VM 物理内存+轻量权限位标记替代 page map/unmap | 消除关键路径上的昂贵操作 |
| Pass-through device I/O page fault | 直通设备的硬件 I/O 缺页 | M3U 通过设备状态识别+预传输消除 98.5% |

## 可复用启发
- **"锁过度使用而非资源不足常是内核可扩展性瓶颈"**：M3U 的根因分析——锁竞争使带宽利用率仅 9.2%。类似于 DeLFS 的 "不优化锁，而是消除共享"
- **"预分配+轻量标记替代重量级 map/unmap"**：减少关键段长度
- 来源：M3U(OSDI'26)
