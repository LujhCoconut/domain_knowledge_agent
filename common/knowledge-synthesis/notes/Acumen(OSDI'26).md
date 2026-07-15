# Acumen(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-cottone.pdf
- **类型**: 论文-系统/安全
- **一句话 TL;DR**: 加密协作编辑平台——基于 CRDT + 密码学累加器 + secure GC，首次同时提供快照一致性+编辑历史隐私+加密+完整性。25 用户 60WPM 同时编辑延迟可忽略。

## 核心问题

协作编辑器（Google Docs/Notion）天然有隐私 vs 协作的张力：加密数据使服务端无法处理编辑。去中心化安全编辑器（CRDT-based）面临四个并发要求：机密性（加密+隐藏访问模式）、完整性（fork-causal consistency）、性能（实时、编辑大小不随历史增长）、安全动态成员（新加入不学习旧历史+被给 snapshot 一致性保证）。Snapdoc（SOTA）泄露访问模式、仅提供弱 snapshot consistency、性能随编辑历史增长。

## 关键洞察

1. **"密码学累加器实现可验证 snapshot 一致性"**：新用户被邀请时收到 document snapshot——需要验证这个 snapshot 未被篡改且与已有成员一致。密码学累加器使新用户可以验证而不需要访问完整编辑历史→同时满足 edit-history privacy 和 snapshot consistency。
2. **"Secure GC 机制使存储随当前文档大小线性扩展"**：覆盖式 GC 在加密环境下困难→Acumen 的 secure GC 使存储不随历史增长。
3. **"25 users × 60 WPM → no degradation"**：密码学 overhead 设计得足够低→实时编辑不受影响。

- 来源：Acumen(OSDI'26)
