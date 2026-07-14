# Arca(OSDI'26)

- **来源**: https://www.usenix.org/conference/osdi26/presentation/srivatsan (PDF: osdi26-srivatsan.pdf)
- **类型**: 论文-OS设计
- **一句话 TL;DR**: 将 continuation capture 作为 OS 核心原语——2.55µs 快照/恢复（vs Linux process 283ms），使 "每个 I/O 操作后捕获 continuation" 变得可行，serverless 工作负载上 50-60× 加速。

## 关键数据

| 隔离原语 | 创建/销毁 | 快照/恢复 |
|----------|----------|----------|
| MicroVM (Firecracker) | 742ms | 217ms |
| Linux process | 540ms | 283ms |
| WebAssembly | 110µs | n/a (不支持) |
| **Arca** | **32.2µs** | **2.55µs** |

## 核心理念

Continuation = "程序从当前点开始的剩余部分"——捕获为可序列化、可移植的纯函数。

传统 serverless 需开发者**提前**拆分→函数。Arca 让 OS 自动捕获 continuation（作为 syscall）→可以在任何 I/O 操作后被暂停/迁移/复制。**不需要开发者提前决定 split point。**

## 关键洞察

1. **"Continuation capture 作为 OS 核心原语而非库函数"**：现有 snapshot（CRIU）需数百 ms——因为 OS 不是为 continuation 设计的。Arca 重新设计 OS→2.55µs 快照——五个数量级差距。
2. **"Effect system 替代 syscall"**：Arca 进程不直接做 I/O→返回 effect（I/O 描述+回调 continuation）→框架处理 I/O→resume continuation。这是 pure functional paradigm 在 OS 层的实现。
3. **"Zero-copy continuation"**：in-memory process 的 continuation 不需要复制→可直接在内存中传递。

## 可复用启发
- **"Continuation 是 serverless 的缺失原语"**：当前 serverless 需开发者手动拆分→continuation 让 OS 处理"在哪个点拆分"
- 来源：Arca(OSDI'26)
