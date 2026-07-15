# RT(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-li-zekai.pdf
- **类型**: 论文-编程语言/系统
- **一句话 TL;DR**: Shell 管道程序的静态类型检查——regular types 捕获命令的 input/output stream 结构，多项式复杂度 type checking，正则表达式错误消息。91% 精度，平均 0.02s 检查时间。

## 核心问题

Shell 是无类型环境——命令通过 byte stream 通信，类型错误只在运行时发现（程序崩溃、静默文件系统损坏）。现有 shell 没有类型系统→开发者在组合管道时可能传入不匹配的输出→错误在运行多天后才暴露（如 batch cron jobs）。

## 关键洞察

1. **"Regular types = 正则表达式作为类型——适合 shell 的流式本质"**：Shell 命令的 I/O 可以用正则表达式描述（"只有 [a-z]+ 行"、"每行三个 TAB 分隔字段"）→type checking = 语言包含（基本操作）= 多项式复杂度。错误消息本身是正则表达式→开发者熟悉。
2. **"Finite-state transducer 用于复杂变换"**：某些命令的 I/O 关系不能用简单正则→有限状态变换器捕获更复杂的转换→扩展表达能力。
3. **"Static type checking for shell——practical accuracy"**：数百个程序的评估→91% 精度，83% 假阴性减少（通过扩展如 concretization/annotations/heuristics）。类似 hS "推测性执行"——shell 程序可享受类似传统编程语言的 safety。

- 来源：RT(OSDI'26)
