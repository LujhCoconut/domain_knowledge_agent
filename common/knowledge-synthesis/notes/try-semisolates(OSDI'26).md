# try / Semisolates (OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-lamprou.pdf
- **全称**: Controlling Opaque-Component Effects with Semisolates and Try
- **系统名**: try (command-line tool) / semisolates (abstraction)
- **作者**: Evangelos Lamprou* (Brown), Tianyu (Ezri) Zhu* (Stevens), Di Jin, Grigoris Ntousakis (Brown), Georgios Liargkovas (Columbia), Calvin Eng (Brown), Konstantinos Kallas (UCLA), Michael Greenberg (Stevens), Nikos Vasilakis (Brown)
- **开源**: https://binpa.sh/try
- **类型**: 论文-系统 (OS + tooling + security)
- **一句话 TL;DR**: `try` — 一个**无特权、语言无关、高阶命令**，让你在执行任何 opaque component (curl piped to sh, LLM-generated script, third-party installer) 之前先**预览它对文件系统和环境的副作用**（创建/修改/删除了什么），然后选择性地 apply、revert 或 partial hide 这些 effects。它与容器不同——**不完全隔离**，而是在当前的半隔离环境中让 component 运行但捕获其外部可见效果供审查。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **Semisolate** | 部分隔离的抽象——不完全隔离（container）但也非完全暴露（bare execution） | 核心抽象：在 current environment 中运行，但捕获 effects |
| **try** | `try <command>` — 执行命令并自动捕获其文件系统副作用 | 面向用户的 CLI 实现 |
| **Opaque component** | 你不完全了解或信任的程序/脚本/installer — 但需要运行它 | try 保护的典型目标 |
| **Effect** | 组件对文件系统的**外部可观察改变**（创建、修改、删除文件、环境变量等） | try 捕获和控制的核心对象 |
| **Filesystem overlay/interposition** | 在组件和实际文件系统之间的拦截层：所有文件系统操作先经过 try 的 semisolate | try 的核心机制 |
| **Effect control** | 四个维度：introspect (检查做了什么) → selectively apply (选择性地接受) → revert (撤销) → partially hide (对组件隐藏文件) | 比 container 的 "isolate all" 更精细 |
| **Higher-order, language-agnostic** | `try` 包裹任意命令（bash/python/node/rust installer），不依赖被包裹程序的语言 | 通用性 |

## 背景与动机

### 问题
现实中有大量 **opaque components** —— 你不了解或不能信任的程序，但需要执行：
- `curl ... | bash` （安装 rustup、nvm、pip install 等）
- LLM 生成的脚本（"cleans up directory" → 实际删除了用户的全部文件 [§52]）
- 第三方 CI/CD pipeline 步骤
- Stack Overflow 上的 `find -exec` 命令
- 遗留二进制 installer（闭源、无源码）

当前用户面对这类组件的选择是：
1. **盲目信任**：直接执行 → 可能的灾难性后果
2. **完全隔离**：container/VM → 可以看见 effects 但没有**细粒度控制**（"允许这个文件创建，但阻止那个文件修改"）
3. **手动审查**：阅读源码/脚本 → 太耗时、不现实（尤其是二进制）

### 核心洞察
> 不是**完全隔离**，也不是**完全暴露**——而是**半隔离**。
> Component 在当前的 environment 中运行但通过拦截层；捕获其文件系统副作用 → 用户审查 → 决定接受、撤销或部分接受。

### 与 Containers 的对比

| | Container (Docker/VM) | **try semisolate** |
|---|---|---|
| 隔离程度 | 完全隔离 | **部分隔离** |
| 能否看到当前文件系统 | 否（fresh empty env） | **是**（component 可以读取当前文件） |
| Effects 是否自动捕获 | 否（需要 volume mount 等复杂配置） | **是**（自动） |
| 精细控制 effects | 否（"全部接受"或"全部拒绝"） | **是**（选择性地 apply/remove） |
| 权限 | 需要 root/daemon | **无特权** |

### 我的分析
这是 OSDI '26 中最"工具化"的一篇论文——它不是一个大型分布式系统或 GPU 训练优化，而是一个**每个开发者每天都能用**的命令行工具。try 的核心思想非常优雅："你不信任这个 installer，但你也不需要为了运行它而启动一个完整的 container —— 只需要 interpose 它的文件系统 effects 然后审查"。

## 方案介绍

### try 的工作流程

```
$ try sh install.sh

1. try 为 install.sh 创建一个 semisolate — 拦截所有文件系统操作
2. install.sh 执行 — 可以看到/读取当前文件系统，但在 try 的管控下
3. install.sh 执行完毕 — try 显示总结：哪些文件被创建/修改/删除
4. 用户审查 → 决策：
   - apply all   → 所有 effects 写入真实文件系统
   - apply partial → 选择性地接受某些 effects
   - revert all  → 丢弃所有 effects
   - hide files  → 对组件隐藏某些文件
```

### Semisolate 机制

- **Filesystem overlay**：创建当前文件系统的"半隔离视图"——component 读取的是真实的文件系统，但写入先进入 overlay
- **Automatic effect capture**：所有磁盘写入都被截获并存储，标记为 {created, modified, deleted}
- **Effect introspect**：执行后列出所有 effects，类似 `git diff` 的文件变更视图
- **Effect manipulation**：
  - `apply`: 将效果写入真实文件系统
  - `revert`: 丢弃
  - `partial apply`: 交互式选择哪些文件的效果要保留

### 实现要点
- Unprivileged（无需 root）
- Language-agnostic（`try python script.py`, `try curl ... | sh`, `try make install`）
- Higher-order（`try try ./install.sh` 可以嵌套）
- 基于 Linux 的 `ptrace`/`seccomp`/`LD_PRELOAD` 等无特权拦截机制

## 证据与评估

- 多个现实案例验证（LLM 生成脚本规避、curl-pipe-sh 审查、第三方 installers）
- 在学术和生产环境中使用
- 性能开销适度（在每个案例的"可接受水平"内）

## 整体评估

### 真正的新意
1. **"semisolate"作为一等系统抽象**：在 "bare execution"和 "full containerization"之间的空白地带——既非完全信任，也非完全隔离
2. **Effect 的可审查和可控**：不只是"看到 component 做了什么"，而是可以选择性地 apply/revert/hide —— 类似 git 的 stage/unstage 操作，但针对文件系统 effects
3. **无特权、语言无关、高阶**：这使 try 适用于任何场景，无需 root 或特殊 runtime

### 优点
- **实用性极强**：每个开发者都会遇到 opaque component 的场景
- **填补了生态位的空白**："我不信任这个 installer 但我也懒得搞个 container"是一大类未满足的需求
- **与容器正交而非竞争**：try 解决的是"当前环境内的 partial isolation"，容器解决的是"全新环境的 full isolation"

### 局限
- **仅文件系统 effects**（当前实现）：不捕获网络 effects（组件仍然可以建立网络连接）或 CPU/memory 资源消耗
- **拦截层可能被 bypass**：强对抗的恶意组件可能试图检测和绕过 filesystem overlay（取决于具体实现机制）
- **需要 Linux 支持**：依赖 `ptrace`/`seccomp`/`LD_PRELOAD` 等 Linux 特定机制

### 可复用启发

1. **"Semisolate"是系统设计中一个极具价值的中间地带**：很多场景不需要 full containerization 的开销（CPU/memory/配置复杂度）但需要比"盲目信任"更安全的执行。适用于 CI/CD pipeline、plugin 系统、laptop 开发环境
2. **"Effect"作为一等抽象**：将程序的外部可观察行为定义为"effects"，并允许 inspect/apply/revert 这些 effects —— 这个抽象可以推广到其他类型的副作用（数据库写入、API 调用、消息发送）
3. **"不要隔离，要截获"**：Container 的核心哲学是 "不让 component 看到当前环境"；try 的哲学是 "让 component 看到当前环境，但拦截它的修改"
