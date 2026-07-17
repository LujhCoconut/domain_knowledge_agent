# Knowledge Synthesis

把阅读过的技术资料（论文、文档、博客、源码、会议分享）转化为可复用的个人 skill 知识。

包含三个核心动作：
1. **四轮递进阅读**（R1 速览 → R2 深读 → R3 交叉验证 → R4 对抗审视）：从快速筛选到深度理解到知识网络构建
2. **结构化元数据提取**：生成 JSON metadata + 技术倒排索引，支持程序化查询
3. **归档与整合**：判断新知识应该归入哪个已有 skill，还是新建一个 skill，并落地为 `SKILL.md` 或可执行笔记

---

## 0. 论文命名规范（⚠️ 必须遵守）

**不要用 PDF 文件名或 URL 路径作为论文的引用名称**，因为这些命名不可控（可能乱码、缩写不一致、缺少会议信息）。每次处理论文时，必须从论文**正文中提取**以下信息来构造规范名称：

### 提取来源（按优先级）

1. 论文标题 → 提取方案/系统名称（通常是标题的首个专有名词或冒号前部分）
2. 论文首页 → 提取会议/期刊缩写 + 年份（通常在页眉或版权声明区，如 "ASPLOS '26"）

### 命名格式

```
方案名(会议'年份)
```

**示例**：

| 论文标题 | PDF 文件名 ❌ | 规范名称 ✅ |
|----------|--------------|-------------|
| PACT: A Criticality-First Design for Tiered Memory | `PACT_ASPLOS.pdf` | `PACT(ASPLOS'26)` |
| TPP: Transparent Page Placement for CXL-Enabled Tiered Memory | `tpp_final.pdf` | `TPP(ASPLOS'23)` |
| Memtis: Efficient Memory Tiering with Dynamic Page Classification | `memtis-sosp23.pdf` | `Memtis(SOSP'23)` |

### 适用范围

此规范名称用于：
- 深度阅读笔记文件名: `notes/PithTrain(arXiv'26).md`
- 阅读日志中的「资料标题」列
- JSON metadata 中的 `canonical_name` 字段
- 各 `SKILL.md` 中引用论文时的行文
- commit message 中的论文标识

**对于非论文资料**（技术博客、文档、源码），用原始标题或 URL 路径中可识别的名称即可，不需要套用此格式。

---

## 1. 四轮递进阅读流程

论文阅读不是一次性活动，而是分阶段递进：快速筛选 → 深度理解 → 建立联系 → 批判审视。

### 1.1 R1 速览（5-10 分钟）：决定是否值得深读

**输入**：PDF / 网页 / 标题+摘要
**输出**：JSON metadata 条目初稿 + 一句话 TL;DR + R2 决策

**产物格式**：
```markdown
# R1 Quick Note: <方案名(会议'年份)>

- **一句话 TL;DR**: <用一句话概括核心贡献或观点>
- **问题域**: <解决什么问题>
- **方法类型**: <方法/系统/协议/编译器/理论/经验报告>
- **工业可用性初判**: high / medium / low
  - high: 有可直接集成到生产系统的开源代码/方案
  - medium: 核心思想可复用但需要适配
  - low: 需要特殊硬件、远未成熟、或纯理论
- **是否进入 R2**: yes / no（理由）
```

**必做操作**：
1. 在 `history/metadata.json` 中创建条目初稿。字段模板见 §4 JSON 元数据规范。至少填充：`canonical_name`, `title`, `authors`, `conference`, `year`, `url`, `date_read`, `type`, `tags`, `r1_tldr`, `industrial_applicability`, `knowledge_locations`
2. 在 `history/reading-log.md` 中追加一行

### 1.2 R2 深读（30-60 分钟）：提取可复用启发

**输入**：全文
**输出**：深度笔记 + KNOWLEDGE.md 更新 + metadata 填充

执行完整的深度阅读模板（§1.5），并额外填充 JSON metadata 中的 `techniques`, `builds_on`, `contrasts_with`, `r2_insights`, `applicability_why`, `prerequisites`。

**⚠️ 知识归档（‼️ 绝不可偷懒）**：同 §2 归档流程 — 必须将可复用启发写入对应 `KNOWLEDGE.md`。

### 1.3 R3 交叉验证（10-20 分钟）：建立知识网络

**输入**：R2 产出 + 已有知识库（`history/metadata.json`）
**输出**：关系边标记 + 矛盾检测

**执行步骤**：
1. 在 `metadata.json` 中搜索与本论文 `tags` 有交集的已有论文
2. 检查是否存在矛盾声明（如两篇论文声称相反的最优策略）："这篇说 X 是最优的，那篇说 Y 是最优的，是因为假设不同还是结果冲突？"
3. 标记关系类型并更新 metadata 的 `builds_on` / `contrasts_with` / `complements` / `supersedes` 字段
4. 填充 `r3_relations` 字段
5. 如有重要矛盾或互补，在相对应的 KNOWLEDGE.md 中补充交叉引用

**产物格式**：
```markdown
# R3 Cross-Reference: <方案名(会议'年份)>

- **与已有知识的关系**:
  - 继承: <已有论文> — <具体继承了什么>
  - 矛盾: <已有论文> — <矛盾点及其原因>
  - 互补: <已有论文> — <如何组合>
  - 超越: <已有论文> — <在什么维度上更好>
- **新发现的关系**: <之前不知道的联系>
```

### 1.4 R4 对抗审视（10-15 分钟）：批判性审视

**输入**：R2+R3 产出
**输出**：局限标记 + 过度声明检测

**执行步骤**：
1. 逐条审视作者的 claim，问"证据链够强吗？"
2. 检查实验遗漏：只测了一种 workload？一种硬件？一个 scale？
3. 检查过度声明：abstract 宣称的性能提升是否有充分实验支持？
4. 填充 metadata 中的 `r4_refute` 字段

**产物格式**：
```markdown
# R4 Adversarial Review: <方案名(会议'年份)>

- **最脆弱的 claim**: <哪个声明证据最弱>
- **实验遗漏**: <什么场景没测/什么硬件没测>
- **过度声明风险**: <abstract 中的数字是否有充分实验支持>
- **假设敏感性**: <如果某个关键假设不成立，方案还 work 吗？>
- **整体可信度**: high / medium / low
```

### 1.5 深度阅读模板（R2 使用，原 Deep Note）

```markdown
# <方案名(会议'年份)>

- 来源 / 年份 / 版本
- 一句话 TL;DR
- 资料类型

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| ...  | ...  | ...            |

## 背景与动机（可选）

- 图/观察
- 作者结论
- 我的分析

## 问题定义

- 要解决什么
- 现有工作为什么不够

## 方案介绍

- 方案概述
- 关键模块/算法
- 关键图/代码片段

## 证据与评估

- 测试环境
- 每个实验：测试目的 / 测试方案 / 测试结果 / 数据解读

## 整体评估

- 真正的新意
- 优点 / 缺点
- 局限与假设
- 适用条件
- 可复用启发
- 讨论问题
```

---

## 2. 归档与整合流程

读完资料后，不要只存一份笔记。把**可复用启发**拆出来，放到对应的 skill 里。

### 2.1 判断新知识归属

按这个决策树走：

```
新知识
├── 是关于某个具体系统/工具的运维、部署、排错？
│   └── → operations/<system>-<topic>/
│
├── 是关于串行/并行/并发/系统/数据库/网络/GPU 的性能优化？
│   └── → performance/<paradigm-or-domain>/
│
├── 是关于分布式系统/微服务/数据系统/可靠性/云原生设计？
│   └── → architecture/<domain>/
│
├── 是关于软件框架/系统的设计方法论（如 Agent-Native 设计）？
│   └── → architecture/<methodology-domain>/
│
├── 是跨领域复用的工具、脚本、检查清单、诊断流程？
│   └── → common/<tooling|diagnosis-playbooks|checklists>/
│
├── 是关于如何阅读、学习、整理知识本身？
│   └── → common/knowledge-synthesis/
│
└── 不属于任何现有目录？
    └── 在对应一级目录下新建 skill 子目录
```

### 2.2 整合到已有 skill 的方式

- **补充知识点（‼️ 必须做，不可跳过）**：在对应 `KNOWLEDGE.md` 中追加完整的 `##` 章节，包含三段式结构：

  ```markdown
  ## <主题名> (<方案名>)

  ### 核心问题
  <为什么这个问题重要、现有方案为什么不够>

  ### 关键洞察
  1. **"<洞察一句话>"**：<解释>
  - 来源：<方案名(会议'年份)>

  ### 实践启发
  - **"<启发>"**：<如何应用到自己的项目/其他场景>
  ```

  **⚠️ 仅添加一行子主题表条目（`| 主题 | 关键词 | 来源 |`）而省略完整的 `##` 章节是严重偷懒，禁止这样做。表条目只是索引，完整的 `##` 章节才是知识本身。**

- **补充案例**：新建 `<skill-dir>/cases/<case-name>.md`，按「环境-现象-定位-优化-验证」组织。
- **补充检查清单**：在 `common/checklists/` 下增加条目，并在相关 `SKILL.md` 中引用。
- **补充工具/脚本**：在 `common/tooling/` 下新增，并在相关 skill 中说明使用场景。

### 2.3 新建 skill 的方式

如果新知识无法被已有 skill 覆盖：

1. 在对应一级目录下新建子目录，命名格式：`{topic}-{subtopic}` 或 `{system}-{capability}`。
2. 目录内必须包含 `SKILL.md` 或 `KNOWLEDGE.md`。
3. `KNOWLEDGE.md` 至少包含：
   - 子主题索引表
   - 每个子主题的完整 `##` 三段式章节

---

## 3. JSON 元数据规范

每篇论文必须在 `history/metadata.json` 中有一个 JSON 条目，支持程序化查询和交叉引用。Schema 定义见 `history/metadata.schema.json`。

### 3.1 示例条目

```jsonc
{
  "canonical_name": "PithTrain(arXiv'26)",
  "title": "PithTrain: A Compact and Agent-Native MoE Training System",
  "authors": ["Ruihang Lai", "Hao Kang", "Haozhan Tang", "Tianqi Chen"],
  "conference": "arXiv",
  "year": 2026,
  "url": "https://arxiv.org/abs/2605.31463",
  "date_read": "2026-07-17",
  "type": "论文-系统",
  "tags": ["MoE training", "agent-native design", "pipeline parallelism", "torch.compile"],
  "techniques": ["DualPipeV", "FP8 weight cache", "EP dispatch dedup", "fullgraph compilation"],
  "builds_on": ["DeepSeek-V3(DualPipe)", "FSDP", "torch.compile"],
  "contrasts_with": ["Megatron-LM(registry-based design)"],
  "industrial_applicability": "medium",
  "applicability_why": "11K行Python可直接fork改造，但需适配自己的模型架构和训练配置",
  "prerequisites": "PyTorch 2.x, H100/B200 GPU, NCCL",
  "knowledge_locations": [
    "architecture/agent-native-design/",
    "performance/gpu-ai-performance/"
  ],
  "review_rounds": {
    "r1_tldr": "将agent效率作为第一等优化目标的11K行MoE训练框架，匹敌生产吞吐",
    "r2_insights": "紧凑Python-native代码库+无隐式间接引用+agent skills降低agent成本62-64%",
    "r3_relations": "",
    "r4_refute": ""
  }
}
```

### 3.2 倒排索引

`metadata.json` 中的 `technique_index` 和 `tag_index` 是自动生成的倒排索引，格式：

```json
{
  "technique_index": {
    "DualPipeV": ["PithTrain(arXiv'26)", "Tessera(OSDI'26)"],
    "FP8 weight cache": ["PithTrain(arXiv'26)"]
  },
  "tag_index": {
    "MoE training": ["PithTrain(arXiv'26)", "Tessera(OSDI'26)"]
  }
}
```

这些索引由后置操作自动从 `papers[].techniques` 和 `papers[].tags` 生成，无需手动维护。

### 3.3 生成/更新命令

每次完成论文解析后，在 metadata.json 中追加条目，然后重新生成倒排索引：

```bash
cd ~/.claude/skills/domain-knowledge
# 重新生成倒排索引
python3 history/rebuild_index.py  # 如果有脚本
# 或者手动 jq 重建
```

如果暂时没有自动化脚本，索引可以在后续按需手动重建。

---

## 4. 输出规范

- **正文主要用中文**；标准术语保留英文原名（如 ablation、baseline、throughput、latency、scalability）。
- **明确区分「资料事实」和「我的理解/判断」**。
- **优先用 bullet 和表格**，避免长篇散文。
- **如果材料不完整，直接说明缺失**，不要猜。
- **每个实验结论后补一行数据解读**，说明它支持了什么、没支持什么。
- **论文/资料图尽量提取并插入文档**，不要只列 "Figure X"。

---

## 5. 与本知识库其他 skill 的关系

- 读完论文/资料后，把**启发**拆到 `operations/`、`performance/`、`architecture/`、`algorithms/`、`security/`、`network/`。
- 把**元数据**写入 `history/metadata.json`。
- 把**阅读方法论**本身放在 `common/knowledge-synthesis/`。
- 把**通用工具**放在 `common/tooling/`，把**检查清单**放在 `common/checklists/`。
