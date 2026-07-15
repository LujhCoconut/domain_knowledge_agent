# WriteGuards(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-mao-ziming-writeguards.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: CLINK(进程内)+CRINK(远程) 分布式缓存，基于 WriteGuards 存储原语解决 delayed-writes anomaly——key-range 粒度 fencing 替代 per-key fencing，线性化读 tail latency 降三个数量级（CLINK），远程读写改善 2.2-2.4×。

## 核心问题

分布式缓存提供低延迟读但需要强一致性（linearizable reads）才能在生产关键路径（权限检查、SQL 协调）上使用。核心难点是 **delayed-writes**——reshard 后前任 owner 仍有 in-flight 写，新 owner 在那些写到达前读到的值可能是 stale 的。生产系统观察到此延迟可达 ~90 秒（GitHub outage 期间）。Per-key fencing 不可扩展。

## 关键洞察

1. **"WriteGuards = key-range 粒度 fencing"**：每个写携带一个关联当前 owner 的 fencing 值，存储系统检查后拒绝延迟写。粒度是 key-range 而非 per-key→大规模可扩展。
2. **"与 sharding 系统松耦合"**：不需要存储系统重写——只需要在写路径加一个条件检查。读路径完全不受影响。
3. **"CLINK = first distributed linked cache with linearizable reads"**：进程内 linked cache 不再需要 contact storage 就能提供线性化读。
