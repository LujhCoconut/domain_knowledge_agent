# Timelock Drive(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-rosenblum.pdf
- **类型**: 论文-系统/安全
- **一句话 TL;DR**: 将 timelock 强制执行下推到物理磁盘块级别——小型隔离 checker (~400 LoC, 形式验证) 保证块在固定期间不可变，即使 OS/VS/管理员全部被攻破也无法覆盖。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| Transient immutability | 每个块写入后进入固定不可变期，期间任何软件（含管理员）都无法修改 | TD 的核心安全保证 |
| TD checker | 运行在隔离微控制器上的 ~400 行代码，执行 timelock 策略 | 唯一的 TCB——已通过 Dafny 形式验证 |
| TD-log | 纯追加日志存储 TD 元数据（块地址→时间锁映射） | 解决 "元数据本身也不能覆盖" 的自指问题 |
| Delegate-but-verify | 不可信 host 维护 TD 元数据的内存缓存 + BLAKE3 hash，TD checker 仅验证 | 消除扫描日志的性能问题 |
| Freshness counter | TD checker 存储的 ~2MB/TB 的小型计数器集 | 防止 host 重放旧元数据欺骗 checker |
| Time-of-lock guarantee | Recovery 时能可靠确定每个块的锁定时 | 使冒用条目可在恢复时被识别和丢弃 |

## 背景与动机

95% 勒索软件攻击尝试破坏备份，其中三分之二得手。现有 retention policy 方案（FlashGuard/S4）在 VS 侧实现时间锁定，但 VS 本身被攻破（bug/credential compromise）后策略就失效。根本问题是 TCB 太大（整个 VS 都在 TCB 中）。

## 核心方案

### 物理块级别的 Timelock

TD 暴露简单的 read/write/timelock 接口——VS 在不可信 host 上运行，TD checker 是唯一的 TCB：

```
Host (untrusted VS)  →  TD checker (~400 LoC, formally verified)  →  Physical blocks
                             ↑ 唯一能拒绝 overwrite 的组件
```

### 三个关键技术挑战

1. **元数据覆盖问题**：TD 本身也不能覆盖任何 timelocked 块→元数据用纯追加 TD-log 存储→每个新条目创建新的 log 块而非覆盖。自指：log 块本身也被 timelocked。

2. **Log 扫描性能问题**：追加式 log 意味着检索元数据需要扫描→不可接受的开销。解决方案：**delegate-but-verify**——host 维护完整的 in-DRAM metadata cache + 密码学 hash，TD checker 仅验证 hash 匹配+freshness counter 防止重放→不需要自己检索。

3. **TCB 最小化**：TD checker 仅 ~400 LoC→可形式验证（Dafny）。Freshness counter 仅 ~2MB/TB。

## 可复用启发
- **"Delegate-but-verify"是缩小 TCB 的通用策略**：不可信端做繁重工作，可信端仅做轻量验证。类似 Mohabi 的 validator-removes-TCB
- **"追加式 log + 不可信缓存"解决自指元数据问题**：覆盖被禁止→追加；追加导致扫描开销→host 缓存加速。两层解决
- 来源：Timelock Drive(OSDI'26)
