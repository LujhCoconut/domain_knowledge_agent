# Domain Knowledge Agent

一个基于 Claude Code 的个人领域知识库，自动将论文/技术资料解析、归档到结构化 skill 体系中，并支持 Git 远程同步。

## 项目是什么

这是一个 **Claude Code Skill**——当你用 `/domain-knowledge` 命令 + 论文链接/PDF 时，Claude 会：

1. 从论文标题+首页自动提取规范名称（如 `PACT(ASPLOS'26)`）
2. 按深度阅读模板输出结构化解析（术语、问题定义、方案、证据、局限、启发）
3. 新建/更新对应子领域的 `SKILL.md`，将可复用启发归档
4. 追加阅读记录到 `history/reading-log.md`
5. 自动 `git commit && git push` 推送到远程仓库

## 目录结构

```
domain-knowledge/
├── SKILL.md                  # 入口 skill — 请求路由 + 前置/后置操作
├── config.md                 # Git 仓库配置 + 自动同步策略
├── README.md                 # ← 你正在看的文件
├── history/                  # 阅读日志
├── common/                   # 通用工具、检查清单、知识合成模板
│   └── knowledge-synthesis/  #   论文解析模板 + 深度笔记
├── performance/              # 性能优化 → 内存系统、GPU/AI
├── architecture/             # 架构与体系结构 → 分布式、微架构、存储层次、加速器
├── operations/               # 运维与 SRE → 存储、监控、测试、云基础设施、内核调优
├── algorithms/               # 算法（待填充）
├── security/                 # OS 安全与程序分析 → 访问控制、沙箱、追踪
└── network/                  # 网络系统 → TCP/RPC、用户态 runtime
```

## 已覆盖的领域知识

<!-- 以下区域由 /domain-knowledge 后置操作自动更新，请勿手动编辑本节 -->

- **总计**: 194 篇
- **会议分布**: OSDI 133 篇（'26），FAST 43 篇（'26），NSDI 5 篇（'26），ASPLOS 4 篇（'22–'26），SOSP 3 篇（'23–'25），arXiv 2 篇（'26），ATC 1 篇（'25），HPCA 1 篇（'24），MICRO 1 篇（'24），SIGMOD 1 篇（'22）
- **领域分布**:
  - LLM 推理/GPU-AI/训练: 46 篇（Strata(OSDI'26)、ECHO(OSDI'26)、DirectKV(OSDI'26)…） — 见 `performance/gpu-ai-performance/KNOWLEDGE.md`
  - 存储/文件系统: 34 篇（ByteDance DataPipeline(OSDI'26)、DeLFS(OSDI'26)、Espresso(OSDI'26)…） — 见 `performance/storage-filesystem/KNOWLEDGE.md`
  - OS 安全/隐私/程序分析: 18 篇（USEC(OSDI'26)、Mohabi(OSDI'26)、Ichnaea(OSDI'26)…） — 见 `security/os-security/KNOWLEDGE.md`
  - CXL/内存系统/stall 回收: 16 篇（PACT(ASPLOS'26)、TMO(ASPLOS'22)、M5(ASPLOS'25)…） — 见 `performance/system-tuning/KNOWLEDGE.md`
  - 云基础设施/虚拟化: 12 篇（mwait-sched(OSDI'26)、Janus(OSDI'26)、Nested SEV(OSDI'26)…） — 见 `operations/cloud-infrastructure/KNOWLEDGE.md`
  - 存储层次/体系结构: 11 篇（Soul/GCP(OSDI'26)、Duhu(OSDI'26)、Blowfish(OSDI'26)…） — 见 `architecture/memory-storage-hierarchy/KNOWLEDGE.md`
  - 网络系统: 10 篇（PolicyCache(NSDI'26)、SBB(OSDI'26)、Rakaia(OSDI'26)…） — 见 `network/os-networking/KNOWLEDGE.md`
  - 监控/可观测性: 9 篇（CoreSec(OSDI'26)、StriaTrace(OSDI'26)、gigiprofiler(OSDI'26)…） — 见 `operations/monitoring-observability/KNOWLEDGE.md`
  - 云原生/解耦式服务: 7 篇（RamRyder(OSDI'26)、DGC(OSDI'26)、OpenTela(OSDI'26)…） — 见 `architecture/cloud-native/KNOWLEDGE.md`
  - 分布式共识: 6 篇（Bodega(OSDI'26)、Pompē-SRO(OSDI'26)、Jetpack(OSDI'26)…） — 见 `algorithms/distributed-consensus/KNOWLEDGE.md`
  - 程序分析与动态优化: 5 篇（hS(OSDI'26)、Incr(OSDI'26)、UCSan(OSDI'26)…） — 见 `operations/program-analysis/KNOWLEDGE.md`
  - 软件测试/DBMS/云服务: 4 篇（kSTEP(OSDI'26)、S3 MBT(OSDI'26)、Mimesys(OSDI'26)…） — 见 `operations/os-testing/KNOWLEDGE.md`
  - 加速器架构与编译: 3 篇（TileLoom(OSDI'26)、μShell(OSDI'26)、qTPU(OSDI'26)） — 见 `architecture/accelerators/KNOWLEDGE.md`
  - Agent-Native 软件设计: 2 篇（PithTrain(arXiv'26)、Jitskit(arXiv'26)） — 见 `architecture/agent-native-design/KNOWLEDGE.md`
  - OS 内核/调优: 2 篇（Xkernel(OSDI'26)、ECO(OSDI'26)） — 见 `operations/os-performance-tuning/KNOWLEDGE.md`
  - 并发数据结构: 2 篇（Arctic(OSDI'26)、FARLock(OSDI'26)） — 见 `algorithms/concurrent-data-structures/KNOWLEDGE.md`
  - 资源调度与供给: 2 篇（SPADE(OSDI'26)、Quota Marketplace(OSDI'26)） — 见 `algorithms/resource-scheduling/KNOWLEDGE.md`
  - 缓存算法: 2 篇（Merlin(OSDI'26)、S4-FIFO/LAH(OSDI'26)） — 见 `algorithms/cache-algorithms/KNOWLEDGE.md`
  - 图处理: 1 篇（Pluto(OSDI'26)） — 见 `algorithms/graph-processing/KNOWLEDGE.md`
- **🚀 新增功能**: JSON 结构化元数据 (`history/metadata.json`) + 技术倒排索引 + 四轮递进阅读 (R1-R4) + 工业可用性评分 + DBLP 自动元数据补全 + BibTeX 收集导出
- **最后更新**: 2026-07-24

<!-- 自动更新区域结束 -->

更多细节见各子目录下的 `SKILL.md`（路由文件）和 `KNOWLEDGE.md`（知识文件），如 `performance/system-tuning/KNOWLEDGE.md`。

## 如何使用

### 前置条件
- Claude Code CLI
- Git + SSH 访问 GitHub
- pdftotext (poppler-utils)

### 安装

```bash
# 克隆到 Claude Code skills 目录
git clone git@github.com:LujhCoconut/domain_knowledge_agent.git ~/.claude/skills/domain-knowledge
```

之后每次启动 Claude Code，该 skill 自动可用。

### 使用方式

```
/claude /domain-knowledge 解析一下这篇论文。https://arxiv.org/abs/...
/claude /domain-knowledge 我读过 TMO 那篇论文吗？  ← 查询阅读记录
/claude /domain-knowledge CXL 系统中怎么管理 page migration?  ← 检索已有知识
```

### 自动同步

- **启动时**: 自动 `git pull --rebase` 同步远程
- **结束时**: 如有变更自动 `git commit && git push`
- 详见 `config.md`

## ⚠️ 重要：自定义与微调

**这个仓库已包含我个人的领域知识（`SKILL.md` 中记录的经验 + `notes/` 中的论文笔记）。**

如果你要基于此建立自己的知识库：

1. **保留所有目录下的 `SKILL.md`** — 它们是知识的结构骨架
2. **自由微调 `SKILL.md` 内容** — 添加你的领域经验、修改归档分类、调整优先级
3. **可以删除 `notes/` 下的论文笔记** — 重新解析你感兴趣的论文时系统会自动生成新的
4. **可以清空 `history/reading-log.md`** — 那是我的阅读记录
5. **建议保留入口 `SKILL.md` 和 `config.md`** — 前者是 skill 路由逻辑，后者是 Git 同步配置；修改 `config.md` 中的仓库地址为你自己的

`common/knowledge-synthesis/SKILL.md` 中的 §0 论文命名规范建议保留，它确保所有论文使用统一的 `方案名(会议'年份)` 命名。
