# Open Source Code Analysis

对主流开源项目的源码级分析，涵盖架构设计、核心机制、关键路径和设计权衡。每个项目按子模块组织，叶子目录存放 `KNOWLEDGE.md`。

## 覆盖项目

| 项目 | 目录 | 子模块 |
|------|------|--------|
| vLLM | `vllm/` | `scheduler/`、`kv_connector/`、`worker/` |
| SGLang | `sglang/` | （待补充） |
| Mooncake | `mooncake/` | `store/`、`transfer-engine/`、`ep/`、`integration/`、`p2p-store/` |
| gem5 | `gem5/` | （待补充） |

## 子主题总表

| 项目 | 子模块 | 主题 | 关键词 | 技术点 | 来源 |
|------|--------|------|--------|--------|------|
| vLLM | scheduler | 三队列模型 | scheduler, continuous batching, KV cache | three-queue scheduling, break-vs-continue guard, num_computed_tokens guard re-trigger | `scheduler.py:64-856` |
| vLLM | scheduler | Step 生命周期 | engine, forward pass, GPU | busy loop stepping, non_block execute_model | `core.py:439-468` |
| vLLM | kv_connector | Scheduler/Worker 角色分离 | KV connector, MooncakeStore, ZMQ | role separation, ZMQ REQ/REP IPC, get_finished deferred enqueue | `mixin.py:78-103`, `worker.py:1390-1451` |
| vLLM | kv_connector | exists→get 时间窗口 | scheduler, KV connector, async loading | guard re-trigger on allocate failure, compute-transfer overlap | `scheduler.py:596-766` |
| vLLM | worker | GPU forward + KV connector 集成 | worker, GPU, forward pass | context manager KV lifecycle, background transfer threads | `gpu_model_runner.py:4034-4070` |
| vLLM | worker | MooncakeStore 后台线程 | MooncakeStore, background thread | batch_get_into_multi_buffers, send/recv thread model | `worker.py:437-858` |
| Mooncake | store | Lease 三层保护 | lease, eviction, memory management, DRAM | GrantLease(hard_ms,soft_ms) dual timeline, ExistKey also grants lease | `master_service.cpp:175-177,3306-3308` |
| Mooncake | store | Eviction 判定链 | soft pin, hard pin, BatchEvict | IsHardPinned/IsLeaseExpired/IsSoftPinned guard chain, multi-thread parallel collection | `master_service.cpp:6708-7110` |
| Mooncake | store | Replica refcnt | refcnt, promotion, offload | refcnt pin on source LOCAL_DISK, orthogonal to lease | `replica.h:329-332`, `master_service.cpp:4037` |
| Mooncake | store | Promotion-on-Hit | promotion, SSD offload, Count-Min Sketch, heartbeat | TryPushPromotionQueue admission gating, PROCESSING MEMORY replica staging | `master_service.cpp:5538-5930` |
| Mooncake | transfer-engine | 声明式架构 | TENT, declarative API, NIXL | tent_submit declarative intent API, Unified Segment abstraction | [TENT #1](https://renfeng.org/zh/posts/tent-internal-arch/) |
| Mooncake | transfer-engine | 晚期绑定 + 路径合成 | late binding, path synthesis, orchestrator | late binding path resolution, Tier-aware affinity sorting, autonomous multi-hop pipeline | [TENT #1,#2](https://renfeng.org/zh/posts/tent-internal-orchestrator-part-1/) |
| Mooncake | transfer-engine | Transport 插件 | plugin backend, NVLink, RDMA, GDS, io_uring, SHM/CXL | plugin-based Transport backend, Capabilities matrix, transport_attrs encapsulation | [TENT #2](https://renfeng.org/zh/posts/tent-internal-orchestrator-part-1/) |
| Mooncake | transfer-engine | Slice Spraying | slice spraying, EWMA, RDMA, multi-rail | EWMA single-parameter bandwidth estimation, proportional allocation by predicted_time | [TENT #3](https://renfeng.org/zh/posts/tent-internal-slice-spraying-and-qos/) |
| Mooncake | transfer-engine | QoS 机制 | QoS, priority scheduling | strict priority + anti-starvation timeout, cross-process time-slot coordination (2ms × 3) | [TENT #3](https://renfeng.org/zh/posts/tent-internal-slice-spraying-and-qos/) |

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
