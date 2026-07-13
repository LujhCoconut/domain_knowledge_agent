# Agent Skill Library

个人技能知识库，用于归档运维、性能优化、架构设计等领域的可复用经验。

## 目录结构

```
agent_skill/
├── operations/          # 运维与 SRE
├── performance/         # 性能优化
├── architecture/        # 架构设计
├── common/              # 通用工具、模板、检查清单、知识整合方法论
├── history/             # 阅读与解析记录
└── knowledge/           # 早期归档目录（已清空并迁移）
```

## 归档规范

1. **每个 skill 一个子目录**，目录内必须包含 `SKILL.md` 作为入口。
2. `SKILL.md` 中应说明：
   - 这个 skill 解决什么问题
   - 适用场景
   - 核心知识点/命令/配置
   - 常见坑与排查思路
3. 优先把内容归到 **operations / performance / architecture** 三大领域；`common` 放置跨领域复用的工具、模板、检查清单。
4. 避免在目录名中使用拼写错误或不一致的缩写。

## 快速导航

- [operations/README 与目录说明](./operations/SKILL.md)
- [performance/README 与目录说明](./performance/SKILL.md)
- [architecture/README 与目录说明](./architecture/SKILL.md)
- [common/README 与目录说明](./common/SKILL.md)

## 新增 skill 方向建议

- `operations/incident-response/<system>-failures`：某个系统的典型故障案例库。
- `performance/optimization-paradigms/<workload>-case-study`：具体工作负载的串/并/并发优化案例。
- `architecture/reliability-engineering/<pattern>-trade-offs`：某个可靠性模式的取舍分析。
