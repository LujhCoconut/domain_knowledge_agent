# Common Tools & Templates

跨领域复用的工具、模板、检查清单与诊断手册。

## 子目录

| 目录 | 主题 | 适合归档的内容 |
|------|------|----------------|
| `knowledge-synthesis/` | 知识整合方法论 | 快速阅读论文/资料、提取核心启发、归档到已有 skill 或新建 skill 的流程与模板 |
| `tooling/` | 常用工具 | 脚本、CLI、编辑器/IDE 配置、效率工具 |
| `diagnosis-playbooks/` | 诊断手册 | 通用排错流程、分层定位法、常见错误码速查 |
| `checklists/` | 检查清单 | 上线前检查、安全基线、性能回归检查、架构评审清单 |

## 使用方式

- `checklists/` 中的清单可以直接在 code review 或变更前逐项打勾。
- `diagnosis-playbooks/` 中的流程应与 `operations/incident-response/` 中的具体系统排错 skill 配合使用。
