# RubikFS(FAST'26)

- **来源**: https://www.usenix.org/system/files/fast26-huang.pdf, FAST '26
- **作者**: Hao Huang, Yifeng Zhang, Yanqi Pan, Wen Xia, Xiangyu Zou, Darong Yang (HIT Shenzhen), Jubin Zhong, Hua Liao (Huawei)
- **一句话 TL;DR**: 通过相似度排序+聚类解决只读文件系统块压缩的 data mixture 问题——对数据 chunk 构建相似度图并子图分割聚类后排序，使相似数据落入同一压缩块，压缩比提升最高 42.60%，读放大降低最高 70.70%。
- **资料类型**: 论文-系统

---

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| Data Mixture | 固定大小块划分时将相似数据分散到不同块、不相似数据混合在同一块中 | 块压缩无法充分利用冗余的根因 |
| RubikFS | "魔方"——将混合数据像魔方还原一样重新排序 | 本文系统名 |
| Direct | 直接将整个 image 作为连续 bitstream 压缩（不划分块），大字典消除冗余 | 压缩比的上界 |
| Sort-Enhanced Compression | 先按相似度排序 chunk 再分块压缩 | 本文核心 idea |
| Similarity Graph | 节点=chunk, 边=相似度(0~1)的无向图 | 用子图分割聚类相似 chunk |
| METIS | 图分割算法 | 将相似度图划分为预设数量子图 |
| Feature Extraction | 用 gear hash 滚动计算哈希值，按采样率 P 提取特征 | 将 chunk 表示为特征向量的方法 |
| Data Grouper | 按文件类型（ELF Code/ELF Data/Binary/Text/Others）预分组 | 加速 image 构建 |
| Data Chunker | 定长 chunking (FSC) + 全去重 | 划分排序单元 |
| Hotness Grouper | 按启动时是否访问将 chunk 分为 hot/cold 子组 | 缓解排序导致的读放大不可预测 |
| EROFS | Enhanced Read-Only File System (华为/阿里贡献的 Linux 只读 FS) | RubikFS 基于 EROFS 实现 |

---

## 背景与动机

### 问题场景

只读压缩文件系统（Squashfs, EROFS）广泛应用于 IoT 嵌入式设备和 Docker 容器——仅华为 IoT 场景就有数十亿设备。Image size 是核心关注点：更小的 image = 更便宜的硬件 + 更快的容器启动。

### Data Mixture 问题（核心问题）

观察到：块压缩无法达到 Direct（整 image 压缩）的效果，是因为 **data mixture**：
- 当 image 被划分为固定大小的压缩块时，相似数据被分散到不同块中
- 跨块的数据冗余字典压缩无法消除（字典大小 = 块大小）
- Direct 用大字典（如 XZ 64MB）在全 image 范围内找相似数据→压缩比更高，但读一个字节需要解压整个 image→性能不可接受

**关键发现**：如果**先排序再压缩**（Data Sorted），压缩比始终高于不排序（Data Mixed）——排序是解决方案。

### 排序的三个挑战

1. **排序不适配只读文件系统**：现有相似度检测算法（Finesse/Odess）只能识别高度相似 chunk，不能量化部分相似度（0~1）
2. **排序造成不可预测的读放大**：排序后 hot/cold chunk 随机分布→访问热数据时被迫读大量冷数据
3. **排序大幅增加 build time**：O(N²×M²) 的相似度计算复杂度

---

## 方案设计（四个组件）

### 1. Data Grouper（按类型预分组）

**做法**：将 image 数据按类型分为 ELF Code / ELF Data / Binary / Text / Others 五个组。

**原因**：同类型数据更可能相似，不同类型通常无重复——分组处理减少计算量。实验表明预分组不降低压缩比（不同类型间几乎没有跨组相似数据）。

### 2. Data Chunker（分块 + 去重）

**选择 FSC（定长）而非 CDC（内容定义）**：CDC 产生变长 chunk→页面不对齐→最坏读放大会严重恶化（因为排序后 chunk 可能被放入大块中）。

**Chunk 大小**：`min(4KB, BlockSize / 16)` ——在压缩比和数据局部性之间折中。

**去重**：全去重（整 chunk 相同才去重）而非尾去重——因为 Similarity Sorter 可通过聚类补偿部分去重无法覆盖的冗余，同时避免尾去重造成的页不对齐问题。

### 3. Hotness Grouper（热数据分组）

**做法**：kprobe 追踪启动阶段的 readpage 调用→生成 hot chunk trace→将 chunk 分为 hot/cold 子组分别处理。

**效果**：12% hot 数据场景下，运行时读取量从 2.88s/55.72MB 降至 1.21s/16.41MB（LZ4 1MB block）。排序不再是读放大的放大器。

**压缩比代价可忽略**：即使在 40% hot 的极端场景，压缩比差异 < 0.11×。

### 4. Similarity Sorter（相似度排序）

**五步流程**：

1. **特征提取**：gear hash 滚动计算→每 1/P 字节记录一个 max_hash 作为特征（默认 P=1/128，每个特征代表 128 字节）
   - 为什么不用传统 3-12 超特征？只读 FS 需要量化部分相似度（0~1），而非二分类相似
2. **建相似度图**：节点=chunk，边=共享特征数/总特征数。用哈希表散列特征→复杂度从 O(N²) 降至 O(N)
3. **METIS 子图分割**：将图分为预设大小的子图，最小化跨子图边（移除低相似度连接）
   - 精细去重是子图分割的退化版本（边 weight 仅为 0 或 1）
4. **排序**：子图内按 chunk 相似度排序 + 子图间按子图特征聚合后的相似度排序
5. **打包 + 索引**：额外 12B/chunk 索引（文件偏移→打包偏移→chunk 大小），开销 0.018%-2.93%

---

## 评估数据

### 压缩比提升

| 场景 | vs EROFS/Squashfs | 亮点 |
|------|-------------------|------|
| 六张 image × 三种算法 (LZ4/ZSTD/LZMA) | 最高 +42.60% | LZ4 效果最显著（字典仅 64KB，排序收益最大） |
| Harm-3516/3518/3861 | 甚至**超过 Direct** | 排序可以聚类原始 image 中物理距离很远但在相似度上接近的数据 |

### 读放大抑制

| 指标 | 12% hot (18MB) |
|------|---------------|
| EROFS/Squashfs 运行时间 | 2.88-3.46s |
| RubikFS | **1.21s (LZ4), -65%** |
| RubikFS 读取量 vs w/o Hotness | **-70.70%** |

### Build Time

| Image | No Sort | No Grouper | RubikFS (w/ Grouper) |
|-------|---------|------------|----------------------|
| Harm-3516 (667MB) | 163s | +288s | **+208s** (节省 28%) |
| openEuler (155MB) | 41s | +1.9s | **+0.84s** (节省 56%) |
| Harm-3861 (42MB) | 12.7s | -1.05s | **-1.78s** (排序甚至比不排序更快！) |

### 敏感度分析（六项配置均对压缩比鲁棒）

所有默认配置（数据分组、自适应 chunk size、全去重、12% hot、P=1/128、子图大小=64）均通过充分的敏感度实验验证。

---

## 整体评估

### 真正的新意

1. **"相似度排序 + 块压缩"是新范式**：将备份存储领域的相似度检测/排序技术引入只读文件系统压缩——此前二者完全隔离。关键转变是：从二分类（similar or not）→连续值（0~1）→子图分割聚类。

2. **"只读"的约束是优势而非限制**：正因为 image 是 write-once 的，可以承受昂贵的一次性排序开销——这在线数据压缩场景不可接受。RubikFS 正是利用了只读场景的独特自由度。

3. **Hotness grouper 是解决排序副作用的关键**：排序聚类相似数据→但破坏了 hot/cold 局部性→hotness grouper 在排序前预分组→用极小的压缩比代价（<0.11×）换取巨大的读放大改善（-70.70%）。

### 优点

- 问题、方案、实验之间有非常清晰的因果链
- 每个设计决策（FSC vs CDC、全去重 vs 尾去重、chunk 大小）都有"为什么"的解释和替代方案的利弊分析
- 敏感度分析全面覆盖了六个关键配置维度
- 利用 EROFS 的已有基础设施（仅改 ~3.5K LoC），部署成本低

### 局限与假设

- 仅适配三种压缩算法（LZ4/ZSTD/LZMA）——需要压缩算法支持 fixed-size block 输出
- image 规模限于 MB-GB 级别（嵌入式/容器场景），PB 级冷数据归档不适用
- Hotness tracing 依赖 kprobe + 固定场景（嵌入式设备启动 pattern 确定性高）——更动态的场景效果未知
- 对非结构化数据（pictures/videos/tar packages，即 Others 组）几乎无增益

### 适用条件

- 嵌入式系统 / Docker 容器 / IoT 设备等只读 image 场景
- 可执行文件和文本文件占比高（相似度排序对此有效）
- 启动时 I/O pattern 可预测（可 trace hot chunks）

### 可复用启发

1. **"排序前先压缩 = 用数据重排替代更大的字典窗口"**：当字典大小受限时（如 LZ4 64KB），通过重新排列数据使相似内容落入字典窗口距离内——本质是在数据布局层面做"字典扩容"。

2. **"利用 write-once 的奢侈"**：只读场景允许昂贵的一次性优化——在线系统不敢承受的代价（O(N²)→O(N) 相似度计算、全量重排）在此是完全可接受的。识别并利用场景的独特自由度是系统设计的高价值策略。

3. **"Hotness grouper 是用语义信息补偿排序的物理副作用"**：排序优化压缩比但损害访问局部性→引入访问热度信息（语义层）来恢复局部性→用极小代价换取大收益。这是"多层信息协同"的案例。

4. **"子图分割优于二分类——连续值 > 离散值"**：传统方案问"这两个 chunk 是否相似（0/1）"，RubikFS 问"相似度是多少(0~1)，如何最大化子图内的总相似度"。从 yes/no 到 optimization 的范式转变。

### 讨论问题

- 对于包含大量 pre-compressed assets（JPEG/PNG/MP4）的 image，Others 组是否可以进一步细分以利用相似性？
- 在容器 layer 场景（多 image 共享 base layer），跨 layer 的相似度排序是否能进一步减少总存储？
- 排序后的安全影响——sorted layout 是否更易受信息泄漏攻击（通过压缩块大小反推数据内容）？
