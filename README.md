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

- **总计**: 115 篇
- **会议分布**: ASPLOS 4 篇（'22–'26），OSDI 111 篇（'26）
- **领域分布**:
  - CXL/内存系统/stall 回收: 10 篇
  - 存储层次/体系结构: 4 篇（Soul/GCP, Duhu, Blowfish, InfiniDefrag） — 见 `architecture/memory-storage-hierarchy/KNOWLEDGE.md`
  - 云基础设施/虚拟化: 8 篇（mwait-sched, Xkernel, Janus, Nested SEV, PowerSight, M3U, Quark, DVLA） — 见 `operations/cloud-infrastructure/KNOWLEDGE.md`
  - 云原生/解耦式服务: 5 篇（DGC, OpenTela, Arca, Spice, libDSE） — 见 `architecture/cloud-native/KNOWLEDGE.md`
  - LLM 推理服务: 9 篇（含 agentic workflow + 本地 CPU-GPU 混合 MoE + 批量推理协程调度）
  - LLM 大规模训练+数据管线: 10 篇（含 RL 五篇 + Kareus 训练能耗）
  - OS 安全/隐私/程序分析: 13 篇 — 见 `security/os-security/KNOWLEDGE.md`
  - 软件测试/DBMS/云服务: 2 篇（ValScope, S3 MBT） — 见 `algorithms/`, `operations/os-testing/KNOWLEDGE.md`
  - OS 内核/调优: 2 篇（kSTEP, ECO） — 见 `operations/os-performance-tuning/KNOWLEDGE.md`
  - 监控/可观测性: 6 篇 — 见 `operations/monitoring-observability/KNOWLEDGE.md`
  - 存储/文件系统: 9 篇（ByteDance DataPipeline, DeLFS, Espresso, FORGE, Oxbow, DINGO, Umap, Helmsman, WiseCode） — 见 `performance/storage-filesystem/KNOWLEDGE.md`
  - 程序分析与动态优化: 4 篇（hS, Incr, UCSan, Aletheia） — 见 `operations/program-analysis/KNOWLEDGE.md`
  - 并发数据结构: 1 篇（Arctic） — 见 `algorithms/concurrent-data-structures/KNOWLEDGE.md`
  - 资源调度与供给: 2 篇（SPADE, Quota Marketplace） — 见 `algorithms/resource-scheduling/KNOWLEDGE.md`
  - 分布式共识: 5 篇（Bodega, Pompē-SRO, Jetpack, Ambulance, LogDrive） — 见 `algorithms/distributed-consensus/KNOWLEDGE.md`
  - 图处理: 1 篇（Pluto） — 见 `algorithms/graph-processing/KNOWLEDGE.md`
  - 加速器架构与编译: 2 篇（TileLoom, μShell） — 见 `architecture/accelerators/KNOWLEDGE.md`
  - 网络系统: 7 篇（SBB, Rakaia, UEP, UCCL-Tran, BALBOA, DPA-Store, Sepia） — 见 `network/os-networking/KNOWLEDGE.md`
- **最后更新**: 2026-07-15

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
