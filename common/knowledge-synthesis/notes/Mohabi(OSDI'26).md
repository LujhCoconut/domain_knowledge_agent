# Mohabi(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-sharma.pdf
- **全称**: Mohabi: Disaggregating and Sandboxing the Firefox JavaScript Engine
- **系统名**: Mohabi (Monkey Habitat)
- **作者**: Abhishek Sharma, Anand Balaji (UT Austin), Zachary Yedidia (Stanford), Anthony Du, Taehyun Noh (UT Austin), Iain Ireland, Jan de Mooij, Matthew Gaudet (Mozilla), Tal Garfinkel (Google), Deian Stefan, Hovav Shacham (UCSD), Shravan Narayan (UT Austin)
- **类型**: 论文-系统 (browser security + SFI + compiler)
- **一句话 TL;DR**: 首个在现代浏览器中**完整 sandbox JS 引擎**的系统 — 用 SFI 将 Firefox 的 SpiderMonkey 与浏览器进程隔离，开发 C++ 类型系统和代码生成工具链使跨数万函数的拆分工程可控。JetStream overhead **24.82%**，Speedometer **24.43%**；MH-LFI 是当前最快的 x86-64 SFI toolchain (SPEC 2017: **5.9-6.6%**)。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **SFI** (Software-based Fault Isolation) | 在单进程内通过编译器插桩（masking、guard）实现内存隔离 | Mohabi 的核心 sandbox 机制 |
| **MH-LFI** (Mohabi's Load-Fault-Isolation) | 优化版 SFI toolchain，针对 JS engine 的大内存 footprint 定制 | SFI 实现，SPEC 5.9-6.6% overhead |
| **Disaggregation** | 将 SpiderMonkey 从 Firefox 进程中拆分出来 | 使 SFI sandbox 成为可能的前提步骤 |
| **Split-allocation types** | C++ 类型，将一个对象的字段拆分到不同 allocator（sandboxed vs unsandboxed） | 解决共享/隔离的字段级张力 |
| **SFI validator** | 验证 AOT/JIT 编译器输出的二进制代码中确实插入了 SFI checks | 将 JIT 编译器从 TCB 中移除 |
| **JITCage / Ubercage** | Apple V8 的部分 JS sandbox（已多次被绕过） | 对比 baseline |
| **NaCl** (Native Client) | Google 的早期 SFI 系统 | SFI toolchain 对比 |

## 背景与动机

### 问题
- JS engine 是现代浏览器**最大的攻击面** — 解释器+JIT+优化器，持续演进
- 内存安全 bug 经常不在编译器代码中，而在 **JIT 生成的代码**中（range analysis 错误 → 跳过 bounds check → OOB access）
- Apple Lockdown Mode / MS Enhanced Security / Android Advanced Protection 的答案都是 **禁用 JIT** — 但 JIT 提供 **3.5-7×** 加速
- 5/12 的 Chrome V8 2025 年漏洞即使在 JIT 禁用后仍然存在
- 现有浏览器 sandbox (V8 Ubercage, Safari JITCage) **不是 sound 的** — 已被多次绕过

### 挑战

**C1: Disaggregation 工程规模** — SpiderMonkey + Firefox 代码库巨大（数万函数），控制流和数据流深度交织

**C2: SFI 需适应 JS engine 的特殊需求** — 大内存 footprint、JIT 生成代码、高效的 mask/guard

**C3: JIT 编译器生成代码的正确性** — 必须将 JIT 从 TCB 中移除

### 我的分析
这是 OSDI '26 中第二篇安全方向的论文（与 USEC 同日）。与 USEC 的"800 万端点"生产验证不同，Mohabi 是学术界的 deep engineering work — 在真实浏览器代码库（Firefox）上实现首个 sound 的 JS engine SFI sandbox。其中"disaggregation 工具链"（split-allocation types + 代码生成 hook）本身就是一个重要贡献。

## 方案介绍

### 两大支柱

**支柱 1: Disaggregation (§3-4)** — 拆分 SpiderMonkey 出 Firefox

- **Split-allocation types** (§4.2): C++ 类型系统扩展，允许将一个 C++ 对象的字段分配到不同 heap
  - sandboxed allocator: JS engine 内部状态（不可被浏览器直接访问）
  - unsandboxed allocator: 需要跨边界共享的数据
- **代码生成 hook**: 利用 Firefox 已有的自动代码生成 [5,15,17,39] 和 wrapper types [63,100,104] 基础设施
  - 修改生成器 → 自动产生跨边界调用的 marshalling/serialization
  - 大幅降低手动拆分工作量

**支柱 2: MH-LFI — 优化的 SFI toolchain** (§5-6)

- **大内存 footprint 优化**: 针对 JS engine 的 GB 级堆设计 mask/lookup
- **AOT + JIT 编译集成**: 
  - AOT: LLVM pass → 对每个 load/store 插入 mask
  - JIT: SpiderMonkey JIT 编译器修改 → 生成的代码自带 SFI checks
- **SFI Validator** (§6.3): 验证 JIT 编译器输出的二进制确实插入了 SFI 指令
  - **将 JIT 编译器从 TCB 中移除** — 即使 JIT 有 bug 产生未 checked 代码，validator 会拒绝
  - 作者表示 validator 在开发中 catch 到多个遗漏的 SFI check 边缘情况

### 与 NaCl 的对比

| | NaCl | MH-LFI |
|---|---|---|
| SPEC 2017 overhead | ~10-15% | **5.9-6.6%** |
| 大 memory support | 有限 | 为 JS engine 定制（GB 级堆） |
| JIT 支持 | — | AOT + JIT 全路径 |

### 安全保证
- SFI 确保 compromised JS engine 无法随意 corrupt browser memory
- SFI validator 确保 JIT compiler bugs 不会产生未 sandboxed 代码
- 对比 Ubercage: 分析其先前的 bypass，证明 Mohabi 的 SFI 方案能防止这些攻击

## 证据与评估

### 关键结果

| 指标 | 结果 | 说明 |
|------|------|------|
| JetStream overhead | **24.82%** | 纯 JS benchmark |
| Speedometer overhead | **24.43%** | 全浏览器 benchmark（JS + 浏览器性能） |
| MH-LFI SPEC 2017 | **5.9-6.6%** | 当前最快的 x86-64 SFI toolchain |
| MH-LFI vs NaCl | MH-LFI 显著更快（大 memory 场景优势更大） | |
| SFI validator | 开发中发现并阻止了多个遗漏的 SFI check 边缘情况 | |
| Ubercage 对比 | Mohabi 防止了多个已知 Ubercage bypass | |

## 整体评估

### 真正的新意
1. **首个在现代浏览器中 sound sandbox JS engine**: 之前的工作要么是 standalone JS engine (学术)，要么是 unsound 的部分 sandbox (工业)
2. **Disaggregation 工具链**: split-allocation types + 代码生成 hook — 将"拆分大型 C++ 代码库"这一手工密集型任务自动化
3. **SFI validator 将 JIT 移出 TCB**: 这是 SFI 在 JS engine 场景下的关键安全创新 — JIT 编译器即使有 bug 也无法绕过 sandbox

### 优点
- **工业级代码库**: 在真实的 Firefox + SpiderMonkey 上实现，不是简化原型
- **完整的 SFI 对比**: MH-LFI vs NaCl，证明了 toolchain 的先进性
- **实际漏洞 mitigation 分析**: 用 Anthropic Mythos 发现的最近 bug 验证沙箱有效性
- **Mozilla 合作**: 作者包含 3 名 Mozilla SpiderMonkey 团队成员

### 局限
- **仅 x86-64**: SFI toolchain 目前只支持 x86-64（ARM64 是 future work）
- **~25% overhead**: 虽然比禁用 JIT 好得多（JIT 禁用 → 3.5-7× slowdown），但对延迟敏感的部署可能仍有顾虑
- **SpiderMonkey 特定**: 虽然方法（disaggregation + SFI）是通用的，但 split-allocation types 和代码生成 hook 的具体实现是 SpiderMonkey 特定的
- **工程复杂度**: 尽管有工具链辅助，仍需要对数万函数进行代码修改

### 可复用启发

1. **Disaggregation 工具链是"解耦大型系统"的通用模式**: split-allocation types + 代码生成 hook — 适用于任何需要将一个组件从 monolithic codebase 中拆出的场景
2. **Validator 移出 TCB**: 与其信任 JIT 的正确性（已被无数次证明不可信），不如用独立的 validator 验证 JIT 的输出
3. **SFI 在 2026 年仍然 relevant**: 尽管有 V8 Ubercage 和 Safari JITCage，但它们都不是 sound — SFI 有清晰的 formal guarantee
4. **与厂商合作的 deep engineering**: Mozilla 团队的参与使论文能从"学术原型"跨到"真实浏览器代码库" — 这种合作模式对系统安全研究有价值
