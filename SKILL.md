---
name: domain-knowledge
description: 个人领域知识库路由 skill。当用户请求涉及论文/资料解析、Linux/Kubernetes 运维、性能优化（串行/并行/并发/系统/数据库/网络/GPU）、架构设计/计算机体系结构（分布式/微服务/云原生/微架构/存储层次/加速器）、算法（调度/负载均衡/共识/优化/问题求解/图算法/流式算法）、OS 安全与程序分析（MAC/SFI/动态追踪/策略提取/移动端分析）、故障排查或检查清单时，自动判断请求类型并调用对应子目录的 skill。
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
| **算法问题** | 涉及资源调度、负载均衡、共识、分布式算法、最优化、问题求解、图算法、流式算法、复杂度分析 | `algorithms/` |
| **OS 安全与程序分析** | 涉及访问控制、内存沙箱、动态追踪/插桩、策略提取、二进制分析、移动端安全 | `security/` |
| **网络系统问题** | 涉及用户态网络 runtime、内核网络栈、TCP/RPC 调度、去中心化网络架构 | `network/` |
| **程序分析 / 运行时优化** | 涉及推测性执行、动态插桩、effect tracing、shell 脚本优化、syscall 拦截 | `operations/program-analysis/` |
| **通用工具 / 检查清单 / 诊断手册** | 涉及脚本、常用命令、上线检查、排错流程 | `common/` |
| **知识库组织问题** | 用户问“这个应该放哪”“如何归档”“skill 目录怎么设计” | 当前文件 + 各一级 `SKILL.md` |

如果请求同时涉及多个类型，按以下优先级组合检索：
1. 先定位主要类型（论文解析 / 运维 / 性能 / 架构 / 算法 / 安全 / 网络 / 程序分析 / 通用）。
2. 再检索跨领域支持文件（如 `common/checklists/`、`common/diagnosis-playbooks/`）。

## 检索与回答流程

1. **读取对应一级入口**
   - 论文解析：读取 `common/knowledge-synthesis/SKILL.md`
   - 运维：读取 `operations/SKILL.md`
   - 性能：读取 `performance/SKILL.md`
   - 架构：读取 `architecture/SKILL.md`
   - 算法：读取 `algorithms/SKILL.md`
   - 安全：读取 `security/SKILL.md`
   - 网络：读取 `network/SKILL.md`
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
   - 再按“问题定义 → 相关知识 → 具体建议/命令/配置 → 验证方式”输出。
   - 如果是论文解析，按 `common/knowledge-synthesis/SKILL.md` 的模板输出。

## 论文/资料解析的特殊处理

当用户要求解析论文或技术资料时：

1. 先读取 `common/knowledge-synthesis/SKILL.md`，按其中的快速阅读或深度阅读模板执行。
2. **⚠️ 论文命名**: 必须从论文正文（标题+首页）提取方案名和会议信息，构造规范名称 `方案名(会议'年份)`，例如 `PACT(ASPLOS'26)`。**禁止使用 PDF 文件名或 URL 路径作为论文的引用名称**。详见 `common/knowledge-synthesis/SKILL.md` §0 论文命名规范。
3. 提取可复用启发后，判断应归档到 `operations/`、`performance/`、`architecture/`、`algorithms/`、`security/`、`network/` 还是 `common/` 下的具体 skill。
4. ⚠️ **知识归档**：将可复用启发写入对应子目录的 `KNOWLEDGE.md`。如果目标子目录不存在，**应主动创建**子目录和 `KNOWLEDGE.md`。如果 `KNOWLEDGE.md` 已存在，在对应的二级 `##` 章节下追加新的知识点。禁止只写论文笔记而不更新 `KNOWLEDGE.md`。
5. 如果用户没有明确说”不要记录”，解析完成后在 `history/reading-log.md` 中追加一条记录（资料标题列填写规范名称）。
6. 如果现有 skill 无法覆盖新知，建议用户新建 skill 子目录，并给出推荐路径。

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

## 目录索引

- `operations/SKILL.md` — 运维与 SRE
- `performance/SKILL.md` — 性能优化
- `architecture/SKILL.md` — 架构设计与计算机体系结构
- `algorithms/SKILL.md` — 算法
- `security/SKILL.md` — OS 安全与程序分析
- `network/SKILL.md` — 网络系统
- `common/SKILL.md` — 通用工具、检查清单、诊断手册、知识整合方法论
- `history/SKILL.md` — 阅读与解析记录说明

## ⚠️ 后置操作：提交并推送变更（必须最后执行）

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

**⚠️ 每次 commit 前须更新 `README.md`**：从 `history/reading-log.md` 统计总篇数、会议分布和领域分布，写入 README.md 中 `<!-- 以下区域由 /domain-knowledge 后置操作自动更新` 和 `<!-- 自动更新区域结束 -->` 之间的区域。格式示例：

```markdown
- **总计**: 13 篇
- **会议分布**: ASPLOS 4 篇（'22–'26），OSDI 9 篇（'26）
- **领域分布**:
  - CXL/内存系统/可观测性: 8 篇（PACT, TMO, M5, CAMP, RamRyder, MAC, NEMO, OBASE）
  - LLM 推理服务: 5 篇（Strata, ECHO, DirectKV, LMetric, Prism）
- **最后更新**: YYYY-MM-DD
```

领域分类依据 `history/reading-log.md` 的「归档位置」列和「备注」列综合判断。
