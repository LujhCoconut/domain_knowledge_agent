# Domain Knowledge 配置

本文件定义领域知识库的 Git 同步配置与自动化行为。

## Git 仓库

| 配置项 | 值 |
|--------|-----|
| **远程仓库** | `https://github.com/LujhCoconut/domain_knowledge_agent` |
| **默认分支** | `main` |
| **本地路径** | `~/.claude/skills/domain-knowledge/` |

## 自动同步策略

### 前置操作（每次 skill 被调用时自动执行）

在读取任何子目录 SKILL.md 之前，先执行：

```bash
cd ~/.claude/skills/domain-knowledge && git pull --rebase
```

- 目的：确保本地知识库与远程仓库一致，避免编辑冲突
- 失败处理：如果 pull 失败（网络问题、冲突等），**继续执行**不要阻塞用户的请求，但告知用户同步失败

### 后置操作（每次 skill 完成所有写入/编辑后自动执行）

在完成所有知识库变更（新增文件、编辑 SKILL.md、追加阅读记录等）之后，执行：

```bash
cd ~/.claude/skills/domain-knowledge && git add -A && git diff --cached --stat && git commit -m "<自动生成的提交信息>" && git push
```

- 提交信息格式：简洁描述本次变更，例如 `"papers: add PACT ASPLOS'26 reading note"` 或 `"skill: update system-tuning SKILL.md with PAC insights"`
- **仅在确实有变更时执行**（`git diff --cached` 非空），无变更则跳过
- 失败处理：如果 push 失败（网络问题等），告知用户但不要重试，也不阻塞后续操作
- **重要**：提交信息末尾不要添加 `Co-Authored-By: Claude <noreply@anthropic.com>`，这是个人知识库，不是代码项目

### 冲突处理

如果 `git pull --rebase` 产生冲突：
1. 报告用户有冲突发生
2. 不要自行解决冲突（个人知识库内容应由用户决断）
3. 继续执行用户的原始请求（不影响用户的使用）

## 变更频率

- 每次 `/domain-knowledge` 调用产生文件变更后都会自动 commit + push
- 单个调用可能产生 1 次 commit（聚合一整轮的所有变更）
