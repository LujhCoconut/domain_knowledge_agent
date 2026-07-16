# CloudTS(FAST'26)

- **来源**: https://www.usenix.org/system/files/fast26-zhang-kai.pdf, FAST '26
- **作者**: Kai Zhang (CUHK), Tianyu Wang (Shenzhen U), Zili Shao (CUHK)
- **一句话 TL;DR**: 面向云存储的性能监控时序数据存储模型——metadata/data 分离 + 全局 Patricia Trie tag 字典 + 二维 bitmap 时序-tag 映射(TTMapping/TMMC 压缩) + TSObject 按 tag 相似度分组，消除读放大，查询性能 1.37× Cortex, 优于 Parquet/JTS。
- **资料类型**: 论文-系统（时序数据库+云存储）

---

## 重要术语解释

| 术语 | 解释 | 作用 |
|------|------|------|
| TagDict | 全局 Patricia Trie-like tag 字典，双向指针(encoding↔tag pair) | 消除跨 partition tag 重复(>70%冗余)→空间+查询加速 |
| TTMapping | 二维 bitmap: row=时序ID, col=tag encoding, bit=关联 | 时序↔tag 双向索引(B+ -tree 替代) |
| TMMC | Timeseries Metadata Mapping Compression, CSR-based 压缩仅存 ind+ptr | O(M×N)→O(M+N) 空间 |
| TSObject | 按时序组+时间分区的压缩 chunk 对象(key=时序组ID) | 类似 tag 相似度分组的 Parquet row group |
| CloudWriter | 守护进程，data block 持久化时转换+上传 | 不干扰正常监控服务 |
| CloudQuerier | 三步查询: TagDict lookup→TTMapping→并行 TSObject get | 消除全量 block 下载的读放大 |
| Time Partition Tag Array | 每时间分区仅存相关 tag pairs→减搜索空间 | 时间分区感知优化 |
| Tag Frequency-based Grouping | tag pair 按出现频率分类→高频 tag 不能过滤→中低频 tag 分组 TSObject | 查询时过滤无关 TSObject |

---

## 背景与问题

### 性能监控时序系统的云迁移困境

Prometheus/Cortex 将时序 metadata+data 打包为一个时间分区文件→直接转 cloud object →获取少量数据也需下载整个 object→**严重读放大**。

Parquet 列存格式虽压缩数据但不解决按时序过滤的读放大（需扫描整个 column）。JTS 按时序分 object→tag-based 查询需扫描所有 objects→不可扩展。

**核心数据**: 十亿级时序中 >80% metadata 是 tags, >70% tags 跨 partition 重复→反复存储+反复访问。

### 三个关键挑战

1. metadata-data 分离后如何保持逻辑关联
2. 大规模高冗余 tag 如何紧凑管理+高效索引
3. 数据对象如何组织以最小化读放大+最大化云存储带宽

---

## 方案设计

### 1. TagDict: 全局 Patricia Trie 标签字典

- 层级共享前缀(如 cpu=core1, cpu=coren 共享 cpu 节点)
- 每个 tag pair 分配全局唯一 encoding (存储于叶子节点)
- **双向指针**：encoding→tag pair (反向查找无需遍历 trie)
- **时间分区感知**：每 partition 维护 local tag array，排除无关 tags

### 2. TTMapping: 二维 Bitmap 时序-Tag 映射

- Row = 时序 ID, Column = tag encoding（时间分区 local array 顺序）
- Bit=1 → 该时序关联该 tag
- **TMMC 压缩**：CSR-based, 仅存 ind(bit=1 位置) + ptr(累计偏移)
- 空间 O(M+N) vs 原始 bitmap O(M×N)
- **双向索引**：时序ID→tag (按行) + tag→时序列表 (按列扫描 ind+ptr)

### 3. Tag Frequency-based Timeseries Grouping

- 按 tag pair 出现频率分为: 低频(高选择性/高过滤能力)/中频/高频(共享大多数时序)
- 按时序组分割 TTMapping→子矩阵→查询时直接跳过无关组
- 高频 tag pair 不用于过滤但用于 TSObject 分组→并行访问多组

### 4. TSObject: 按时序组分组的数据块

- 每组时序的压缩 chunk 按时序 ID+时间排序→按 group 打包 object
- Key = 时序组 ID→查询时仅下载相关 groups
- 平衡 file size（不过小→metadata 开销 vs 不过大→读放大）

---

## 评估数据

| 对比 | CloudTS vs |
|------|-----------|
| Cortex (全系统) | 平均 **1.43×** 加速 |
| Apache Parquet | 显著优于 |
| JSON Time Series | 显著优于 |
| 多查询模式 | 均优于所有 baseline |

---

## 整体评估

### 新意

1. **metadata-data 分离云存储时序模型**: 传统时序系统 metadata+data 打包为单文件→云对象读放大。分离使 metadata(TagDict+TTMapping) 和数据(TSObject) 独立下载→按需获取。

2. **Patricia Trie + 双向指针 + 时间分区感知**: 三合一设计——前缀共享(省空间) + encoding↔tag 双向(省查找) + 每分区 local array(减搜索空间)。

3. **二维 bitmap CSR 压缩的时序-tag 双向索引**: O(M×N)→O(M+N) + 保留 row/column 双方向访问能力。

### 局限

- 主要验证 Node Exporter 场景(691 时序/452 tags)→更大规模的效果需验证
- Tag frequency-based grouping 是静态的→workload 变化时需重组
- CloudWriter 的数据转换开销未量化

### 可复用启发

- **metadata-data 分离+全局去重** 是消除云存储读放大的通用模式(不仅时序)
- **CSR 压缩保留双向访问** 的 index 设计适用于任何稀疏关联矩阵
- **Tag frequency 分层分组** 是"根据选择性分流"的经典信息检索思路

### 归档建议

主要归档到 `operations/monitoring-observability/` (监控时序系统) + `performance/storage-filesystem/` (云存储模型)。
