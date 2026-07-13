# OBASE(OSDI'26)

- **来源**: OSDI '26, https://www.usenix.org/system/files/osdi26-banakar.pdf
- **全称**: OBASE: Object-Based Address-Space Engineering to Improve Memory Tiering
- **作者**: Vinay Banakar (UW-Madison & Google), Suli Yang (Google), Kan Wu (xAI), Andrea C. Arpaci-Dusseau, Remzi H. Arpaci-Dusseau (UW-Madison), Kimberly Keeton (Google)
- **开源**: https://github.com/WiscADSL/obase
- **类型**: 论文-系统 (compiler + runtime + memory management)
- **一句话 TL;DR**: 内存热量碎片化是 hyperscaler 内存 tiering 效率不高的根本原因——**活跃页中 70-90% byte 是冷的**（因为 allocator 按大小而非热度分配对象）。OBASE 通过编译器辅助的对象迁移，将热对象聚类到 HOT 堆、冷对象聚类到 COLD 堆，让任何现有 page-based tiering backend (kswapd/TMO/TPP/Memtis) 的回收效率提升 **2-4×**，内存节省 **70%**，overhead 仅 **2-5%**。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|---------------|
| **Hotness fragmentation** | 热对象和冷对象在同一页内交错混合 → 一个热对象标记整页为 active → 页内冷数据被"困"在快 tier | 核心问题 |
| **Page utilization** | `∑bytes_accessed / ∑page_size` — page 中被实际访问的 byte 比例 | 量化 fragmentation 的指标 |
| **Address-space engineering** | 动态重排虚拟地址空间，让冷/热对象聚类到各自页面 | OBASE 的核心思想 |
| **Guide** | 替代 C++ raw pointer 的 indirection object，携带地址 + 元数据 | 实现对象移动的基础机制 |
| **SAMA** (Spatially-Aware Memory Allocator) | 按 heap 类型（NEW/HOT/COLD）预留连续虚拟地址空间的分区分配器 | 让 OS 能对整片冷区域发出粗粒度回收 hint |
| **SODA** (Sparse Object Data Activity) | 两级位图扫描所管理对象的活动状态 | 无需遍历应用特定数据结构即可发现对象 |
| **ATC** (Active Thread Count) | 每对象计数：有多少公共操作正在使用该对象 | 判断对象是否可安全迁移（ATC=0 时才可移）|
| **TAG** (Thread-local Active scope Guard) | 公共 API 入口创建的线程局部 scope，记录本次操作 touch 了哪些 guides | 编译器自动注入，开发者无感 |
| **CIW** (Consecutive Inactive Windows) | 对象连续未被访问的扫描窗口数 | 冷热分类的 hysteresis 机制 |
| **ODM** (Optimistic Data Migration) | 类似 OCC 的 CAS-based 对象迁移协议 | 无锁并发迁移，失败则回退 |
| **PR** (Promotion Rate) | 来自 COLD heap 的 unique page 访问占比 | 控制冷阈值 Ct 的反馈信号 |

## 背景与动机

### 问题
- DRAM 占服务器成本 50%，memory tiering 理论上可以将 80-98% 冷数据移到慢 tier
- 但**实际收益远小于理论值**：Google 仅 offload 20%，Meta 仅 20-32%
- **根因**: Google 6 个工作负载的分析显示，活跃页中 **70-90% byte 从未被访问**（Figure 2）——即"热页不热"

### Hotness fragmentation (热量碎片化)

```
一个 4KB 页内有 3 个对象:
  [████ HotObj1 (128B)] [░░░░ ColdObj2 (2KB)] [████ HotObj3 (256B)] [░░░░░░ ColdObj4 (1.6KB)]

OS 视角: 这个页被访问了 → 是"热页" → 留在 DRAM
实际情况: 仅 384B 热 + 3.6KB 冷 → page utilization = 9.4%
         → 3.6KB 冷数据被"困"在昂贵的 DRAM 中
```

**根本原因**: allocator（jemalloc/tcmalloc）按对象大小和 allocation site 分配，不关心访问模式。热对象和冷对象随机交错在同一页。

**量化数据** (Figure 2, Google 6 个生产工作负载):
- **4KB pages**: Tahoe/Yankee 80% 的页面利用率 <20%；Bravo 60% 的页面 <40%
- **2MB pages**: Tahoe/Bravo/Yankee 85-90% 的 huge pages 利用率 <10%
- **仅有 1.7-21.3% bytes 被访问**，但 70-91.8% pages 被标记为 active

### 为什么静态方案不够

**Finding 1**: Active pages are mostly cold: 70-90% bytes 在 OS 认为"热"的页中从未被访问
**Finding 2**: Object hotness is transient: 对象的冷热属性随时间变化，无法在分配时预知
- Meta trace: 阶段性协同 inactivity (whitening bands) → 冷热持续迁移
- Twitter trace: 稀疏访问模式，大部分对象有长 idle gap（75% 对象 reuse spread >5×）
- 对于 64B-4KB 对象（占 94% Meta/98.2% Twitter keys），65% 的 reuse spread >30×

### 我的分析
这篇论文回答了一个被之前所有 CXL/tiering 论文忽略的根本问题：**back-end 再好，front-end 给的数据质量不够怎么办？** 之前 6 篇 CXL 论文都在优化"给定页面后如何决策迁移"，但没有人质疑"页面本身是否值得被迁移"——OBASE 论证了页面质量（page utilization）是限制 tiering 效率的第一性瓶颈。这和 Strata/ECHO/DirectKV 形成有趣的对比：它们都在解决"如何高效搬运"，OBASE 解决"搬运什么才值得"。

## 方案介绍

### Frontend-Backend 解耦

```
OBASE (Frontend)                    OS Kernel (Backend)
  │                                     │
  ├─ Guide dereference tracking         ├─ kswapd (page reclaim)
  ├─ SAMA: HOT/COLD heap allocation     ├─ TMO (PSI-based offloading)
  ├─ ODM: lock-free object migration    ├─ TPP (transparent page placement)
  └─ SODA: object discovery             └─ Memtis (dynamic page classification)
         │                                     │
         └─────── COLD pages ───────────────→ (自然被 backend 回收)
```

### 关键创新 1: Guide + SAMA 实现对象移动 (§3.2, §4.1)

**Guide 抽象**: 替代 C++ raw pointer 的 64-bit word
- 低 48 bits: canonical address（指向对象当前物理位置）
- 高 16 bits: 元数据（7 bits ATC + 5 bits CIW + 2 bits heap ID + 2 bits flags）

**开发者只需 annotate 哪些 pointer field 可被 rellocate**（如 hash table bucket pointer, B+ tree child pointer），编译器自动：
1. 将类型从 `T*` 改为 `Guide<T>`
2. 在公共 API 入口/出口注入 `createTAG()`/`destroyTAG()`
3. 在 guide dereference 前注入 `addToTAG(guide)`

**SAMA**: 基于 jemalloc extent 管理，每个 heap（NEW/HOT/COLD）预留连续 mmap 区域
- 大块连续空间 → OS 可用 `MADV_COLD`/`MADV_PAGEOUT` 对整个区域发 hint
- HOT 区域可请求 `MADV_HUGEPAGE` 改善 TLB coverage

### 关键创新 2: Lock-Free Optimistic Migration (§3.5, §4.5)

**三步协议** (Algorithm 2):
1. OC 检查 `ATC=0` + `migration-lock clear` → 原子设 lock bit (CAS)
2. OC 在新 heap 分配空间 → 拷贝对象 → 构造新 guide
3. OC 用单次 CAS 原子发布新 guide（同时释放 lock）

**竞态安全** (Table 1):
- 任何并发 dereference 会修改 guide → OC 的 commit CAS 失败 → 迁移 abort → 对象留在原位 → thread 看到的是有效数据
- **应用线程永不被阻塞**，OC 的 work per object 有上界

**Epoch-based ATC 激活** (Figure 6):
- 仅在 migration epoch 期间启用 ATC（大部分时间关闭，overhead 为 0）
- 三步状态转换: INACTIVE → PREPARE（等所有 thread 看到新 epoch）→ ACTIVE（可迁移）→ INACTIVE
- Thread 永不被阻塞——仅在进入公共 API 时记录 epoch 参与

**TAG (Thread-local Active scope Guard)**:
- 基于 BaseDeltaPtrSet — 利用 pointer locality（同一操作中访问的指针物理上聚集）压缩存储
- Median: 3 guides/op (hash table) 到 12 guides/op (B+Tree traversal)
- Per-operation TAG overhead <100ns

### 关键创新 3: 自适应冷阈值控制 (§3.4, §4.4)

**三堆状态机** (Figure 5):
- NEW: 新分配的对象（热度未知）
- HOT: 当前 working set
- COLD: 持续 inactivity 超过 Ct 的对象

**CIW (Consecutive Inactive Windows)**: hysteresis 计数器，每次扫描无访问 +1，有访问则归零

**AIAD (Additive-Increase/Additive-Decrease) 控制** (Algorithm 1):
- `PR_actual` = COLD pages accessed / working-set size × 60/scan_interval
- 若 `PR_actual > PR_target(1%)` → Ct += 1（更保守地降级）
- 若 `PR_actual < PR_target` → Ct -= 1（更激进地回收）
- Ct 范围: [1, 32] windows; 默认 Ct=3 (~6 min at 120s scan interval)

### 编译器辅助 (§4.7)
三个 LLVM pass:
1. **Type rewrite pass**: 识别 annotated pointer fields → 类型改写为 `Guide<T>`
2. **Instrumentation pass**: 注入 createTAG/destroyTAG/addToTAG hooks
3. **Validation pass**: 拒绝 pointer arithmetic over managed objects + physical contiguity assumptions

## 证据与评估

### 测试环境
- 10 种并行 pointer-based data structures (hash table, B+Tree, skip list, linked list, queue, stack, sorted array, balanced tree, vector, set)
- 6 种 tiering backends: kswapd, zswap, TMO, TPP, Memtis, HeMem
- 负载: YCSB (A-F workloads) + Meta KV trace + Twitter trace
- 对比: Baseline（无 OBASE，同一 backend）+ 各 backend 最佳配置

### 关键结果

| 指标 | 结果 | 说明 |
|------|------|------|
| Page utilization | **2-4×** 提升 | 跨 all workloads 和 backends |
| Memory savings | **up to 70%** | 同等性能下比 baseline 多省 70% DRAM |
| 同等吞吐下半数 DRAM | ✅ | OBASE + any backend ≈ Baseline ×2 DRAM |
| CPU overhead | **2-5%** | 远低于软件 sampling (PEBS >1% 时 >50% overhead) |
| 失效 case | 稀疏访问极限下退化到 baseline | concurrent pointer-chasing 不受益 |

### 与现有 Backend 的兼容性
不需要修改任何 backend — OBASE 仅重组地址空间：
- **kswapd**: 自然回收 COLD heap 中"无 access bit"的 pages
- **TMO** (PSI-based): COLD pages 无 PSI 压力 → 自然被 offload
- **TPP**: COLD pages 识别为 cold → 迁移到 slow tier
- **Memtis**: THP splitting 在 COLD heap 中不再需要（整个 hugepage 是冷的）
- **HeMem**: PEBS 采样发现 COLD heap 无 LLC miss → 自然降级

## 整体评估

### 真正的新意
1. **"Address-space engineering" 作为 tiering 的前置步骤**: 将所有现有 tiering 系统重新定义为 backends，OBASE 是第一个专注于 layout quality 的 frontend
2. **在 C++ 非托管语言中实现 safe concurrent object migration**: 通过 Guide + TAG + ODM + epoch 四层机制，首次在 C++ 中实现无暂停对象迁移
3. **Hotness fragmentation 的定量表征**: Google 6 生产 trace 的 page utilization CDF 系统性揭示了"热页不热"的严重性

### 优点
- **正交解耦**: 前端(layout)和后端(migration)独立创新——OBASE 不绑定任何后端，未来任何新后端自动受益
- **零 backend 修改**: 与现有 hypervisor/OS 基础设施无缝兼容
- **低 overhead**: 2-5% CPU，远低于软件 profiling 方案
- **优雅的并发模型**: epoch + OCC 风格迁移 → 线程永不阻塞
- **Google 生产 trace 验证**: 非合成 benchmark

### 局限
1. **仅支持指针型数据结构**: 不支持 raw pointer arithmetic、graph、doubly-linked list（需 unique ownership of guide）
2. **C++ 特有**: Guide + 编译器 pass 是 C++/LLVM 特定的；managed languages (Java/Go) 实现更简单但需不同机制
3. **Annotation 负担**: 开发者需手动 annotate relocatable pointer fields（虽然每个类型仅 1-3 个字段）
4. **扫描间隔**: 120s 默认间隔可能不适合极快速冷热切换的 workload（但 Ct 参数可调）
5. **COLD heap 内的内部碎片**: 虽然 SAMA 避免了热冷混合页，但 COLD heap 中仍有未被访问的"更冷"对象和无对象区域

### 可复用启发

1. **"分成 frontend + backend"是系统设计的通用模式**: 当某个系统组件（backend）的性能受输入数据质量限制时→添加一个专门的 frontend 来整理数据布局。可推广到 database buffer pool、CDN cache placement、ML feature store

2. **Page utilization 是一个简单而强大的诊断指标**: 任何页级内存管理系统的第一步应该是测量 page utilization——如果 <20%，backend 再怎么优化也是徒劳

3. **OCC-style 并发对象迁移模式**: "先拷贝→CAS 提交→失败回退"在无锁数据结构设计中常见，但应用到 OS/compiler 级别的对象迁移是新颖的

4. **Epoch-based overhead activation**: 将同步开销限制在短暂的 migration epoch 中（大部分时间 ATC 关闭），类似 RCU grace period 的思想应用到对象迁移

5. **Hotness fragmentation 是 hyperscale 的普遍问题**: 不限于 Google——任何使用通用 allocator (jemalloc/tcmalloc) 的系统都可能存在。简单的诊断方法：采样 page access bits + 计数页内 cache line 访问
