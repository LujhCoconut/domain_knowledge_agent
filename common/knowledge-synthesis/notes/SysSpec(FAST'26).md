# SysSpec(FAST'26)

- **来源**: https://www.usenix.org/system/files/fast26-liu-qingyuan.pdf, FAST '26
- **作者**: Qingyuan Liu, Mo Zou, Hengbin Zhang, Dong Du, Yubin Xia, Haibo Chen (SJTU IPADS)
- **一句话 TL;DR**: **生成式文件系统范式**——用形式化方法风格的多维规格(Functionality+Modularity+Concurrency)取代自然语言 Prompt 指导 LLM 生成+演进 FS，通过 SpecCompiler(两阶段:逻辑先→并发后)+SpecValidator(验证+反馈重试)+DAG spec patch 演进机制，成功生成通过数百回归测试的 SPECFS，集成 10 个 Ext4 真实特性。

## 核心问题

FS 开发陷入恶性循环：Ext4 自 Linux 2.6.19 以来 3157 commits 中 **82.4%** 是 bug fix/maintenance，仅 5.1% 是新功能。"fast commits" 功能 9 commits 实现→80 commits 修复→稳定化成本远超实现。

**LLM 生成 FS 的三大挑战**:
1. **语义鸿沟**: NL prompt 无法精确表达 FS 的并发正确性、磁盘布局、不变量
2. **复杂组合**: LLM context window 有限→必须模块化生成→接口兼容+跨模块变更传播困难
3. **不可靠**: LLM 幻觉→"生成即祈祷"不可接受

## 方案设计

### Multi-part Specification (形式化方法风格)

- **Functionality**: Hoare-logic pre/post-conditions + invariants
- **Modularity**: Rely-guarantee 接口规范(各模块对其他模块的依赖+保证)
- **Concurrency**: 显式 locking protocol + ordering

### LLM-based Toolchain (三个 Agent)

- **SpecCompiler**: 两阶段生成(先逻辑后并发)→逐步细化避免 LLM 被复杂并发淹没
- **SpecValidator**: 验证生成的 code ↔ spec →不匹配→反馈→重试→自主纠错
- **SpecAssistant**: 辅助开发者编写 specification

### Evolution: DAG-structured Spec Patch

不直接改 C 代码→改 specification→toolchain 自动重新生成实现。Spec patch 是 DAG 结构→保证新特性不破坏已有 invariants→类似形式化验证中的"preservation of invariants"。

## 关键数据

- 生成 **SPECFS** (FUSE-based concurrent FS)→通过数百回归测试
- 正确性等同于手工编码的 AtomFS (之前经形式化验证的 FS)
- 成功集成 10 个 Ext4 真实特性→演进能力验证

## 可复用启发

1. **"用规格而非自然语言桥接 LLM 与系统软件"**: 不是更好的 prompt engineering→是更好的 specification formalism。类比系统软件从"写代码"到"写 TLA+"的演进路径

2. **"先逻辑后并发 = 两阶段复杂度分离"**: LLM 同时处理功能逻辑+细粒度锁会被淹没→先生成正确但无并发的版本→再加入并发→逐步细化。类似人类开发者的 workflow

3. **"Spec patch = DAG = 保证 invariant preservation"**: 类比形式化验证中的 refinement proof→新特性的 spec patch 必须证明不破坏已有 invariant。使"演进"从 ad-hoc 变成可验证的步骤

4. **"验证-反馈-重试 = LLM 自我纠错闭环"**: validator 不是一次性 gate→是迭代反馈循环→LLM 从错误中学习纠正

## 归档建议

已归档到 `operations/os-testing/` (系统测试+形式化+LLM)。
