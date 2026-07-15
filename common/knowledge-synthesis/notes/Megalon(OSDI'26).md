# Megalon(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-hu-jiyu.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 部分一致性 CXL 内存的数据共享——split 方法：大但低频更新的元数据通过复制在 LNR 中共享，小但高频更新的元数据通过 SCR 共享。CXL shared log 保持 index replicas 一致。比 Tigon (HCMeta) 支持更大数据集。

## 核心问题

CXL 允许多主机共享内存，但硬件一致性（cache coherence）仅覆盖 CXL 内存的一个小区域（SCR，几百 MB），而 CXL 总容量可达数 TB。现有 HCMeta 方案（如 Tigon）在 SCR 中存储 per-object coherence 元数据——当数据集增大时元数据超出 SCR 容量→churn（反复 unshare/reshare）→吞吐降 10×。

## 关键洞察

1. **"Split 元数据——大-低频 vs 小-高频"**：大的 index 条目复制到 LNR（低频更新），仅 coherence record 的关键字段 + shared-log tail pointer 在 SCR（小、高频）。这不是简单的缓存分层——是两个不同性质的元数据的策略化分离。
2. **"CXL shared log 保持 replica 一致"**：所有对 index 的更新通过 shared log 序列化→每个 host 检查 tail pointer 同步→避免单独的一致性协议开销。
3. **"与 Duhu/Blowfish/InfiniDefrag 共享 '利用 CXL 特性改变软件设计' 的哲学"**：Megalon 利用 CXL 的低延迟 load-store 实现高效的 shared log 来协调主机间一致性。

- 来源：Megalon(OSDI'26)
