# Neuro-Symbolic Proof Generation(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-he-baoding.pdf
- **类型**: 论文-验证/AI
- **一句话 TL;DR**: 神经-符号混合证明生成——best-first tree search over proof states + LLM fine-tuned on proof state-step pairs + ITP tools 修复被拒绝步骤 + 自动释放子目标。seL4 benchmark 上证明 77.6% 定理，大幅超越之前的 LLM-based 方法和独立 Sledgehammer。

## 核心问题

交互定理证明 (ITP) 是形式验证的黄金标准（CompCert、seL4），但 proof script 编写极度手工——seL4 需 20 人年、>100K 行 proof vs 仅 10K 行 C 实现。LLM 有数学推理潜力但直接生成完整正确 proof 失败于两个挑战：(1) 缺乏领域特定 lemma 和 proof tactic 的专门知识 (2) LLM 在大型搜索空间中的 hallucination/错误积累。

## 关键洞察

1. **"Neuro-Symbolic = LLM 提议 + 符号工具验证和修复"**：不是让 LLM 一次性生成完整 proof→LLM 提议下一步 proof step→符号工具 (Sledgehammer、ATP) 验证和修复→只接受被符号工具确认的步骤。类似 LogDrive/WriteGuards 的 "weak semantics + strong verification" 模式。
2. **"Best-first tree search over proof states"**：对 proof search 树做 best-first 搜索（而非 beam search 或 greedy），符号工具不断修剪搜索空间（语义信息）→LLM 只需在语义有效路径上提议。数据高效的 LLM 适应（proof state-step pairs fine-tuning）。
3. **"Isabelle REPL 暴露细粒度 proof states"**：使 LLM 可以观察 proof state（当前子目标、可用 lemma、环境上下文）而不仅仅是定理陈述→更像人类证明者的交互式工作流。

- 来源：Neuro-Symbolic Proof Generation(OSDI'26)
