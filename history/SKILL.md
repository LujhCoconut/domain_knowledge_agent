# History

阅读与解析记录，用于追踪哪些论文/资料已经被处理过、什么时候处理的、由哪个 skill 解析、归档到了哪里。

## 用途

- 避免重复阅读同一篇资料。
- 快速回顾自己曾经从某篇资料中提取过什么启发。
- 统计自己在各个领域投入了多少阅读时间。
- 作为个人知识库的「索引页」。

## 文件组织

| 文件 | 用途 |
|------|------|
| `reading-log.md` | 主日志，记录所有被解析的论文/资料（人类可读的表格） |
| `metadata.json` | 结构化元数据，支持程序化查询、过滤和交叉引用（JSON 格式） |
| `metadata.schema.json` | JSON schema 定义，规范 metadata.json 的字段类型和约束 |
| `rebuild_index.py` | 从 papers[].techniques 和 papers[].tags 重建倒排索引 |
| `generate_metadata.py` | 从 reading-log.md 初生成 metadata.json（用于回填或重建） |

后续如果记录变多，可以按年份拆分，例如 `2025.md`、`2026.md`。

## 记录格式

在 `reading-log.md` 中用表格记录：

| 日期 | 资料标题 | 类型 | 来源 | 解析 skill | 归档位置 | 备注 |
|------|----------|------|------|------------|----------|------|
| YYYY-MM-DD | <方案名(会议'年份)> | 论文-系统 | URL/PDF | knowledge-synthesis | performance/system-tuning/ | 一句话说明 |

对于论文，「资料标题」列填写规范名称 `方案名(会议'年份)`（如 `PACT(ASPLOS'26)`），**不要填写 PDF 文件名**。详见 `common/knowledge-synthesis/SKILL.md` §0 论文命名规范。

### 字段说明

- **日期**：解析完成的日期，格式 `YYYY-MM-DD`。
- **资料标题**：论文或资料的原始标题，保持英文不翻译。
- **类型**：论文-方法 / 论文-系统 / 博客 / 文档 / 源码 / 分享 / 其他。
- **来源**：URL、PDF 文件名、会议名称、书籍章节等。
- **解析 skill**：执行解析时使用的 skill，例如 `knowledge-synthesis`。
- **归档位置**：主要启发归档到的 skill 目录，可写多个，用逗号分隔。
- **备注**：一句话说明这篇资料的核心主题或价值。

## 使用流程

1. 读完/解析完一篇资料后，在 `reading-log.md` 末尾追加一行。
2. 如果资料启发被拆到多个 skill，在「归档位置」列出所有相关目录。
3. 定期（比如每月）回顾一次，看看是否有长期只读未归档的资料。

## 模糊查询：「我读过 X 吗？」

当用户问 "我读过 <论文名> 吗" 或 "X 这篇论文读过吗"，执行以下步骤：

1. **可选 DBLP 查询**：如果用户提供的名称不精确（如缩写、不完整标题），先查询 DBLP 获取完整标题：
   ```bash
   cd ~/.claude/skills/domain-knowledge && python3 -c "
   import sys; sys.path.insert(0, 'common/knowledge-synthesis')
   from dblp_lookup import search
   import json
   r = search('<user_query>', max_results=3)
   print(json.dumps([x['title'] for x in r], ensure_ascii=False))
   "
   ```

2. **模糊匹配 metadata.json**：用 `difflib.get_close_matches` 对比所有已有论文的 `title` 和 `canonical_name`：
   ```python
   import json, difflib
   data = json.load(open('history/metadata.json'))
   candidates = [p['title'] for p in data['papers'] if p.get('title')] + \
                [p['canonical_name'] for p in data['papers']]
   matches = difflib.get_close_matches(query, candidates, n=5, cutoff=0.5)
   ```

3. **返回结果**：
   - 匹配度 ≥ 0.8：已读过，返回详细记录（日期、R1 TL;DR、归档位置、R2 状态）
   - 0.5 ≤ 匹配度 < 0.8：可能读过，列出候选项让用户确认
   - 匹配度 < 0.5：未在知识库中找到，建议添加到阅读队列（`history/reading-queue.json`）

   结果格式示例：
   ```markdown
   - **匹配论文**: PolicyCache(NSDI'26)（相似度: 0.92）
     - 完整标题: PolicyCache: Intra-flow Learning in Congestion Control
     - 阅读日期: 2026-07-20
     - R1 TL;DR: 首个intra-flow learning CC，每条流自训练HAT非参树模型用于自身
     - 归档位置: network/os-networking/
     - R2 状态: ✅ 已完成
   ```
