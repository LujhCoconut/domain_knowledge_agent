# jwmalloc(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-wang-jiawei.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 形式验证的移动端内存分配器——从零构建，bounded model checker 在弱内存模型下验证。替换 jemalloc，CPU 指令 -10%、系统指令 -10%。华为旗舰手机生产部署 >300 亿用户小时。

## 核心问题

移动端分配器（jemalloc）占 8.2%（Android）和 12.4%（HarmonyOS）的总 CPU 指令——远超服务器环境。移动 workload 有独特挑战：前后台阶段切换、bursty 用户交互、软实时约束、弱内存模型（ARM）、能量和性能双目标。现有分配器都未为移动场景从零设计，且缺乏形式化正确性保证。

## 关键洞察

1. **"从零为移动场景构建——不是调参现有分配器"**：thread-local caching + per-size-class binning 但针对移动的 bursty/background/foreground 切换做了专门优化。类似 Arca "OS 为 serverless 重新设计"——不是优化现有方案，而是面向 target domain 从零设计。
2. **"Bounded model checking under weak memory models"**：ARM 的弱内存模型使并发分配器的正确性验证极具挑战→形式验证确保无 data race、无 memory leak、无 double free。类似 Timelock Drive "formal verification on small TCB"——正确性保证超越了测试。
3. **"已经部署在旗舰手机上 >300 亿用户小时"**：生产验证+理论保证双重 credibility。

- 来源：jwmalloc(OSDI'26)
