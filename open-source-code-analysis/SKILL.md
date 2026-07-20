# Open Source Code Analysis

对主流开源项目的源码级分析，涵盖架构设计、核心机制、关键路径和设计权衡。按项目组织，每个子目录对应一个项目。

## 覆盖项目

| 项目 | 目录 | 核心关注点 |
|------|------|------------|
| vLLM | `vllm/` | Continuous batching 调度器、KV cache 管理、KV connector 框架、前缀缓存 |
| SGLang | `sglang/` | （待补充） |
| Mooncake | `mooncake/` | 分布式 KV Store、Transfer Engine、SSD offload/prefetch、三层存储 |
| gem5 | `gem5/` | （待补充） |

## 检索与回答流程

1. 根据用户提到的项目名，直接进入对应子目录读取 `KNOWLEDGE.md`
2. 如果涉及跨项目对比（如 vLLM vs SGLang 的调度器差异），同时读取两个项目的 KNOWLEDGE.md
3. 如果用户问的项目尚未覆盖，创建对应子目录并记录可分析的源码路径
4. 回答时引用 `KNOWLEDGE.md` 中的具体章节

## 知识归档规范

当通过源码阅读或 PR review 获得项目内部机制理解后，按以下模板写入对应项目的 `KNOWLEDGE.md`：

```markdown
## <机制名称>

### 背景
<一句话说明这个机制解决什么问题，在项目的什么位置>

### 核心数据结构
<关键类/结构体/队列，用代码片段说明>

### 完整流程
<从入口到出口的完整调用链，用箭头图 + 代码片段>

### 关键设计点
- **"<设计决策>"**：<为什么这样设计，不这样设计会怎样>

### 与其他模块的交互
<这个机制如何影响项目的其他部分>

### 源码位置
<文件路径 + 关键函数/类名 + 行号>
```

## 新增项目子目录

当需要分析新项目时：
1. 在 `open-source-code-analysis/` 下创建项目子目录和 `KNOWLEDGE.md`
2. 更新本文件的覆盖项目表
3. 如果项目涉及多个子模块（如 vLLM 的 scheduler 和 worker 侧），可以在 `KNOWLEDGE.md` 内用 `##` 二级标题区分
