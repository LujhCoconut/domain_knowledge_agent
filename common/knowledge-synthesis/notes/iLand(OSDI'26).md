# iLand(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-xie-kaitao.pdf
- **全称**: iLand: An Instruction-Level Dynamic Binary Instrumentation framework for iOS
- **作者**: Kaitao Xie, Yizhuo Wang, Xiaolong Bai (Alibaba Group)
- **类型**: 论文-系统 (mobile security + DBI)
- **一句话 TL;DR**: 首个支持**非越狱 iOS 设备**的指令级动态二进制插桩框架 — 用预编译的 micro-operations + application-only emulation（APP 代码解释执行，系统库原生运行）替代 JIT，绕过 iOS 沙箱的 RWX 限制。用于分析 60 个 App Store 头部应用：**21%** 仍调用私有 API，**25%** 通过 SVC 指令直接收集敏感信息绕过 App Review。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **DBI** (Dynamic Binary Instrumentation) | 运行时修改/监控程序指令的技术 | iLand 的类别 |
| **Micro-operations** | 将 ARM64 指令翻译为预定义的原子执行单元 | 替代 JIT 的 code cache（无 RWX 需要） |
| **Atomic execution units** | 预编译的可重定位代码块，实现了每条 ARM64 指令的语义 | 组成解释器的基础构件 |
| **Application-only emulation** | 仅解释 App 自身代码，系统库原生执行 | 核心 memory/CPU 优化 |
| **DSC** (Dyld Shared Cache) | iOS 中所有系统库的预链接缓存（~3.3GB），映射并共享于所有进程 | 如果全量解释会内存爆炸 → 必须 native 执行 |
| **SVC** (Supervisor Call) | ARM64 的 syscall 指令 | 本文发现 25% 的 apps 直接用 SVC 收集敏感信息（绕过 API 层监控） |
| **Stateless control-flow manager** | iLand 中处理 App 代码 ↔ 系统库之间控制流切换的组件 | application-only emulation 的关键挑战 |
| **Jetsam** | iOS 的 OOM killer | iLand 需确保自己的内存不触发 Jetsam |

## 背景与动机

### 问题
- **iOS 没有 DBI**: Valgrind/Dyninst/Pin 等在其他平台上成熟，但在 iOS 上不可用
- **两个基本约束**:
  1. iOS 沙箱**禁止动态代码生成**（无 RWX pages）→ JIT-based DBI 不可行
  2. 移动设备 CPU/内存受限（iPhone 15: 6GB RAM，系统库 DSC 占用 3.3GB）
- **现有方案局限**:
  - Jailbreak + code injection: 仅支持到 iOS 16，不兼容新版本
  - App repackaging + API-level instrumentation: 非指令级，且 app 可能检测到修改

### iLand 的答案
用**预编译 micro-operations** 解释执行每条指令（而非 JIT 编译 code cache）→ 不需要 RWX memory→ compatible with iOS sandbox。

### 我的分析
这是 OSDI '26 的第五篇安全方向论文，也是第一篇 mobile 安全论文。有趣的是它来自 Alibaba 而非学术界——工业界的安全分析需求驱动了这个工具的开发。从抽象层面，iLand 的做法类似于"用软件 interpretation 替代 JIT compilation"，牺牲了 ~10-20× 的原始性能，但换来了在 iOS 沙箱内的可行性。

## 方案介绍

### 核心设计

**1. Micro-Operation-based 解释**
- 每条 ARM64 指令 → 预编译的 micro-op 序列
- 不需要生成新代码 → 所有执行单元已经是 binary 的一部分（预编译进 iLand）
- 绕过 "no dynamic code generation" 限制

**2. Application-Only Emulation**
- **解释**: App 自己的代码（micro-op interpretation）
- **原生**: 系统库（DSC + system frameworks）—— 因为：
  - DSC 占 ~3.3GB，全部解释会导致内存爆炸
  - 系统库已共享映射 → 原生执行利用现有映射，避免重复
  - CPU-intensive 任务（video codec, crypto）不适合解释执行

**3. Stateless Control-Flow Manager**
- Application-only emulation 引入的核心挑战：原生库代码 return 到 App 时需切回解释模式
- 管理 App 代码 ↔ 系统库之间的控制流切换，无需维护复杂的状态机

### 在 iOS 沙箱内的部署
- iLand 本身是一个**标准沙箱 iOS app**
- 被检测的 apps 不需要 jailbreak、不需要 repackaging
- 60/64 个 App Store 头部应用在 iLand 中达到"可用状态"（可正常渲染 UI、交互、视频直播）

## 实证发现

对 60 个头部 App Store 应用的分析：

| 发现 | 比例 | 说明 |
|------|------|------|
| 调用私有 API | **21% (13/60)** | 其中 2 个使用了 Apple 明确禁止的 API |
| SVC 指令直接收集敏感信息 | **25% (15/60)** | 绕过 API 层监控，直接通过 syscall 获取设备指纹等 |

**SVC 发现特别重要**: 这些 app 不通过公开或私有 API（能被静态分析/API hook 检测到），直接用 ARM64 `SVC` 指令发出 syscall 来收集信息——这是**新的绕过 Apple App Review 的手法**，只有指令级 DBI 能检测到。

## 整体评估

### 真正的新意
1. **首个非越狱 iOS DBI**: 用预编译微操作替代 JIT → 绕过 iOS 沙箱的 RWX 限制
2. **Application-only emulation**: 解决了 "全部解释 → 内存爆炸" 和 "全部 native → 无 instrumentation" 的困境
3. **SVC 绕过 App Review 的实证发现**: 有实际操作安全意义

### 优点
- **工业级可用**: 60 个真实 App Store 应用测试
- **不依赖 jailbreak**: 适用于最新 iOS 版本
- **实际安全发现**: 私有 API 使用 + SVC 规避手法
- **完整 UI 交互支持**: 保留动态渲染、实时视频等功能

### 局限
- **仅 ARM64 / iOS**: 平台特定
- **~10-20× 慢于原生**: micro-op interpretation 的固有代价（但做 tracing 而非 production use 可接受）
- **应用兼容性**: 60/64 apps 可用 = 93%，仍有 4 个无法正常运行
- **需要签名/企业证书**: 部署仍需 Apple Developer 账号

### 与之前安全论文的关系

| | Mohabi | Ichnaea | Ote | iLand |
|---|---|---|---|---|
| 平台 | Firefox/Desktop | Linux | Web/Rails | **iOS/Mobile** |
| 方法 | SFI sandbox | MPK tracing | Concolic extraction | **Micro-op DBI** |
| 目标 | 防 JS engine exploit | Object tracing | Policy visibility | **App behavior analysis** |
