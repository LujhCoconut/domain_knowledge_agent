# Open Source Code Analysis

对主流开源项目的源码级分析，涵盖架构设计、核心机制、关键路径和设计权衡。每个项目按子模块组织，叶子目录存放 `KNOWLEDGE.md`。

## 覆盖项目

| 项目 | 目录 | 子模块 |
|------|------|--------|
| vLLM | `vllm/` | `scheduler/`、`kv_connector/`、`worker/` |
| SGLang | `sglang/` | （待补充） |
| Mooncake | `mooncake/` | `store/`、`transfer-engine/`、`ep/`、`integration/`、`p2p-store/` |
| gem5 | `gem5/` | （待补充） |

## 检索与回答流程

### 索引检索（优先）

**先查 `metadata.json` 的索引**，再读 `KNOWLEDGE.md`。`metadata.json` 包含三类索引（由 `rebuild_index.py` 自动生成）：

| 索引 | 字段 | 用途 |
|------|------|------|
| `technique_index` | 按技术名 → 匹配的 entry | 用户问"用了什么技术"时倒查 |
| `tag_index` | 按标签 → 匹配的 entry | 用户问"涉及 XXX 的有哪些" |
| `project_index` | 按项目名 → 匹配的 entry | 用户问"vLLM 有哪些分析过的东西" |

**检索流程**：
1. 如果用户问题涉及具体技术/标签关键词 → 先查 `metadata.json` 的 `technique_index` 或 `tag_index`，定位匹配的 entry name
2. 根据 entry 的 `project` + `submodule` 字段定位到 `open-source-code-analysis/<project>/<submodule>/KNOWLEDGE.md`
3. 读对应 KNOWLEDGE.md 回答问题
4. 如果涉及跨模块交互，同时读取多个子目录

### 直接路径检索（回退）

1. 根据用户提到的项目名 + 子模块，进入对应子目录读取 `KNOWLEDGE.md`
2. 如果涉及跨模块交互（如 vLLM scheduler ↔ kv_connector），同时读取多个子目录
3. 回答时标明引用的源码文件 + 行号

## 信源可信度与写入控制

解析外部资料（博客、PR diff、未验证源码等）前，先检查用户是否附带了可信度标签。标签规则见主 `SKILL.md` 的「信源可信度标签」章节：

| 标签 | 对开源代码分析的行为 |
|------|----------------------|
| **【确信】/【高可信】** | 解析 → 提取知识 → **写入对应子模块 KNOWLEDGE.md** → commit |
| **【不确定】/【询问】/无标签** | **仅检索现有知识库回答**。知识库未覆盖时说"当前知识库没有覆盖这一点"。不写入、不 commit |

**典型场景**：
- 用户说"解析一下这个 PR，【确信】"→ 说明用户已验证过源码，可写入
- 用户说"看看这个博客怎么分析的 vLLM 调度器"（无标签）→ 默认不写入，只回答问题
- 用户说"这个 issue 里讨论的机制靠谱吗，【询问】"→ 仅基于已有 KNOWLEDGE.md 回答，不确定则说不知道

## 知识归档规范

**仅当可信度标签为【确信】或【高可信】时执行以下归档流程。**

当通过源码阅读获得项目内部机制理解后，按以下模板写入对应子模块的 `KNOWLEDGE.md`：

```markdown
## <机制名称>

### 背景
<一句话说明这个机制解决什么问题，在项目的什么位置>

### 核心数据结构
<关键类/结构体/队列，用代码片段说明，标注源文件+行号>

### 完整流程
<从入口到出口的调用链，标出行号>

### 关键设计点
- **"<设计决策>"**：<为什么这样设计>

### 源码位置
<文件路径 + 行号汇总>
```

**重要规则**：
- **每个声明必须可追溯到源码文件+行号**，不得引用 PR 描述、issue 讨论、设计文档的未验证结论
- 不基于 PR diff 推断已合入机制——PR 只是分析参考，最终以实际源码为准

### metadata.json 维护

**每次新增或修改 KNOWLEDGE.md 后，必须同步更新 `metadata.json` 并重建索引**：

1. 在 `metadata.json` 的 `entries` 数组中追加/更新条目：

```json
{
  "name": "<项目名 + 机制名，唯一标识>",
  "project": "<vllm | mooncake | sglang | gem5>",
  "submodule": "<子模块名>",
  "known_for": "<一句话概括这个机制的核心要点>",
  "tags": ["tag1", "tag2", ...],
  "techniques": ["technique1", "technique2", ...],
  "source_files": ["<文件路径>"],
  "source_lines": { "<函数名>": "<行号>", ... },
  "source_urls": ["<如果是博客等非源码来源>"]
}
```

2. 运行 `python3 open-source-code-analysis/rebuild_index.py` 重建 `technique_index`、`tag_index`、`project_index`

**tag 命名规范**：
- 技术概念用英文小写，空格分隔（如 `"late binding"`、`"continuous batching"`）
- 协议/框架名大写（如 `"RDMA"`、`"ZMQ"`、`"TENT"`）
- 每个 tag 应能独立回答"这些知识点涉及什么领域"
