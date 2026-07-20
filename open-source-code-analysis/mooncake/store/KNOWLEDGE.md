# Mooncake Store

Mooncake Store 的 Master 端核心机制：lease 生命周期、eviction 判定、refcnt 并发保护。

> 源码来源：`kvcache-ai/Mooncake` main 分支，核心文件：`mooncake-store/src/master_service.cpp`（9277 行）、`mooncake-store/include/replica.h`（688 行）

## 子主题

| 主题 | 关键词 | 技术点 | 关键源码行号 |
|------|--------|--------|-------------|
| Lease 三层保护 | lease, eviction, memory management, DRAM | GrantLease(hard_ms, soft_ms) dual timeline | `master_service.cpp:175-177`, `3306-3308` |
| Eviction 判定链 | soft pin, hard pin, BatchEvict | IsHardPinned/IsLeaseExpired/IsSoftPinned eviction guard chain | `master_service.cpp:6708-7110` |
| BatchEvict 两阶段淘汰 | parallel collection, nth_element | multi-thread candidate collection, nth_element lease_timeout sorting | `master_service.cpp:6895-7110` |
| Grouped Key Lease | tenant, group routing | grouped key lease refresh, NeedsLeaseRefresh | `master_service.cpp:1849-1888` |
| Replica refcnt | refcnt, promotion, offload | refcnt pin on source LOCAL_DISK | `replica.h:329-332`, `master_service.cpp:4037` |
| Promotion-on-Hit | promotion, SSD offload, Count-Min Sketch, heartbeat | TryPushPromotionQueue admission gating, PROCESSING MEMORY replica staging | `master_service.cpp:5538-5930` |

---

## ObjectMetadata Lease：三层保护机制

Mooncake Master 使用 lease 控制 MEMORY replica 的 eviction 时机。不是分布式锁，而是 `ObjectMetadata` 上的时间戳标记，在 `BatchEvict` 中被消费。

### 两条时间线

`GrantLease(hard_ms, soft_ms)` 在 `ObjectMetadata` 上设置两个截止时间。`BatchEvict` 按以下顺序判定每个 key 的 MEMORY replica 是否可驱逐：

`master_service.cpp:6708`（`BatchEvict`）、`master_service.cpp:6719`（`is_evictable_memory_replica`）、`master_service.cpp:6890-7000`（Phase 1 并行扫描，核心判定逻辑）：

```cpp
auto is_evictable_memory_replica = [](const Replica& replica) {
    return replica.is_memory_replica()    // 只 evict MEMORY replica
        && replica.is_completed()         // PROCESSING 状态的绝不碰
        && replica.get_refcnt() == 0;     // refcnt > 0 = 正在被 promotion/offload 使用
};

// Phase 1 中逐 key 判定：
if (it->second.IsHardPinned()) continue;           // ① hard pin → 永久跳过
if (!it->second.IsLeaseExpired(now)                // ② hard lease 未过期 → 跳过
    || !can_evict_replicas(it->second)) continue;
if (!it->second.IsSoftPinned(now)) {               // ③ soft pin 未激活 → 候选
    candidates.push_back({shard, tenant, key, lease_timeout});
} else if (allow_evict_soft_pinned_objects_) {
    soft_pin_objects.push_back(lease_timeout);      // soft pin 激活但允许强制 evict
}
```

| 阶段 | 时间范围 | hard lease | soft pin | BatchEvict 行为 |
|------|----------|------------|----------|----------------|
| 硬保护 | `now ~ now+hard_ms` | ✅ 有效 | ✅ 有效 | 第一遍直接 skip，绝不 evict |
| 软保护 | `now+hard_ms ~ now+soft_ms` | ❌ 过期 | ✅ 有效 | 第一遍跳过（除非 `allow_evict_soft_pinned_objects_`），第二遍可 evict |
| 无保护 | `now+soft_ms ~` | ❌ 过期 | ❌ 过期 | 第一遍直接进入候选，可 evict |

### mainline 中 GrantLease 的三个调用点

| 调用点 | 源码位置 | hard_ttl | soft_ttl | 触发时机 |
|--------|----------|----------|----------|----------|
| `PutEnd` | `master_service.cpp:3308` | **0**（立即过期） | `default_kv_soft_pin_ttl_` | 写入 key 完成 |
| `ExistKey` | `master_service.cpp:2088-2091` | `default_kv_lease_ttl_`（默认 5000ms） | `default_kv_soft_pin_ttl_` | `is_exist()` 查询 |
| `BatchExistKey` | `master_service.cpp:2157` | 同上 | 同上 | `batch_is_exist()` 查询 |
| `GetReplicaList` | `master_service.cpp:2555-2558` | 同上 | 同上 | `get()` 查询 replica list |

**`PutEnd` 设 `hard=0`**（`master_service.cpp:3306-3308`）：

```cpp
// 1. Set lease timeout to now, indicating that the object has no lease
// at beginning. 2. If this object has soft pin enabled, set it to be soft pinned.
metadata.GrantLease(0, default_kv_soft_pin_ttl_);
```

刚写入的 key 没有客户端正在读它，不需要硬保护——只有 soft pin 撑着。

**`ExistKey` / `BatchExistKey` 也 grant lease**（`master_service.cpp:2085-2091`、`master_service.cpp:2157`）：

```cpp
if (metadata.HasReplica(&Replica::fn_is_completed)) {
    // Grant a lease to the object as it may be further used by the client.
    auto* ts = accessor.GetTenantState();
    if (ts) {
        GrantLeaseForGroup(*ts, key, metadata);
    } else {
        metadata.GrantLease(default_kv_lease_ttl_, default_kv_soft_pin_ttl_);
    }
    return true;
}
```

意味着在 mainline 中，**每次 `is_exist` / `batch_is_exist` 查询也会续约 lease**——不只是 `get()`。

**`GetReplicaList` grant lease**（`master_service.cpp:2555-2558`）：

```cpp
// Grant a lease to the object so it will not be removed
// when the client is reading it.
metadata.GrantLease(default_kv_lease_ttl_, default_kv_soft_pin_ttl_);
```

客户端拿到 replica list 后要通过 RDMA 读数据。如果 lease 在 transfer 完成前过期 → 被 evict → `LEASE_EXPIRED` 错误。

### `NotifyPromotionSuccess` 在 mainline 不 grant lease

`master_service.cpp:5821-5930`——普通 promotion 完成后，**没有** `GrantLeaseForGroup` 调用。新 MEMORY replica 继承 `PutEnd` 时设置的 `GrantLease(0, soft_pin)` 状态——hard lease 已失效，只有 soft pin。PR #2646 的 `from_prefetch` + `GrantLeaseForGroup` 是上游尚未合入的改动。

### 参数来源

`master_service.cpp:175-177`——Master 构造时从 config 加载：

```cpp
default_kv_lease_ttl_(config.default_kv_lease_ttl),
default_kv_soft_pin_ttl_(config.default_kv_soft_pin_ttl),
allow_evict_soft_pinned_objects_(config.allow_evict_soft_pinned_objects),
```

对应 Master 启动参数：
```
--default_kv_lease_ttl              默认 5000ms  ← hard lease 时长
--default_kv_soft_pin_ttl           默认值见 master config
--allow_evict_soft_pinned_objects   ← 是否允许强制驱逐 soft_pinned key
```

`hard_pin` 通过 `ReplicateConfig::with_hard_pin` 在创建对象时设置，永不过期。`soft_pin` 通过 `ReplicateConfig::with_soft_pin` 控制——如果为 true，`PutEnd` 时 `soft_pin_timeout` 被 `emplace()`，后续 `GrantLease` 调用会续约它。

### Lease 续约与 Grouped Key

`GrantLeaseForGroup`（`master_service.cpp:1849-1888`）：

```cpp
void GrantLeaseForGroup(const TenantState& ts,
                        const std::string& key,
                        const ObjectMetadata& metadata) const {
    if (!metadata.IsGrouped()) {
        metadata.GrantLease(default_kv_lease_ttl_, default_kv_soft_pin_ttl_);
        return;
    }
    // NeedsLeaseRefresh 检查 lease 是否值得刷新 → 避免不必要的续约
    bool needs_refresh = metadata.NeedsLeaseRefresh(...);
    if (!needs_refresh) return;
    // 遍历 group 内所有 member key，逐个续约
    auto group_it = tenant_state.group_members.find(metadata.group_id);
    for (const auto& member_key : group_it->second) {
        mit->second.GrantLease(default_kv_lease_ttl_, default_kv_soft_pin_ttl_);
    }
}
```

Grouped key 的 lease 是联动刷新的——触碰 group 内任一 member → 整个 group 续约。

---

## Replica refcnt：并发操作保护

`Replica` 上的 `refcnt_`（`replica.h:329-332`）：

```cpp
std::atomic<uint64_t> refcnt_{0};

[[nodiscard]] bool is_busy() const { return refcnt_.load() > 0; }
```

`refcnt > 0` 阻止 eviction（`is_evictable_memory_replica` 要求 `get_refcnt() == 0`）。两层保护正交：

| 维度 | lease | refcnt |
|------|-------|--------|
| 作用对象 | `ObjectMetadata` 整体（所有 replica 共享） | 单个 `Replica` |
| 语义 | "这个 key 正被客户端使用，lease 期内不要 evict" | "这个特定 replica 正参与操作（promotion/offload），不要动它" |
| 生命周期 | 毫秒级（5s），续约可刷新 | 操作完成后立即释放 |

### refcnt 递增/递减

**递增**（`inc_refcnt()`）：

| 操作 | mainline 行号 | 目的 |
|------|-------------|------|
| `PushOffloadingQueue`（offload-on-evict） | `master_service.cpp:3286` | 防止 offload 排队期间 MEMORY replica 被驱逐 |
| `TryPushPromotionQueue`（promotion-on-hit） | `master_service.cpp:4037` | 防止 source LOCAL_DISK 在 promotion 期间被驱逐 |
| `BatchEvict` offload queue path | `master_service.cpp:4317` | 同上 |

**递减**（`dec_refcnt()`）：

| 操作 | mainline 行号 |
|------|-------------|
| `NotifyPromotionSuccess` | `master_service.cpp:5854` 附近 |
| `NotifyPromotionFailure` | `master_service.cpp:5954` 附近 |
| Offload 完成 / Reaper 超时 / Cleanup | `master_service.cpp:1760, 4087, 4106, 4178, 4367, 4386, 4463` |

---

## Eviction 线程

`master_service.cpp:406`（启动）、`master_service.cpp:5983`（主循环）：

```cpp
eviction_thread_ = std::thread(&MasterService::EvictionThreadFunc, this);

// EvictionThreadFunc:
while (eviction_running_) {
    double used_ratio = get_global_mem_used_ratio();
    if (used_ratio > eviction_high_watermark_ratio_) {
        double target = used_ratio - eviction_high_watermark_ratio_ + eviction_ratio_;
        BatchEvict(target, ...);            // ← 触发两遍淘汰
    } else if (now - last_discard > put_start_release_timeout_sec_) {
        DiscardExpiredProcessingReplicas();  // 清理超时的 PROCESSING replica
    }
    sleep(kEvictionThreadSleepMs);
}
```

### mainline `BatchEvict` 已并行化

`master_service.cpp:6708`——mainline 的 `BatchEvict` 分两阶段：

**Phase 1：多线程并行候选收集**（`master_service.cpp:6915-6950`）。最多 16 个线程并行扫描所有 shard，收集 `IsHardPinned()`→跳过、`IsLeaseExpired`→跳过、`IsSoftPinned`→跳过，通过的分入 `candidates` 或 `soft_pin_objects`。

**Phase 2：串行 key-lookup eviction**（`master_service.cpp:7000-7110`）。按 `nth_element` 排序 `lease_timeout`，淘汰 `evict_ratio_target` 比例的 key。淘汰后通过 `PublishKvRemovedAfterEvict` 通知客户端。

**Grouped key 特殊处理**（`master_service.cpp:6840-6870`）：`try_evict_group_or_object` 中检查 group 内所有 member key 的 lease 是否都过期——任一 member 的 hard lease 有效则整个 group 跳过。

---

## 完整保护矩阵

对于一个 MEMORY replica，阻止 eviction 的四道防线（按 `BatchEvict` 判定顺序）：

```
IsHardPinned()?          → 永久（hard_pin 在创建时设置，永不过期）
       │
      No
       ▼
IsLeaseExpired()==false? → hard lease 有效期内（ExistKey / GetReplicaList 授予）
       │
      Yes
       ▼
IsSoftPinned()?          → 软保护期内（soft_pin_timeout 在 PutEnd/GrantLease 时设置）
       │                 allow_evict_soft_pinned_objects_=true 时可强制突破
      No
       ▼
refcnt > 0?              → 并发操作 pin 住（promotion / offload 执行中）
       │
      No
       ▼
   可被 evict ✅
```

---

## 源码位置汇总

| 文件 | 行号 | 内容 |
|------|------|------|
| `mooncake-store/src/master_service.cpp` | 175-177 | `default_kv_lease_ttl_`、`default_kv_soft_pin_ttl_`、`allow_evict_soft_pinned_objects_` 初始化 |
| `mooncake-store/src/master_service.cpp` | 406, 5983 | EvictionThreadFunc 启动和主循环 |
| `mooncake-store/src/master_service.cpp` | 1849-1888 | `GrantLeaseForGroup`（grouped key lease 联动续约） |
| `mooncake-store/src/master_service.cpp` | 2074-2095 | `ExistKey`：含 lease grant |
| `mooncake-store/src/master_service.cpp` | 2098-2170 | `BatchExistKey`：含 lease grant |
| `mooncake-store/src/master_service.cpp` | 2515-2585 | `GetReplicaList`：含 lease grant + promotion eligibility 判定 |
| `mooncake-store/src/master_service.cpp` | 3306-3308 | `PutEnd`：`GrantLease(0, soft_pin_ttl)` |
| `mooncake-store/src/master_service.cpp` | 5538-5670 | `TryPushPromotionQueue`：promotion 准入控制 + refcnt inc |
| `mooncake-store/src/master_service.cpp` | 5821-5930 | `NotifyPromotionSuccess`（mainline 无 from_prefetch） |
| `mooncake-store/src/master_service.cpp` | 6708-7110 | `BatchEvict`：并行候选收集 + 串行 key-lookup eviction |
| `mooncake-store/src/master_service.cpp` | 6719 | `is_evictable_memory_replica` lambda |
| `mooncake-store/src/master_service.cpp` | 6895-6950 | Phase 1：IsHardPinned/IsLeaseExpired/IsSoftPinned 判定链 |
| `mooncake-store/include/replica.h` | 218-300 | `Replica` 构造函数（含 `refcnt_` 初始化） |
| `mooncake-store/include/replica.h` | 313-344 | `is_completed` / `is_processing` / `is_memory_replica` / `is_local_disk_replica` / `is_busy` |
