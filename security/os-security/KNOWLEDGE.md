# OS Security & Program Analysis

操作系统安全、隐私保护与程序分析的工程经验，覆盖 MAC 强制执行、内存沙箱、差分隐私训练、机密数据库、opaque 组件安全执行、动态追踪、策略提取和移动端分析。

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 强制访问控制 (MAC) | resource-centric policy, demand-driven enforcement, capability bitmap, SELinux | USEC(OSDI'26) |
| 内存沙箱 (SFI) | disaggregation, split-allocation, validator-as-TCB-removal, JIT sandbox | Mohabi(OSDI'26) |
| 差分隐私训练 | correlated noise, noise history management, NMP, hierarchical memory, embedding tables | Cocoon(OSDI'26) |
| Opaque 组件安全执行 | semisolate, effect capture, filesystem interposition, privileged-less, language-agnostic | try(OSDI'26) |
| 对象级内存追踪 | MPK, dormant-by-default, collateral fault, per-access context | Ichnaea(OSDI'26) |
| DB 访问控制策略提取 | concolic execution, LLM branch pruning, policy extraction | Ote(OSDI'26) |
| 移动端指令级 DBI | micro-op emulation, application-only emulation, SVC detection | iLand(OSDI'26) |
| 机密数据库 (TEE/CDB) | crypto-free mappings, TEE, FID, indirection-protection decoupling, confidential computing | ZENO(OSDI'26) |
| 安全计算 (SC) 内存管理 | obliviousness, speculative paging, garbled circuits, 128× expansion, transparent virtual memory | Osprey(OSDI'26) |
| TrustZone USB 驱动重用 | record-lift-replay, kernel specialization, USB FSM determinism, mutational recorder, in-TEE driver | µUSB(OSDI'26) |
| 物理块级 Timelock 防御 | transient immutability, isolated checker, delegate-but-verify, append-only metadata, formal verification, ransomware | Timelock Drive(OSDI'26) |
| VM 自省框架 (LVMI) | shared-VMM observer, lock-aware memory coherence, native-speed introspection, mutualization layer, VMI | GOODKIT(OSDI'26) |
| eBPF 多租户虚拟化 | late-binding, vBPF, static-binding, Sniffer event attribution, O(1) Dispatcher, state isolation | vBPF(OSDI'26) |
| 加密协作编辑 | CRDT, cryptographic accumulator, secure GC, snapshot consistency, edit-history privacy, fork-causal consistency, collaborative editing | Acumen(OSDI'26) |
| 神经-符号证明生成 | neuro-symbolic verification, best-first proof search, LLM+ITP, Isabelle REPL, seL4, sledgehammer, automated theorem proving | NeuroSym-Prover(OSDI'26) |
| 数值计算 Succinct Proof | succinct proof, numerical approximation, approximate constraints, arithmetization, execution integrity, finite field | Spain(OSDI'26) |

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

## 差分隐私训练 (Correlated Noise)

### 核心问题
DP 训练通过给梯度添加噪声提供隐私保证，但噪声累积导致准确率显著下降。相关噪声（跨迭代抵消）解决了准确率问题，已被 Google Gboard/Apple/Microsoft 部署。但其**系统开销从未被研究**——噪声历史内存可能超过参数内存本身，特别是在大型嵌入表场景中。

### 关键洞察

1. **噪声历史是新的"数据维度"**：存储整个迭代的噪声（GB 级）+ 每步 GEMV 计算 → 需要分层管理
2. **CPU-GPU-NMP 三级噪声存储**：GPU 存热噪声，CPU 存温历史，NMP 存冷历史 → 并发处理
3. **稀疏嵌入表的噪声优化**：每次迭代仅访问少量嵌入行 → 预取热行、惰性驱逐冷行、基于行的存储格式
4. **NMP 消除 GEMV 传输瓶颈**：在数据所在位置计算（FPGA NMP），无需将整个噪声历史传输到 GPU
- 来源：Cocoon(OSDI'26)

### 实践启发
- "为准确率而添加的特性"需要系统表征——相关噪声被广泛采用但从未被测量系统成本
- 隐私计算工作负载中"大数据+简单计算"模式与 NMP 天然匹配
- 噪声即数据，应享受与训练数据同等级的分层管理

---

## Opaque 组件安全执行 (Semisolates)

### 核心问题
现代软件栈中充斥着**不透明组件**（curl-pipe-sh installers、LLM 生成的脚本、闭源二进制）—用户盲目信任或需要全量容器化，两者之间缺乏中间地带。

### 关键洞察

1. **"半隔离"是"盲目信任"和"完全容器化"之间的最佳平衡点**：component 可以看到当前文件系统但写入先被拦截层捕获
2. **Effect 作为一等抽象**：程序的外部可观察行为定义为"effects"，支持 inspect → selectively apply → revert → hide
3. **无特权、语言无关、高阶**：`try <command>` 适用于任何可执行程序，无需 root 权限
- 来源：try/semisolates(OSDI'26)

### 实践启发
- "不要隔离，要截获"：让组件看到当前环境但不让它污染
- Effect + select → 类似 git 的 stage/unstage，但针对程序的文件系统副作用
- 适用于 CI/CD pipeline、plugin 系统、LLM 生成代码的沙箱执行

---

---

## 机密数据库 Crypto-free Mappings (ZENO)

### 核心问题
机密数据库 (CDB) 用 TEE 保护敏感数据，但 split 架构（仅安全关键操作在 TEE 内）导致每次跨 TEE 域调用需要 2 次解密+1 次加密（~6500 cycles），分析查询延迟最高达明文数据库的 79.5×。根本原因是**混淆了"间接寻址"和"保护"**——加密了指针（不该加密）和数据（应该加密）。

### 关键洞察

1. **Crypto-free mapping 解耦间接寻址与保护**：FID（数据独立标识符）在普通 DBMS 中无需加密→仅 TEE 内部映射到明文秘密
2. **"不要加密指针"是普遍原则**：指针/索引/标识符不携带机密信息——只需轻量级间接寻址
3. **External synchrony** 简化映射存储：仅需 FID→明文映射，不需要反向映射
- 来源：ZENO(OSDI'26)

### 实践启发
- "区分保护数据 vs 保护索引"适用于任何跨信任边界的间接寻址系统（secure ML、federated analytics）
- FID 作为数据独立标识符是 CDB 的新原语——类似虚拟内存中的页表项
- TEE 边界不应成为 I/O 瓶颈的源头——ZENO 通过架构 redesign 而非硬件加速来解决

---

## 安全计算 (SC) 透明虚拟内存 (Osprey)

### 核心问题
安全计算（SMPC/HE）将数据扩展 **128×**（garbled circuits: 每 bit → 16B），中等数据集立即 OOM。一旦 OS 开始 paging 变得 infeasibly slow。之前的 SC-aware 内存管理需要 up-front planning 并框架重写应用。

### 关键洞察

1. **"将约束转化为优势"**：SC 的 obliviousness（执行路径独立于数据内容）消除了 speculative execution 的 rollback 复杂性 → speculation 变得免费且安全
2. **"借用上层语义简化底层系统"的逆向模式**：通常 OS 为上层提供优化——这里是 SC 的 obliviousness 为 OS virtual memory 提供了安全保障
3. **透明 + 极简集成**：<200 LOC 每 SC 库，零应用修改，无内核修改
- 来源：Osprey(OSDI'26)

### 实践启发
- Obliviousness 不仅是隐私属性——也是系统优化的使能器（类似 OCaml 的 type safety 使能 tail-call optimization）
- 当安全属性隔离了执行路径与数据内容时，speculation 免费且安全
- "约束转化为优势"是最强的系统设计 insight——不仅仅是"克服限制"

## 十篇安全/隐私论文中的共通设计模式

| 模式 | 来自 | 含义 |
|------|------|------|
| **"校验器移出 TCB"** | Mohabi | 不信任复杂生成器，信任简单确认器 |
| **"提取替代编写"** | Ote | 不要求开发者显式声明，自动 infer |
| **"保护声明的而非全部"** | USEC | 明确受保护的边界，其余 pass-through |
| **"dormant-by-default"** | Ichnaea | 不做任何事直到感兴趣的事件发生 |
| **"用预编译绕开运行时限制"** | iLand | 将运行时不确定性提前到编译时解决 |
| **"半隔离而非全隔离"** | try | 不让组件看到当前环境，但拦截它的修改 |
| **"不要加密指针，加密数据"** | ZENO | 将间接寻址层从加密中分离，仅保护数据机密性 |
| **"将约束转化为优势"** | Osprey | Obliviousness 使 speculative execution 免费且安全 |
| **"录制→提升→回放"** | µUSB | 从执行 trace 推导 TEE 可用驱动，替代手动重写 |

## 待补充

- 内核漏洞利用与缓解 (KASLR, SMAP, SMEP, CFI)
- 可信执行环境 (TEE, SGX, TrustZone)
- Fuzzing 与漏洞发现
- 形式化验证在 OS 安全中的应用

---

## TrustZone USB 驱动重用 (µUSB)

### 核心问题
TrustZone 的 Secure I/O 完全缺乏 USB 外设支持——USB 是最多样化的外设类别（传感器、键鼠、摄像头、麦克风）。现有集成方案不可行：手动重写驱动太复杂（协议+多供应商实现差异）、全量移植 Linux USB 栈到 TEE 不现实。

### 关键洞察

1. **Kernel specialization**：Linux USB 驱动在具体硬件+工作负载下的执行路径高度可预测——实际需要的代码远少于完整驱动
2. **USB FSM determinism**：USB 协议状态机是确定性的——录制一次覆盖路径即可回放
3. **Record→Lift→Replay**范式：将"如何将复杂驱动移入 TEE"从 engineering problem 转化为 program analysis problem
- 来源：µUSB(OSDI'26)

### 实践启发
- "Record→Lift→Replay"适用于任何"将复杂传统代码移入受限环境"的场景——不仅是 USB→TrustZone
- Kernel specialization 可以大幅降低复杂性：通用代码中的大部分分支在实际场景中从不执行
- 协议 FSM 的确定性是自动推导的关键使能器

---

## 物理块级 Timelock 防御 (Timelock Drive)

### 核心问题
数据完整性面临勒索软件、篡改和破坏威胁——95% 勒索软件攻击尝试破坏备份，三分之二得手。现有 retention policy 方案（FlashGuard/S4）在版本系统 (VS) 侧实现时间锁定，但 VS 本身被攻破（bug 或 credential 泄露）后策略即失效。根本问题是 TCB 太大——整个 VS 都在可信基内。

### 关键洞察

1. **"将 timelock 强制执行下推到物理块级别"**：TD checker（隔离微控制器上仅 ~400 行代码）是唯一能拒绝 overwrite 的组件。即使 OS/VS/管理员全被攻破，物理块在 timelock 期间仍不可变——TCB 从整个 VS 缩小到 400 行代码。
2. **"纯追加 TD-log + delegate-but-verify 解决元数据的自指问题"**：TD 本身也不能覆盖任何 timelocked 块→元数据用追加 log 存储。但扫描 log 检索元数据不可接受→不可信 host 维护 in-DRAM metadata cache + 密码学 hash，TD checker 仅验证 integrity + freshness counter（~2MB/TB）防止重放。
3. **"Time-of-lock guarantee 使恢复可以可靠识别冒用条目"**：即使攻击者通过 VS 注入伪造的元数据，恢复时可以通过 time-of-lock 信息丢弃攻击时间后写入的所有条目。
4. **"Formal verification 在小 TCB 上可行"**：~400 LoC 允许 Dafny 形式验证 timelock 机制的正确性——更大的 TCB 无法做到这一点。

- 来源：Timelock Drive(OSDI'26)

### 实践启发
- **"Delegate-but-verify"是缩小 TCB 的通用策略**：不可信端做繁重工作（维护缓存），可信端仅做轻量验证（hash check + freshness counter）。类似 Mohabi 的 validator-removes-TCB——不信任复杂生成器，信任简单验证器
- **"追加式 log + 不可信缓存"解决自指元数据问题**：覆盖被禁止→追加；追加导致扫描开销→host 缓存加速。两层解决——每一步都简洁有效
- **"物理隔离 + 小块 TCB"是防御 credenial compromise 的有效范式**：即使管理员密码泄露，攻击者仍无法绕过硬件级的 timelock 强制执行

---

## VM 自省框架 (GOODKIT)

### 核心问题
VM 自省 (VMI) 是云安全的基础——检测 rootkit、勒索软件、性能异常。现有三种部署位置各有致命缺陷：(1) hypervisor 内（扩大 TCB）(2) 单独 VM（LibVMI——需要 pause VM + 多次 kernel-userspace crossing→目标 slowdown 5-37×）(3) guest 内（guest 被攻破后无效）。**没有任何方案同时满足快速、强隔离、不修改 hypervisor。**

### 关键洞察

1. **"Observer VM 与 target VM 共享同一 VMM 进程"**：VMM（如 QEMU）已经是用户态进程，持有 target VM 的完整内存映射。将 observer 也作为轻量 VM 跑在同一 VMM 下→直接 mmap target 内存→native-speed 访问。无需修改 KVM、无需暂停 target、无需 kernel-userspace crossing。
2. **"Lock-aware 内存一致性而非 pause-the-world"**：LibVMI 通过暂停整个 VM 保证内存一致性→应用停止。GOODKIT 理解内核锁状态→在锁持有的安全窗口内捕获一致性快照→target 持续运行。
3. **"Mutualization layer"**：多 observer（租户的安全监控 + 云提供商的合规扫描 + 性能分析工具）共享公共 introspection 工作→减少对内核数据结构的竞争→多 observer 不线性增加开销。

- 来源：GOODKIT(OSDI'26)

### 实践启发
- **"共享 VMM = 零拷贝 VM 自省"**：VMM 已经持有目标 VM 的完整内存映射——直接 mmap 给 observer VM 就是最快路径。类似 CoPilotIO 的 split SQ/CQ——找到两个域之间的高效共享点，而非绕道或暂停
- **"Lock-aware consistency > pause-the-world"**：理解同步原语的状态→在自然安全点捕获→消除人为暂停的 overhead。适用于任何需要一致性快照但不能暂停的系统
- **"Good design eliminates overhead rather than tolerating it"**：GOODKIT 不优化 LibVMI 的暂停机制——它让暂停变得不必要。从 target slowdown 37.6× 到 1.06× 不是优化，是范式改变

---

## eBPF 多租户虚拟化 (vBPF)

### 核心问题
eBPF 已成为云原生系统的内核可编程性标准——但设计时隐含单一信任域假设。多租户部署自己的 eBPF 程序时出现严重冲突：struct_ops 只允许一个全局 TCP 实现（平台 vs 租户二选一）、kprobe 中被另一租户修改返回值导致静默数据损坏、多程序 attachment 争抢共享执行上下文→性能干扰。根本原因是 **eBPF 的 static-binding 模型**——逻辑程序在部署时固定绑定到物理 hook，导致多租户强制争抢同一执行上下文。

### 关键洞察

1. **"Late-binding 替代 static-binding"**：不是将程序在部署时固定绑定到物理 hook→物理 hook 作为通用拦截点→事件在运行时按租户属性动态解析目标程序。类似 VTC "virtual tensor"——物理资源不应与逻辑实体 1:1 绑定。vBPF 创建 per-tenant eBPF namespace，类似 Linux namespace 将全局内核资源虚拟化为 per-process 视图。
2. **"Sniffer 精确归因中断驱动事件到租户"**：中断上下文下的事件无法简单确定属于哪个租户→Sniffer 从硬件状态（如 CR3/page table 切换）推断当前运行的是哪个租户的进程→使 late-binding 在中断上下文中可行。
3. **"Dispatcher O(1) 查找替代线性遍历"**：多个租户可能向同一 hook 注册→线性遍历所有 attached 程序成为瓶颈→Hash table O(1) dispatch。类似 Ambulance "proposal lane" 和 Sepia "page coloring"——消除资源争抢中的线性瓶颈。

- 来源：vBPF(OSDI'26)

### 实践启发
- **"Static-binding→late-binding 是多租户系统中的通用升级"**：不仅是 eBPF——任何共享资源的 binding 模式都应设计为运行时解析（类似 Arca "effect system"、libDSE "speculation sandbox"）
- **"Namespace virtualization = per-tenant 内核视图"**：类似容器使每个容器看到自己的文件系统——vBPF 使每个租户看到自己的内核 hook 和程序集
- **"Interrupt-context event attribution 是新的系统挑战"**：在中断上下文中无法简单确定"当前是谁的进程"——Sniffer 的硬件状态推断是值得学习的 Technique

---

## 加密协作编辑 (Acumen)

### 核心问题
协作编辑器（Google Docs/Notion）天然有隐私 vs 协作的张力——加密使服务端无法处理编辑。去中心化安全编辑器面临四个并发要求：(1) **机密性**（不仅加密内容，还要隐藏访问模式——谁在哪个位置做了插入/删除）(2) **完整性**（fork-causal consistency——即使恶意用户/网络对手攻击也不能分叉）(3) **安全动态成员**（新加入用户既有 edit-history privacy 又有 snapshot consistency——无法获取旧历史但能验证当前文档未被篡改）(4) **性能**（编辑操作实时，存储不随历史增长）。现有 SOTA Snapdoc 泄露访问模式，弱 snapshot consistency，存储规模随历史线性增长。

### 关键洞察

1. **"密码学累加器使可验证 snapshot 与编辑历史隐私共存"**：新用户被邀请时获取 document snapshot，需要通过密码学累加器验证这个 snapshot 的一致性——但不需要访问完整编辑历史。这解决了 "如何验证文档未被篡改" 与 "不泄露过去谁写了什么" 之间的矛盾。类似 Bodega "roster leases"——用密码学原语使参与者可以验证本地状态而不需要全局可见。
2. **"Secure GC——加密数据下的垃圾回收"**：传统 GC 依赖读取数据内容决定是否可回收→在加密环境下不可行。Acumen 的 secure GC 打破这个限制→存储随当前文档大小线性扩展而非历史长度。
3. **"25 users × 60 WPM 同时编辑→零延迟退化"**：密码学 overhead（加密+累加器+GC）设计得足够低→实时编辑性能与明文编辑器相比无明显差异。

- 来源：Acumen(OSDI'26)

### 实践启发
- **"密码学累加器 = 可验证状态摘要而不暴露历史"**：适用于任何需要"证明当前状态一致性但不暴露如何达到此状态"的场景——类似 WriteGuards "key-range fencing" 和 LogDrive "weakTail"——弱语义使实现变得简单但强验证
- **"Encrypted GC 是 privacy-preserving systems 的新维度"**：大多数加密系统只关注加密数据和查询，忽略了随着时间增长的数据存储问题——GC 是 long-running 系统的必要条件
- **"Fork-causal consistency——去中心化环境下的完整性保证"**：即使恶意用户/网络对手无法创建可信历史的 fork→类似 Ambulance "non-equivocation phase"——防止攻击者创建冲突版本的共识

---

## 神经-符号证明生成 (NeuroSym-Prover)

### 核心问题
交互定理证明 (ITP) 是系统软件形式验证的黄金标准（CompCert/seL4），但 proof script 极其手工——seL4 需要 20 人年构建 >100K proof lines，而只有 10K C 代码和 3K 抽象规范。LLM 有数学推理潜力，但直接生成完整 proof 在两个挑战上失败：(1) **缺乏领域特定 lemma/tactic 知识**——不在训练数据中 (2) **大型搜索空间中的 hallucination 和错误累积**——LLM 单个错误步骤使 proof unrecoverable。

### 关键洞察

1. **"Neuro-Symbolic = LLM 提议下一步 + 符号工具验证修复——不接受未被符号确认的步骤"**：不是一次性生成完整 proof→LLM 提议下一个 proof step（tactic application）→符号工具链（Sledgehammer、ATP、simplifier）验证和修复→只接受被符号工具确认的步骤后才继续。类似 LogDrive "weak semantics + strong verification" 和 WriteGuards "key-range fencing check"——LLM 处理提议/探索，符号工具处理确认/修复。
2. **"Best-first tree search over proof states——符号语义修剪搜索空间"**：对证明空间做 best-first search（优先最有希望的 proof state）而非 beam search 或 greedy→符号工具有效修剪无效路径（语义信息）→LLM 只需在语义有效的路径上继续提议。对比：纯 LLM 在无意义路径上浪费探索，纯符号工具搜索空间爆炸。
3. **"Isabelle REPL 暴露 proof states 使 LLM 像人类证明者一样交互"**：LLM 不仅看到定理陈述，还看到当前子目标、可用 lemma、环境上下文→更接近人类证明者的交互式工作流。

- 来源：NeuroSym-Prover(OSDI'26)

### 实践启发
- **"LLM 提议 + 符号验证确认"是 AI+验证的通用模式**：类似 Mimesys "execution as verification" 和 Twill "constraint solver as correctness oracle"——LLM 做创造性的搜索/提议，符号工具做严格的确认/修复。两个世界的最优组合
- **"Best-first search > beam search for proof generation"**：beam search 可能过早排除正确的 proof path→best-first 与符号修剪结合更具鲁棒性
- **"Data-efficient through proof state-step pairs"**：不需要海量数据——few-shot proof state→step 映射即可有效 fine-tune。类似 LAH "single model pretrained on traces"——数据效率使部署可行

---

## 数值计算 Succinct Proof (Spain)

### 核心问题
Succinct proofs（执行完整性/零知识）要求将计算翻译为有限域上的约束（arithmetization）。但数值计算（浮点/定点近似实数）在有限域中没有自然表达——有限域没有负数概念、没有大小关系、条件分支基于数值比较极难表达。现有方案要么做特殊化编码（牺牲通用性），要么做 end-to-end 专用协议（牺牲通用性+性能）。LLM 训练/推理、物理模拟等数值密集型工作负载完全无法从 succinct proofs 中受益。

### 关键洞察

1. **"数值计算的近似误差是机遇而非障碍——约束应允许近似满足"**：既然数值计算本身就有近似误差，约束系统也应允许**近似满足**而非精确满足→大幅降低证明生成开销。这是将数值特性转化为协议优势：近似正确 = 真正正确（因为原始计算本身就不可达到精确）。
2. **"新证明协议专为近似约束设计"**：传统 SNARK/STARK 要求约束精确成立。Spain 的新协议处理 "approximately satisfied" 约束→证明器开销三个数量级以内（vs 原生执行）→远超现有方案的 10^5-10^6×。
3. **"通用 + 高效不是矛盾的"**：核心协议不依赖具体计算→改变数值程序不需要重做底层数学→同时达到通用性、verifier 比原生执行便宜、prover <1000× overhead 三个目标。

- 来源：Spain(OSDI'26)

### 实践启发
- **"Approximation as a feature, not a bug"**：数值计算的近似特性不是 succinct proof 的障碍——是可以利用的特性。约束系统的 "近似满足" 是全新的设计点。类似 Kareus "恒定频率 > 频率波动"——将约束转化为优势
