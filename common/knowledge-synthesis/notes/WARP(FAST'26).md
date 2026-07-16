# WARP(FAST'26)

- **来源**: https://www.usenix.org/system/files/fast26-song.pdf, FAST '26
- **作者**: Inho Song, Shoaib Asif Qazi (Virginia Tech), Javier González (Samsung), Matias Bjørling (Western Digital), Sam H. Noh, Huaicheng Li (Virginia Tech)
- **一句话 TL;DR**: 首个 FDP SSD **开放仿真器 + 跨设备跨负载表征研究**——发现 FDP 在缓存类负载下可达成 near-1 WAF, 但在 RUH 干扰/对抗性失效下崩溃; 揭示 Noisy RUH 和 Save Sequential 两个未报告现象; 通过 II vs PI/OP/RU size 的 firmware 设计空间探索实现超越当前硬件的 WAF 降低。

## 重要术语

| 术语 | 全称 | 说明 |
|------|------|------|
| FDP | Flexible Data Placement | NVMe TP4146, host 通过 RUH tag 向 SSD 提供 placement hint |
| RUH | Reclaim Unit Handle | 逻辑标识符, 引导写入到特定 Reclaim Unit |
| RU | Reclaim Unit | GC 粒度, 通常=NAND superblock |
| II | Initially Isolated | GC 后将有效数据拷贝到共享 GC-RUH (不再隔离) |
| PI | Persistently Isolated | GC 后数据仍保持在源 RUH 内 (持续隔离) |
| OP | Over-provisioning | SSD 预留空间比例 |
| Noisy RUH | — | 一个 RUH 的失效操作放大其他 RUH 的写入 (本文发现的未报告现象) |
| Save Sequential | — | 设备过早回收长顺序写入流 (本文发现的未报告现象) |

## 核心问题

FDP 承诺通过 host hint (RUH) 将相似生命周期的数据同组回收 → WAF 接近 1.0。但商业 FDP SSD 的效果因设备而异——同一负载在一台设备上 near-1 WAF, 在另一台上失败。厂商内部实现 (RU size / OP / II vs PI / GC policy) 对 host 完全不可见。社区对"FDP 何时有效/何时失败/vendor 差异为何产生"缺乏原则性理解。

## 方案设计

### 1. 跨设备跨负载表征

在两台商业 FDP SSD 上测试 3 类负载: synthetic + trace-driven + filesystem → 发现:
- **缓存类负载** (CacheLib-like): 对象生命周期与 RUH 隔离对齐 → near-1 WAF
- **对抗性失效**: 混合 lifetime 的 co-located traffic → RUH 隔离打破 → WAF 退化
- **Noisy RUH**: 某个 RUH 的失效引发连锁 GC → 放大其他 RUH 的写入量
- **Save Sequential**: 设备在检测到长顺序写时过早触发回收 → 打断顺序写入优势

### 2. WARP 仿真器

基于 FEMU 构建, 开放 FDP 仿真器:
- 复现硬件 WAF 趋势 + 暴露 per-RUH 放大/GC victim 选择/资源争用等硬件不可见动态
- 将固件默认值转为可调 knobs: II vs PI / RU size / OP ratio / GC strategy

### 3. Firmware 设计空间探索

- **PI 仅在 OP 超过设备依赖阈值时优于 II**——低于阈值时 II 更鲁棒
- **RU size 影响隔离粒度与 parallelism 的 trade-off**
- **提出降低 WAF 的 firmware 策略** (超越当前硬件)

## 可复用启发

1. **"FDP is flexible but not foolproof"**: FDP 的 near-1 WAF 并非保证——依赖负载与 RUH 隔离对齐。设计 FDP-aware 系统时需了解其失效模式

2. **"Noisy RUH = 跨 RUH 干扰是 FDP 的关键失效模式"**: 一个 RUH 的 GC 可能连锁影响其他 RUH→类似 noisy neighbor problem。在 RUH 分配策略中需要考虑"哪些数据不应该共享同一 RU"

3. **"PI > II 仅在 OP 足够时成立"**: 低 OP 下 PI 的隔离带来碎片化成本>II 的混合 GC 效率。类似 TMO 的 PSI memory offloading——设计方案需考虑 slack 量

4. **"Emulator as firmware exploration platform"**: WARP 暴露硬件固件不可见的设计空间→使研究者能系统性评估 FDP 策略

## 归档

已归档到 `performance/storage-filesystem/` (SSD + FTL 优化)。
