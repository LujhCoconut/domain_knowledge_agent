# LogDrive(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-vickers.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 将共享日志的耐久性（durability）与定序（sequencing）分离——LogDrive 作为云存储之上的可组合耐久层 + AtomicLog 提供共享日志语义，用于 Confluent K2 生产元数据服务，比 DynamoDB 直接使用降成本 10×。

## 核心问题

云对象存储便宜可靠但只支持大块写入。在 S3 之上构建 pub-sub 服务（K2）需要**小写入的元数据存储**。选择：自建分布式 DB 太复杂，用 DynamoDB 太贵（占 K2 总成本 ~75%）。

## 方案：Conflux / LogDrive

- **LogDrive**：简单低层抽象——带编号的随机写地址空间 + weakTail API——可以像 RAID 一样通过 quorum 组合，可以 layer 在任何云存储上（S3/DynamoDB/S3Express 只需数百行代码适配）
- **AtomicLog**：在 LogDrive 之上实现共享日志
- **分离耐久性（LogDrive）与定序（AtomicLog）**
- **K2 生产部署**：metadata 成本比直接 DynamoDB 降 **10×**，整体降 **3×**

## 可复用启发
- **"分离 durability 和 sequencing"是共享日志设计的通用原则**：LogDrive 只保证顺序写的 weak 语义（简化实现），AtomicLog 处理 linearizable 尾部恢复
- 来源：LogDrive(OSDI'26)
