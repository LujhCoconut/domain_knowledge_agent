---
name: domain-knowledge
description: >
  个人领域知识库路由 skill。支持四轮递进阅读 (R1-R4) + JSON 结构化元数据 + 技术倒排索引。
  支持命令: 解析一下这篇论文 [URL] | 润色一下 [语句] | 评价一下这篇论文 | 了解一下 [主题] | [方向]有什么最新进展 | 我读过 [论文名] 吗 | 哪些论文能直接用到工业代码里 | 哪些论文用了 [技术名] | [主题] 应该怎么归档 | 更多见请求类型表。
---


# Domain Knowledge

这是个人领域知识库的入口 skill。你的任务不是直接凭记忆回答，而是先判断用户请求的类型，再到对应子目录中检索相关 `SKILL.md` 和附属文件，最后基于检索到的内容给出结构化回答。

## ⚠️ 前置操作：同步远程仓库（必须最先执行）

**在读取任何子目录文件或处理用户请求之前，必须先执行 git pull 同步：**

```bash
cd ~/.claude/skills/domain-knowledge && git pull --rebase
```

- 如果 pull 成功 → 继续处理用户请求
- 如果 pull 因网络问题失败 → 告知用户"⚠️ 无法同步远程仓库，继续使用本地版本"，不阻塞后续操作
- 如果 pull 产生冲突 → 告知用户"⚠️ git pull 产生冲突，请手动解决"，继续处理用户请求不阻塞
- 此步骤的目的是确保本地编辑基于最新版本，避免 push 时冲突

## 文件命名约定

- `SKILL.md` — **路由型**：Claude Code skill 入口或路由文件，包含检索指令和流程描述
- `KNOWLEDGE.md` — **知识型**：纯领域知识 dump，不包含路由逻辑

路由型文件分布在各级目录入口（如 `performance/SKILL.md`），知识型文件分布在叶子目录（如 `performance/system-tuning/KNOWLEDGE.md`）。

## 请求类型判断与路由规则

收到用户请求后，先按以下分类判断意图：

| 请求类型 | 判断特征 | 应检索的目录 |
|----------|----------|--------------|
| **论文/资料解析** | 用户提供了论文链接/PDF/标题，或要求“读这篇论文”“总结这篇文章”“写阅读笔记” | `common/knowledge-synthesis/` |
| **阅读记录查询** | 用户问“我读过什么”“这篇论文读过吗”“某篇资料归档在哪” | `history/` |
| **故障排查 / 运维问题** | 涉及系统报错、服务异常、部署失败、监控告警、Linux/K8s 运维 | `operations/` |
| **性能优化问题** | 涉及 latency、throughput、CPU、内存、I/O、并发、并行、数据库、网络、GPU 性能、内核调优 | `performance/` |
| **架构设计 / 体系结构问题** | 涉及分布式系统、微服务、数据系统、可靠性、云原生、容量设计、CPU/GPU 微架构、存储层次、互连网络、近存/存内计算 | `architecture/` |
| **算法问题** | 涉及资源调度、负载均衡、共识、分布式算法、最优化、问题求解、图算法、流式算法、并发数据结构、复杂度分析 | `algorithms/` |
| **OS 安全与程序分析** | 涉及访问控制、内存沙箱、动态追踪/插桩、策略提取、二进制分析、移动端安全 | `security/` |
| **网络系统问题** | 涉及用户态网络 runtime、内核网络栈、TCP/RPC 调度、去中心化网络架构 | `network/` |
| **程序分析 / 运行时优化** | 涉及推测性执行、动态插桩、effect tracing、shell 脚本优化、syscall 拦截 | `operations/program-analysis/` |
| **开源项目源码分析** | 涉及 vLLM / SGLang / Mooncake / gem5 等开源项目的内部机制、架构设计、关键路径分析 | `open-source-code-analysis/` |
| **通用工具 / 检查清单 / 诊断手册** | 涉及脚本、常用命令、上线检查、排错流程 | `common/` |
| **知识库组织问题** | 用户问”这个应该放哪””如何归档””skill 目录怎么设计” | 当前文件 + 各一级 `SKILL.md` |
| **写作润色** | 用户要求”润色一下””润色这段话””polish 一下””帮我改改表达” | `common/writing-polish/` |
| **论文评价/了解方向/最新进展** | 用户要求”评价一下这篇论文””xxx 方向有什么最新进展””了解一下 xxx””有哪些方案””梳理一下””对比一下” | 先查 `history/metadata.json` 过滤候选论文 → 读相关 KNOWLEDGE.md → 综合回答。**自由探索/跨领域综合/vibe 查询归入此类** |
| **工业可用性查询** | 用户问”哪些论文能直接用到生产环境””快速判断有没有能用在工业代码上的” | 查 `history/metadata.json` 中 `industrial_applicability: “high”` 或 `”medium”` 的条目，按 tags 过滤 |
| **技术倒排查** | 用户问”哪些论文用了 DualPipe””KV cache offloading 有哪些方案” | 查 `history/metadata.json` 的 `technique_index` 或 `tag_index` |
| **我读过...吗** | 用户问”我读过 X 吗””X 这篇论文读过吗” | `history/` + DBLP fuzzy match |
| **BibTeX 收集/导出** | “collect-bibtex””export-bibtex””导出引用” | `history/bibtex-buffer.json` |
| **阅读队列** | “添加到阅读队列””查看阅读队列””处理下一篇” | `history/reading-queue.json` |

**特殊规则**：
- **写作润色**请求**不触发知识库写入**——不更新 KNOWLEDGE.md、不修改 reading-log.md、不 commit
- **论文评价/了解方向**——先检索已有知识（history/对应领域 KNOWLEDGE.md），再基于检索内容给出评价/概述；如果有未覆盖的新信息，引导用户提供更多输入

如果请求同时涉及多个类型，按以下优先级组合检索：
1. 先定位主要类型（论文解析 / 运维 / 性能 / 架构 / 算法 / 安全 / 网络 / 程序分析 / 通用）。
2. 再检索跨领域支持文件（如 `common/checklists/`、`common/diagnosis-playbooks/`）。

## 检索与回答流程

1. **读取对应一级入口**
   - 论文解析：读取 `common/knowledge-synthesis/SKILL.md`
   - 写作润色：读取 `common/writing-polish/SKILL.md`
   - 运维：读取 `operations/SKILL.md`
   - 性能：读取 `performance/SKILL.md`
   - 架构：读取 `architecture/SKILL.md`
   - 算法：读取 `algorithms/SKILL.md`
   - 安全：读取 `security/SKILL.md`
   - 网络：读取 `network/SKILL.md`
   - 开源项目：读取 `open-source-code-analysis/SKILL.md`
   - 通用：读取 `common/SKILL.md`

2. **根据具体主题，深入二级子目录**
   - 例如用户问“Linux I/O 调度优化”，在读取 `performance/SKILL.md` 后，进一步读取 `performance/system-tuning/KNOWLEDGE.md`。
   - 例如用户问”Kubernetes Pod 调度失败”，在读取 `operations/SKILL.md` 后，进一步读取 `operations/container-k8s/SKILL.md` 或 `operations/incident-response/SKILL.md`。
   - 例如用户问”TCP RPC 消息调度优化”，在读取 `network/SKILL.md` 后，进一步读取 `network/os-networking/KNOWLEDGE.md`。
   - 例如用户问“一致性哈希怎么做负载均衡”，在读取 `algorithms/SKILL.md` 后，进一步读取 `algorithms/load-balancing/KNOWLEDGE.md`。

3. **如果存在案例/检查清单/脚本，一并读取**
   - 故障排查类问题优先查看 `common/diagnosis-playbooks/`。
   - 上线/变更类问题优先查看 `common/checklists/`。

4. **基于检索内容组织回答**
   - 先说明信息来源（引用了哪些 skill 文件）。
   - 再按”问题定义 → 相关知识 → 具体建议/命令/配置 → 验证方式”输出。
   - 如果是论文解析，按 `common/knowledge-synthesis/SKILL.md` 的模板输出。
   - **如果是写作润色，按 `common/writing-polish/SKILL.md` 的流程输出，不修改知识库。**

## 写作润色的特殊处理

当用户要求润色语句时：

1. 读取 `common/writing-polish/SKILL.md`，对照其中的短语库和润色流程。
2. 识别用户输入中的生硬/口语化表达，替换为更地道、学术化的表达。
3. 保持原意不变，仅优化表达方式。
4. **⚠️ 润色操作不触发后置操作**：不更新 KNOWLEDGE.md、不修改 reading-log.md、不 commit/push。
5. 如果用户输入的语句过于简短或缺少上下文（不知道是论文/邮件/日常），先追问语境。

## 论文/资料解析的特殊处理

当用户要求解析论文或技术资料时，按四轮递进流程执行：

1. **R1 速览**（必须）：先读取 `common/knowledge-synthesis/SKILL.md`，提取论文元数据 → 写入 `history/metadata.json` + `history/reading-log.md`。
   - 至少完成 R1 速览，判断是否值得 R2。
   - 如果用户明确要求深度解析，则自动进入 R2。
2. **⚠️ 论文命名**: 必须从论文正文（标题+首页）提取方案名和会议信息，构造规范名称 `方案名(会议'年份)`，例如 `PACT(ASPLOS'26)`。**禁止使用 PDF 文件名或 URL 路径作为论文的引用名称**。详见 `common/knowledge-synthesis/SKILL.md` §0 论文命名规范。
3. **R2 深读**：提取可复用启发后，判断应归档到 `operations/`、`performance/`、`architecture/`、`algorithms/`、`security/`、`network/` 还是 `common/` 下的具体 skill。
4. ⚠️ **知识归档（‼️ 绝不可偷懒）**：将可复用启发写入对应子目录的 `KNOWLEDGE.md`。如果目标子目录不存在，**应主动创建**子目录和 `KNOWLEDGE.md`。如果 `KNOWLEDGE.md` 已存在，在对应的二级 `##` 章节下追加新的知识点。禁止只写论文笔记而不更新 `KNOWLEDGE.md`。

   **每篇论文在 `KNOWLEDGE.md` 中的归档必须包含以下完整结构（不是仅加一行表条目！）：**

   ```markdown
   ## <主题名> (<方案名>)

   ### 核心问题
   <一段话描述为什么这个问题重要、现有方案为什么不够>

   ### 关键洞察
   1. **”<洞察一句话>”**：<解释>
   2. ...
   - 来源：<方案名(会议'年份)>

   ### 实践启发
   - **”<启发>”**：<如何应用到自己的项目/其他场景>
   ```

   **⚠️ 仅添加子主题表条目（`| 主题 | 关键词 | 来源 |`）而不写完整的 `##` 章节 = 严重偷懒。每条子主题表条目必须对应一个完整的三段式 `##` 章节。此规则无例外。**
5. 如果用户没有明确说”不要记录”，解析完成后更新 `history/metadata.json`（填充 `techniques`, `r2_insights`, `applicability_why` 等字段）和 `history/reading-log.md`。
6. R3 交叉验证和 R4 对抗审视可以延迟到后续消息中执行，或者在同一消息中快速完成（简版）。
7. 如果现有 skill 无法覆盖新知，建议用户新建 skill 子目录，并给出推荐路径。

## 输出规范

- **引用来源**：回答开头或每节末尾说明参考了哪些 `SKILL.md` 或子目录。
- **中文为主**，标准术语保留英文（如 throughput、latency、scalability、ablation、baseline）。
- **区分事实与推断**：从 skill 中读到的内容是事实；你基于事实的推理要明确标注。
- **结构化输出**：优先用 bullet、表格、代码块，避免大段散文。
- **不确定时说明**：如果 skill 中没有相关信息，直接说“当前知识库没有覆盖这一点”，并建议用户补充到对应 skill。

## 知识库维护建议

当发现以下情况时，提示用户更新知识库：

- 某个问题反复被问到，但对应 skill 里还没有答案 → 补充到对应 `SKILL.md`。
- 论文/资料的启发没有被现有 skill 覆盖 → 新建 skill 子目录。
- 现有 skill 目录结构不清晰 → 参考当前文件和各一级 `SKILL.md` 的目录说明重新设计。

## 特殊命令

| 命令 | 行为 |
|------|------|
| `/domain-knowledge collect-bibtex <dblp_key> --citation-key <key>` | 查询 DBLP 获取 BibTeX，改写 citation key 后缓存到 `history/bibtex-buffer.json` |
| `/domain-knowledge export-bibtex [output_path]` | 导出所有缓存的 BibTeX 到 .bib 文件（默认 `~/papers.bib`），清空缓存 |
| `/domain-knowledge 添加到阅读队列 <URL> [--priority high\|medium\|low]` | 将论文 URL 追加到 `history/reading-queue.json` |
| `/domain-knowledge 查看阅读队列` | 列出队列中所有待读论文，按优先级排序 |
| `/domain-knowledge 处理阅读队列的下一篇` | 从队列取出下一篇（优先级最高的 pending），启动 R1 解析 |
| `/domain-knowledge backfill-metadata [--dry-run]` | 批量回溯修复 metadata.json 中空的 title/authors 字段（通过 DBLP 模糊搜索） |

## 目录索引

- `operations/SKILL.md` — 运维与 SRE
- `performance/SKILL.md` — 性能优化
- `architecture/SKILL.md` — 架构设计与计算机体系结构
- `algorithms/SKILL.md` — 算法
- `security/SKILL.md` — OS 安全与程序分析
- `network/SKILL.md` — 网络系统
- `open-source-code-analysis/SKILL.md` — 开源项目源码分析（vLLM、SGLang、Mooncake、gem5）
- `common/SKILL.md` — 通用工具、检查清单、诊断手册、知识整合方法论
- `common/writing-polish/SKILL.md` — 写作润色，学术中英文短语库
- `history/SKILL.md` — 阅读与解析记录说明

## ⚠️ 后置操作：提交并推送变更（必须最后执行）

**仅当请求类型属于「论文/资料解析」「新增知识点」「知识库维护」等会产生知识库变更的类型时，才执行以下后置操作。写作润色请求直接跳过本步。**

**在完成所有知识库变更（新建文件、编辑 SKILL.md、追加阅读记录等）之后，必须 commit 并 push：**

```bash
cd ~/.claude/skills/domain-knowledge && git add -A && git diff --cached --stat && git commit -m "<变更摘要>" && git push
```

**规则**：
- `<变更摘要>` 格式：`"<动作>: <简要描述>"`，例如 `"papers: add PACT ASPLOS'26 reading note"` 或 `"skill: update system-tuning with tiered memory insights"`
- **仅在 `git diff --cached` 非空时执行**（有实际变更才 commit），无变更则跳过并告知用户
- push 失败时告知用户（网络问题等），但不重试、不阻塞
- commit 信息中**不要**加 `Co-Authored-By: Claude <noreply@anthropic.com>`
- 一整个调用中的所有变更聚合成 **1 次 commit**，不要多次提交

详细配置见 `config.md`。

**⚠️ 每次 commit 前须更新统计和索引**：
1. `python3 history/rebuild_index.py` — 重建技术/标签倒排索引
2. `python3 scripts/generate_readme_stats.py` — 自动生成 README.md 统计区域
3. 如为新增论文：在 `history/metadata.json` 追加条目后运行上述两个脚本

```markdown
- **总计**: 13 篇
- **会议分布**: ASPLOS 4 篇（'22–'26），OSDI 9 篇（'26）
- **领域分布**:
  - CXL/内存系统/可观测性: 8 篇（PACT, TMO, M5, CAMP, RamRyder, MAC, NEMO, OBASE）
  - LLM 推理服务: 5 篇（Strata, ECHO, DirectKV, LMetric, Prism）
- **最后更新**: YYYY-MM-DD
```

领域分类依据 `history/reading-log.md` 的「归档位置」列和「备注」列综合判断。
