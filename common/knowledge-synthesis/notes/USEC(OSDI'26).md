# USEC(OSDI'26)

- **来源**: OSDI '26 (Operational Systems Track), https://www.usenix.org/system/files/osdi26-jiang-yu.pdf
- **全称**: USEC: A User-Requirement-Driven Mandatory Access Control Framework for Operating Systems
- **作者**: Yu Jiang, Wenhuan Liu, Fuchen Ma*, Yuheng Shen, Yuanliang Chen* (Tsinghua), Lei Zhang, He Li (UnionTech), Quan Zhang, Chijin Zhou (ECNU)
- **类型**: 论文-系统 (Operational Systems — 安全 + OS)
- **部署**: 8,000,000+ 企业终端, 210+ 安全厂商 (QiAnXin, 360, NSFOCUS)
- **一句话 TL;DR**: 重新设计 Linux MAC 框架 — 用 resource-centric policy（从"进程能访问什么"转为"谁可以动这个资源"）+ demand-driven enforcement（仅保护声明的资源时启用 hooks）+ binary-compatible LSM 接口（与 SELinux 共存）。策略代码比 SELinux 少 **10×**，运行时 overhead 低 **3.4-17.1%**，已部署 **800 万+ 端点**。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **MAC** (Mandatory Access Control) | 由 OS 内核强制执行的访问控制，用户无法绕过 | USEC 的目标机制 |
| **LSM** (Linux Security Modules) | Linux 内核的安全 hook 框架 | USEC 基于 LSM 实现 |
| **SELinux** | NSA 开发的 Linux MAC 系统（基于 type enforcement） | 主要对比 baseline |
| **Resource-centric policy** | 以资源为锚点的策略模型（"谁可以动这个文件"）| USEC 核心创新 #1 |
| **Demand-driven enforcement** | 仅对声明的 capability 相关路径启用 hook 检查 | USEC 核心创新 #2 |
| **Capability set C** | 部署时声明的一组受保护能力（如 FILE_WRITE, PROC_FORK） | 驱动 retained-hook 解析 |
| **Retained-hook bitmap** | 全局位图，每 bit 对应一个内核 hook；只有声明的 capability 相关的 hook 才是 enabled | 选择性执行的机制 |
| **Capability dictionary** | 每个 capability → {TE permissions, hook set} 的映射表 | 内核版本感知的编译时解析 |
| **UAVC** (USEC Access Vector Cache) | USEC 版本的 AVC 缓存（与 SELinux 的 AVC 分开） | 加速热路径的重复决策 |
| **Compatibility security interface** | 运行时 dispatcher + hook mapping table + validation | 让 vendor custom hooks 与 SELinux 共存 |

## 背景与动机

### 问题
SELinux 在现实中难以部署：
- **配置复杂**: 管理员需要维护数千条低层规则，分布在多个策略模块中
- **性能开销高**: 每个 syscall 都要经过多个 LSM hook 检查（即使策略最终允许），open() 延迟最高 +87%
- **兼容性差**: 启用 enforcing 模式后很多企业应用直接 failure（Oracle HSF、Dell SDC 等）

**主流 Linux 发行版和企业部署中普遍禁用 SELinux**（或设为 permissive mode）

### 三个核心挑战 (Motivation Sections 3.1-3.3)

**C1: 策略配置复杂**。SELinux 需要：
- 定义 type、attribute、allow rules、file_contexts、constraints 跨多个 .te/.if/.fc 模块
- 一个简单的 "agent 数据目录只有 agent 能写" 需要跨多个域类型和约束
- 小型更改需要编辑多个模块
- **以 camera device 为例**: SELinux 需要 3 个新 attribute + interface 定义 + 模块间绑定 → >300 行；而 USEC 用单个 JSON object

**C2: 运行时开销**。SELinux 的"全覆盖"模式：
- 在每个 syscall 路径上安装大量 hooks（open() 经过 3-4 个检查点）
- 即使策略允许，每个 hook 仍然执行 AVC cache 查找 + 同步
- 直接导致 performance tax，而大部分检查实际上对声明的保护目标无贡献
- **以 DBus 访问控制为例**: AT-SPI interface 下数十个 method，其中大多数是 read-only 查询 → SELinux 无法区分，全部 mediation

**C3: 兼容性断裂**。SELinux 在 enforcing 下：
- 改变 LSM hook 的执行顺序和数量 → 影响 vendor kernel patch 的行为
- 基于 type 的策略与 pathname-based 安装/更新场景冲突
- 应用程序在安装、升级、备份路径上的写操作被静默 deny

### 威胁模型
- 攻击者可以执行非特权或应用级别代码，通过正常 kernel 接口（文件、IPC、设备、网络）尝试访问 protected resources
- USEC **不**尝试自动推断所有需要保护的资源 — 范围是「声明的 capability set 所覆盖的资源的**封闭边界保护**」
- 非声明资源回退到 DAC（不受 USEC 限制）

### 我的分析
这是 OSDI '26 的 Operational Systems track（即工业/部署 track）论文，也是 15 篇中第一篇 OS 安全方向的。USEC 的核心哲学是 **"protect what matters, leave the rest alone"** — 这和传统 MAC 的 "mediate everything" 有本质区别。其 engineering wisdom 在于认识到安全厂商 care 的只是少数高价值资源，"全量 mediation" 既无必要又带来配置、性能、兼容性的三重成本。

## 方案介绍

### 三大支柱

**1. Resource-Centric Policy Model (§4.2)**
- **逆转方向**: SELinux/AppArmor 是 process-centric（"这个进程能访问什么"），USEC 是 resource-centric（"谁能 touch 这个资源"）
- **JSON-based 声明**: 每个策略规则锚定在资源描述符上（file path, device node, socket endpoint, mount point）
- **身份位图**: 用 bitmap 表示 principals，规则只需声明"具有 AGENT 或 SECADMIN 位的进程可以 write 这个资源"
- **资源类明确**: device, file, socket, process 等 — 属性 built into JSON schema（如 camera 的 devtype, ATSPI 的 dbus_path）
- **编译流程**: JSON → USEC Policy Compiler → identity-bitmap layout + compact rule table → 内核 rule lookup

**减少量** (UOS V25 部署数据):
| 指标 | SELinux | USEC | 减少 |
|------|---------|------|------|
| 策略模块 | 320 | 11 | 29× |
| 策略文件 | 2.1 MB | 949 KB | 2.2× |
| file_contexts 规则 | 5,428 | 1,577 | 3.4× |
| homedirs 规则 | 408 | 65 | 6.3× |
| 策略代码行 | — | — | **10×** |

**2. Demand-Driven Enforcement (§4.3)**
- **Capability declaration**: 安全厂商声明他们需要的 security-critical capabilities
- **Capability→hook resolution**: policy compiler 查询 capability dictionary → 展开为 TE permissions 和 hook 集合
  - 例: `FILE_WRITE` → permissions `{write, open, getattr, ...}` → hooks `{file_open, inode_permission, mmap_file, inode_setattr, inode_link, inode_rename}`
  - 例: `SOCK_CONNECT` → hooks `{socket_connect}`; `PROC_FORK` → hooks `{task_create}`
- **Retained-hook bitmap**: 取所有声明能力的 hook 集合的并集 → 编译为全局 bitmap
- **Kernel-version aware**: compiler 维护 per-kernel hook inventory，版本不匹配 → 拒绝编译（而非静默使用 stale mapping）
- **Selective enforcement pipeline**: 每个 hook 做 O(1) bitmap membership test → 不在 bitmap 中 → 立即返回（不进 MAC engine）
- **非声明资源**: 无 matching rule → fallback to DAC（零 USEC overhead）

**关键属性**: enforcement cost 随声明的保护范围缩放。只保护文件属性 → 不需要为无关的网络或设备路径付费。

**3. Compatibility-Oriented Security Interface (§4.4)**
- **Runtime dispatcher + hook mapping table**: 在 LSM hook 和 vendor code 之间插入兼容层
  - Matching entry exists → 运行 vendor hook chain
  - No matching entry → 返回 immediately → LSM 继续默认行为
- **Strict validation**: 注册时检查函数签名、返回类型、原始 LSM 原型 → 不匹配则拒绝注册
- **与 SELinux 共存**: 
  - 完全独立的 policy/AVC 状态（`usec_state` vs `selinux_state`）
  - reuse SELinux 的 on-disk labeling 约定
  - mount hooks 使用 per-task private list 而非 `fs_context.security` 字段（避免冲突）
- **Permissive mode**: 允许操作员先验证策略而不触发 SELinux 风格的断裂

## 实现

### 代码规模 (82,412 LOC total)
| 层 | 组件 | LOC |
|------|------|-----|
| Kernel | USEC LSM | 19,223 (18,765 new + 458 #ifdef) |
| User space | usecd, libusec, usecpolicy, etc. | 63,189 |

### 运行时路径
```
System Call → LSM Hook → retained? → UAVC cache → policy engine
                           ↓ no
                        return (bypass)
```

### 自动化 vs 手动
- 自动化: 策略加载、hook dispatch、cache lookup、enforcement
- 手动: capability-to-hook binding 维护（per kernel version, lightweight）

## 证据与评估

### 配置简化
- **(§6.1.1) Camera 控制**: SELinux >300 行 → 1 个 USEC JSON object (~10 行)
- **(§6.1.2) DBus AT-SPI 控制**: SELinux 需要 type 属性 + allow rules → USEC 的 declarative JSON 用 resource-centric 语义直接表达

### 运行时性能

| 场景 | USEC vs SELinux | 说明 |
|------|----------------|------|
| Server workloads (综合) | **3.4-17.1% lower overhead** | 代表性服务器负载下 |
| Desktop workloads | **3.4-17.1% lower overhead** | 代表性桌面负载下 |
| Hot-path hooks | 仅 retained hooks 触发 MAC | bypass irrelevant hooks 的 0 开销 |
| Camera+DBus 策略代码 | **10× fewer lines** | 策略复杂度度量 |

### 生产部署
- **800 万+ 企业端点** (2025 年初数据)
- **210+ 安全厂商**采用（QiAnXin, 360, NSFOCUS）
- 部署于金融、能源、交通等关键基础设施客户
- 基于 UAPP ecosystem (安全厂商协作推广平台)
- Deployed on UOS V25 (UnionTech 的 Linux 发行版)

## 整体评估

### 真正的新意
1. **"保护目标驱动的选择性 mediation"**: 将 MAC 从 "mediate everything" 反转为 "mediate only what's declared" — 不是 weakening security，而是让 protection scope explicit 且 bounded
2. **Resource-centric policy model**: 从 process-centric 到 resource-centric 的策略语义转换 — 与安全厂商"保护高价值资源免受所有人"的心态对齐
3. **Capability dictionary + compiler-driven hook resolution**: 将 capability→hook 映射 formalized + kernel-version aware → 替代手工选择 hooks 的 ad-hoc 做法

### 优点
- **生产部署规模罕见**: 800 万端点是企业级 MAC 系统中最广泛的部署之一
- **与 SELinux 共存**: 不需要替换现有 MAC → 逐步 adoption 可行
- **策略复杂度度量全面**: camera device、DBus ATSPI 两个具体 case study 展示了 10× reduction
- **理论+工程结合**: capability set 的 formal definition + hook bitmap 的形式化处理
- **开源 + 厂商采纳**: 210+ 安全厂商通过 UAPP ecosystem 协作

### 局限
1. **威胁模型的范围**: USEC 不保护"未声明"的资源 — 安全效果取决于厂商对 capability set 的完整性声明
2. **Capability dictionary 的手动维护**: 每个新 kernel version 需要更新 capability→hook 映射
3. **仅有保留的保护**: 如果 capability set 遗漏了关键的 access path（如某些间接别名路径），保护不完整
4. **评估缺乏标准 benchmark**: 性能对比以"3.4-17.1% lower overhead"表述但没有给出绝对延迟数字和具体 workload 细节（论文是 9 页 short paper 格式）
5. **仅 Linux**: 当前实现仅针对 Linux LSM 框架

### 可复用启发

1. **"保护什么就 mediation 什么"的工程设计原则**: "mediate everything" 是理论纯洁性，"mediate what matters" 是工程可用性。USEC 证明了 explicit bounded protection 在实际部署中比 "try to cover everything" 更有效
2. **Resource-centric 的语义 vs Process-centric 的语义**: 安全厂商不想"跟踪每个进程的访问权限"，他们只想"保护这些资源不被非法进程碰"。这两个视角的差异是 SELinux 复杂度的根源
3. **Kernel-version-aware compilation gate**: USEC 的 "版本不匹配 → 拒绝编译" 比"静默使用过期映射"更安全。在系统工具的编译链中嵌入版本检查是一个 low-cost 但 high-impact 的正确性保证
4. **Hook bitmap 作为"声明式最小化 TCB 面"**: retained-hook bitmap 让 enforcement surface 从 "所有 kernel hooks" 缩小到 "仅能力相关的 hooks" — 形式上，这是 capability set 的封闭性保证
5. **Industrial ecosystem 驱动 adoption**: UAPP ecosystem（210+ 厂商）是 USEC 从学术原型到 800 万端点部署的关键 — 论文本身用的是"厂商采纳"而非"开源社区采纳"的推广模型
