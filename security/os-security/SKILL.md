# OS Security & Program Analysis

操作系统安全与程序分析的工程经验，覆盖 MAC 强制执行、内存沙箱、动态追踪、策略提取和移动端分析。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 强制访问控制 (MAC) | resource-centric policy, demand-driven enforcement, capability bitmap, SELinux | USEC(OSDI'26) |
| 内存沙箱 (SFI) | disaggregation, split-allocation, validator-as-TCB-removal, JIT sandbox | Mohabi(OSDI'26) |
| 对象级内存追踪 | MPK, dormant-by-default, collateral fault, per-access context | Ichnaea(OSDI'26) |
| DB 访问控制策略提取 | concolic execution, LLM branch pruning, policy extraction | Ote(OSDI'26) |
| 移动端指令级 DBI | micro-op emulation, application-only emulation, SVC detection | iLand(OSDI'26) |

---

## MAC 强制访问控制

### 核心问题
SELinux 在生产环境中大规模禁用 — 配置复杂（320 策略模块 vs 11）、性能开销（每次 syscall 多次 hook 检查）、兼容性差（安装/升级路径被静默 deny）。

### 关键洞察

1. **Resource-centric 优于 Process-centric**：安全厂商的思维模式是"保护这些高价值资源"，不是"追踪每个进程能访问什么"。将策略语义对齐到资源视角 → 策略规模减少 10×。
2. **Demand-driven enforcement**：只对声明的 capability 相关路径启用 LSM hooks，无关路径 bypass → enforcement cost ∝ protection scope（而非系统全局）
3. **Capability-to-hook bitmap**：声明能力 → 编译器查询字典 → 展开为 hook 集合 → 运行时 O(1) membership test → 非 retained hook 立即返回
4. **与 SELinux 共存**: 独立 policy/AVC 状态 + same labeling scheme → 逐步 adoption 可行
- 来源：USEC(OSDI'26)

### 实践启发
- 安全策略应从资源出发，而非从进程出发
- "全量 mediation"在理论上完整，在工程上不可行 → "explicit bounded protection"更实用
- 保留与现有系统的兼容路径（coexistence）是 adoption 的关键

---

## 内存沙箱 (SFI)

### 核心问题
JS engine 是浏览器最大的攻击面。JIT 编译器 bugs 产生未安全 checked 的生成代码（range analysis bug → 跳过 bounds check）。现有浏览器方案要么禁用 JIT（损失 3.5-7× 性能）要么使用 unsound 部分沙箱（已被多次绕过）。

### 关键洞察

1. **SFI validator 将 JIT 移出 TCB**：不信任 JIT 编译器的正确性 → 独立二进制验证器检查 JIT 输出是否包含 SFI mask/guard 指令 → 即使 JIT 有 bug, validator 也会拒绝执行
2. **Disaggregation 工具链**：split-allocation types (一个 C++ 对象的字段分到 sandboxed/unsandboxed allocator) + 代码生成 hook（修改自动生成器产生 marshalling）→ 将跨数万函数的拆分工程自动化
3. **大内存 footprint SFI**：针对 JS engine 的 GB 级堆设计优化 mask/lookup → MH-LFI 是当前最快的 x86-64 SFI toolchain (SPEC 2017: 5.9-6.6%)
- 来源：Mohabi(OSDI'26)

### 实践启发
- "Validator removes TCB" 模式：不信任复杂组件，而是信任简单验证器
- Disaggregation 工具链可复用于任何"拆分大型 C++ monolithic 代码库"场景
- SFI 在 2026 年仍比 addr-space-based sandbox (Ubercage/JITCage) 更 sound

---

## 对象级内存追踪 (MPK)

### 核心问题
追踪"谁、什么时候、修改了什么对象"对调试/取证/并发分析至关重要。Intel Pin 精确但慢 10-100×（每条指令插桩）；`mprotect` 每次调用需 syscall + TLB shootdown → 微秒级延迟。

### 关键洞察

1. **MPK `pkey_set()` 是"最便宜的 page fault 触发器"**：一个用户态寄存器写指令（~1 cycle）即可改变当前线程对页面的访问权限 → 比 `mprotect()` 快 100-1000×
2. **Dormant-by-default 模式**：零开销常态 → 仅在 access ObjOfInterest 时触发 → 比 Pin 的 always-on 模式快 10-60×
3. **Collateral fault 容忍**：同页非 target 变量触发保护 → handler 快速识别跳过 → 放弃"完美隔离"换取更低的 setup 复杂度
4. **Per-access data diff**：捕获 call stack + thread ID + 修改前后的值 → 比"这页被访问过"价值高得多
- 来源：Ichnaea(OSDI'26)

### 实践启发
- MPK 适用于任何需要"临时 guard 内存区域"的场景
- "Dormant monitoring" 是最佳低开销监控模式
- 不追求完美隔离，接受 collateral noise → 大幅降低系统复杂度

---

## 访问控制策略提取

### 核心问题
Web 应用的 DB 访问控制策略从未显式声明 — 散布在 `if current_user.can?` + `WHERE user_id = ?` 中 → 只有原始开发者知道 policy → 随时间遗忘 → 访问控制 bug 积累。

### 关键洞察

1. **"Extract, don't write"**：不要求开发者显式声明 policy → 用程序分析自动提取 → 人工审查 → 可选强制执行
2. **Partial concolic execution**：只追踪 query 相关的简单操作（非全程序符号化）→ 大幅减少路径爆炸
3. **LLM relevance judge**: 用 LLM 的语义理解剔除与数据访问无关的 branch → "天数 → 小时数"
4. **Ote + BlockAid 闭环**: extract → review → enforce at DB layer
- 来源：Ote(OSDI'26)

### 实践启发
- "自动提取 > 人工编写" 适用于任何需要显式安全策略但开发者不愿意写的场景
- LLM + symbolic execution 的组合模式 (LLM 剪枝, SE 验证) 可推广
- 针对特定操作而非全程序 → 符号执行在 legacy code 上变得 tractable

---

## 移动端指令级 DBI

### 核心问题
iOS 没有非越狱的 DBI。沙箱禁止 JIT (无 RWX pages)，移动设备内存受限（iPhone 15: 6GB RAM 中系统 DSC 占 3.3GB）。

### 关键洞察

1. **预编译 Micro-ops 替代 JIT**：ARM64 指令 → 预编译的原子执行单元 → 所有 code 已经是 binary 的一部分 → 无需动态生成代码 → 兼容 iOS 沙箱
2. **Application-only emulation**: App 代码解释执行 + 系统库原生运行 → 避免"全量解释的内存爆炸"和"全量原生的无 instrumentation"
3. **Stateless control-flow manager**: 管理原生库 return 到 App 时切回解释模式
4. **SVC 绕过 App Review**：25% 头部 App 直接用 syscall 指令收集敏感信息 → 只有指令级 DBI 能检测
- 来源：iLand(OSDI'26)

### 实践启发
- "预编译替代 JIT" 模式适用于任何"禁止动态代码"的受限平台
- Application-only emulation 是解决"全量 vs 部分"困境的有效策略
- 指令级 DBI 在安全审计中的价值：发现 API 层监控无法捕获的 syscall 级绕过

---

## 五篇安全论文中的共通设计模式

| 模式 | 来自 | 含义 |
|------|------|------|
| **"校验器移出 TCB"** | Mohabi | 不信任复杂生成器，信任简单确认器 |
| **"提取替代编写"** | Ote | 不要求开发者显式声明，自动 infer |
| **"保护声明的而非全部"** | USEC | 明确受保护的边界，其余 pass-through |
| **"dormant-by-default"** | Ichnaea | 不做任何事直到感兴趣的事件发生 |
| **"用预编译绕开运行时限制"** | iLand | 将运行时不确定性提前到编译时解决 |

## 待补充

- 内核漏洞利用与缓解 (KASLR, SMAP, SMEP, CFI)
- 可信执行环境 (TEE, SGX, TrustZone)
- Fuzzing 与漏洞发现
- 形式化验证在 OS 安全中的应用
