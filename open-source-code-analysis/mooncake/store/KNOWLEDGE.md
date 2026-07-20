# Mooncake Store

Mooncake Store 的 Master 端核心机制：lease 生命周期、eviction 判定、refcnt 并发保护。

> 源码来源：`kvcache-ai/Mooncake` main 分支，核心文件：`mooncake-store/src/master_service.cpp`（9277 行）、`mooncake-store/include/replica.h`（688 行）

## 子主题

| 主题 | 关键词 | 技术点 | 关键源码行号 |
|------|--------|--------|-------------|
| Lease 三层保护 | lease, eviction, memory management, DRAM | GrantLease(hard_ms, soft_ms) dual timeline | `master_service.cpp:175-177`, `3306-3308` |
| Eviction 判定链 | soft pin, hard pin, BatchEvict | IsHardPinned/IsLeaseExpired/IsSoftPinned eviction guard chain | `master_service.cpp:6708-7110` |
| BatchEvict 两阶段淘汰 | parallel collection, nth_element | multi-thread candidate collection, nth_element lease_timeout sorting | `master_service.cpp:6895-7110` |
| Grouped Key 生命周期绑定 | group routing, lease refresh, eviction atomicity | same-shard routing by group_id, GrantLeaseForGroup all-member refresh, try_evict_group_or_object all-expired gate | `master_service.cpp:1592-1844`, `6585-6625` |
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

## Grouped Key：多个 key 的生命周期绑定

**背景**：vLLM 的 prefix caching 把一个 request 的 KV cache 沿 `block_size` 边界切成多个 block，每个 block 按 hash 存为 Mooncake 的一个独立 key。这些 key 形成一条前缀链——如果其中某几个 block 被 evict 了，剩下的即使还在 DRAM 里也无法命中（chain broken）。Grouped Key 就是把它们绑在一起——同生共死。

### 创建：PutStart 时分配 group_id

`master_service.cpp:3093-3098`（`PutStart`）：

```cpp
auto group_id_result = GetGroupIdForKey(config, 1, 0);
// 从 ReplicateConfig.group_ids 取出当前 key 的 group_id
const std::string group_id = group_id_result.value();
```

`ReplicateConfig`（`replica.h:90-98`）：

```cpp
// Optional per-key routing group IDs. Empty string keeps that key
// ungrouped. Grouped keys share metadata routing, coalesced lease refresh,
// and memory eviction behavior.
std::optional<std::vector<std::string>> group_ids{};
```

调用方传入 `group_ids` 向量，第 i 个 key 对应第 i 个元素。同一个 `group_id` 的多个 key 组成一个 group（如 vLLM 里用 `request_id + block_prefix` 作为 group_id）。

`ObjectMetadata` 上持久化 `group_id` 字段。`IsGrouped()` 检查 `group_id` 是否非空。

### 路由：同 group 的 key 落在同一 shard

`master_service.cpp:960-963`（`ExistKey` 中的 shard 路由）：

```cpp
auto route_it = object_group_ids_.find(MakeTenantScopedKey(tenant, key));
if (route_it == object_group_ids_.end()) {
    return getShardIndex(tenant, key);     // ungrouped：按 key hash
}
return getShardIndex(route_it->second);    // grouped：按 group_id hash
```

同 group 的所有 key 落在同一个 metadata shard——lease 刷新和 eviction 判定不需要跨 shard 协调。

### 注册：RegisterGroupMember

`master_service.cpp:1592-1601`（`RegisterGroupMember`）：

```cpp
object_group_ids_[MakeTenantScopedKey(tenant, key)] = group_id;
tenant_state.group_members[group_id].insert(key);
```

建立两组映射：
- `object_group_ids_`：`tenant+key → group_id`（路由用，全局，带 `group_routing_mutex_` 保护）
- `tenant_state.group_members`：`group_id → {key1, key2, ...}`（lease/eviction 用，per-tenant）

Master 重启后通过 `RebuildGroupRoutingIndex`（`master_service.cpp:1823-1844`）从每个 `ObjectMetadata.group_id` 重建这两组映射。

### Lease 联动：碰一个全刷

`GrantLeaseForGroup`（`master_service.cpp:1849-1888`）：

```cpp
if (!metadata.IsGrouped()) {
    metadata.GrantLease(default_kv_lease_ttl_, default_kv_soft_pin_ttl_);
    return;
}

// 遍历 group 内所有 member key，逐个续约
auto group_it = tenant_state.group_members.find(metadata.group_id);
for (const auto& member_key : group_it->second) {
    auto mit = tenant_state.metadata.find(member_key);
    if (mit != tenant_state.metadata.end()) {
        mit->second.GrantLease(default_kv_lease_ttl_, default_kv_soft_pin_ttl_);
    }
}
```

**任一 member 被 `ExistKey` / `BatchExistKey` / `GetReplicaList` 查询 → 整个 group 的所有 member 的 lease 被同步刷新到 `now+5000ms`。** 只要 vLLM 持续访问这个 request 的任何 block，所有 block 都不会被 evict。

### Eviction 原子性：全员过期才淘汰

`master_service.cpp:6585-6625`（`try_evict_group_or_object`）：

```cpp
if (!metadata.IsGrouped()) {
    return try_evict_or_offload(key, metadata, ...);   // ungrouped：直接 evict
}

// ── Group 级 gate ──
auto group_it = tenant_state.group_members.find(metadata.group_id);
for (const auto& member_key : group_it->second) {
    auto member_it = tenant_state.metadata.find(member_key);
    if (member_it != tenant_state.metadata.end() &&
        !member_it->second.IsLeaseExpired(now)) {
        return {};  // ★ 任一 member lease 未过期 → 整个 group 跳过，返回 0
    }
}

// ── Per-member 判定 ──
for (const auto& member_key : group_it->second) {
    auto& member_metadata = member_it->second;
    if (member_metadata.IsHardPinned() ||
        !member_metadata.IsLeaseExpired(now) ||
        (!allow_soft_pinned && member_metadata.IsSoftPinned(now)) ||
        !can_evict_replicas(member_metadata)) {
        continue;  // 每个 member 单独过四道防线
    }
    try_evict_or_offload(member_key, member_metadata, ...);
}
```

**两层判定**：
1. **Group 级 gate**：遍历 group 所有 member，**任一** lease 未过期 → 返回 0，整个 group 不 evict
2. **Per-member 单独过**：全过期后，每个 member 还要单独过 `hard_pin` / `IsLeaseExpired` / `IsSoftPinned` / `can_evict_replicas(refcnt)` 四道防线

**注意**：`BatchEvict` Phase 1 的候选收集是 per-key 的（不感知 group）。一个 grouped key 可能因自身 lease 过期被加入候选列表，但在 Phase 2 调用 `try_evict_group_or_object` 时被 group 级 gate 拦截。这是因为 GrantLeaseForGroup 保证同 group 所有 member lease 基本同时过期，实践中误加入候选的概率很低。

### 总结

```
                    ┌─ key_a (block hash 0xAAAA)
group_id = "req_001" ├─ key_b (block hash 0xBBBB)
                    └─ key_c (block hash 0xCCCC)

ExistKey(key_a) → GrantLeaseForGroup → key_a, key_b, key_c 的 lease 全部刷新到 now+5s

BatchEvict:
  Phase 1: key_b 自身 lease 过期 → 进入 candidates
  Phase 2: try_evict_group_or_object(key_b)
           → 检查 group 所有 member lease
           → key_a.IsLeaseExpired()? No (刚被 ExistKey 续过)
           → return {}  ← 整个 group 不淘汰
```

**不分组的话**：key_a 有 lease 保护但 key_b、key_c 可能已被 evict → 后续 get 只能命中前缀的一部分，其余 block 必须从 SSD 读或重算。

---

## Replica refcnt：并发操作保护

`Replica` 上的 `refcnt_`（`replica.h:329-332`）：

```cpp
std::atomic<uint64_t> refcnt_{0};

[[nodiscard]] bool is_busy() const { return refcnt_.load() > 0; }
```

### refcnt 阻止 eviction 的机制

`refcnt > 0` 的 replica **根本不会进入 evictable 候选集合**——`is_evictable_memory_replica` 最先就把它排除了：

```cpp
auto is_evictable_memory_replica = [](const Replica& replica) {
    return replica.is_memory_replica()
        && replica.is_completed()
        && replica.get_refcnt() == 0;     // ★ refcnt > 0 → 直接判 false
};

auto can_evict_replicas = [&](const ObjectMetadata& metadata) {
    return metadata.HasReplica(is_evictable_memory_replica);
};
```

`can_evict_replicas` 在 Phase 1 候选收集阶段就被调用——`refcnt > 0` 的 replica **连进候选列表的机会都没有**。对比四道防线的生效方式：

| 防线 | 第一遍 evict | 第二遍 evict | 可被时间改变？ | 可被配置覆盖？ |
|------|-------------|-------------|---------------|---------------|
| **hard pin** | 跳过（永久） | 跳过 | ❌ | ❌ |
| **hard lease** | `IsLeaseExpired?No` → 跳过 | 跳过 | ✅ 到期后失效 | ❌ |
| **soft pin** | `IsSoftPinned?Yes` → 跳过 | **可 evict**（`allow_evict_soft_pinned_objects_`） | ✅ 到期后失效 | ✅ 可被配置覆盖 |
| **refcnt > 0** | `can_evict_replicas?No` → **跳过，不进候选** | 同上（仍然不进候选） | ✅ 操作完成后释放 | ❌ |

**结论**：`refcnt` 的防护等级 = hard pin——**绝对的、无条件的、不进入候选队列**。区别只在于生命周期：hard pin 是永久的，refcnt 是操作级临时的。

### refcnt pin 的到底是什么

`inc_refcnt()` **不是 pin "请求"，而是 pin "正在被异步操作读取的那个源 replica"**。具体 pin 的是谁取决于数据流向：

| 操作 | 数据流向 | 被 pin 的 replica | 原因 |
|------|----------|------------------|------|
| **promotion**（`TryPushPromotionQueue`, L4037） | LOCAL_DISK(SSD) → MEMORY(DRAM) | **LOCAL_DISK 源** | promotion 期间需要从 SSD 读数据，如果 source 被并发 evict / remove 就无数据可读 |
| **offload**（`PushOffloadingQueue`, L3286） | MEMORY(DRAM) → LOCAL_DISK(SSD) | **MEMORY 源** | offload 排队期间需要从 DRAM 读数据写入 SSD，如果 MEMORY 被并发 evict 数据就丢了 |

**共同逻辑**：异步数据搬迁操作拿着 **source replica 的 refcnt**，等操作完成（`NotifyPromotionSuccess` / `NotifyPromotionFailure` / Reaper 超时 / Cleanup）才 `dec_refcnt()` 释放。在这期间 `is_evictable_memory_replica` 不通过 → eviction 线程不会碰这个 replica。

**目标端不在 refcnt 的保护范围**：promotion 中新分配的 PROCESSING MEMORY replica 靠的是 `!is_completed()` → `is_evictable_memory_replica` 直接拒绝（只有 COMPLETE 状态才可 evict），而不是 refcnt。

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

对于一个 MEMORY replica，阻止 eviction 的四道防线，按防护强度从高到低：

| 防线 | 防护方式 | 第一遍 evict | 第二遍 evict | 可被时间改变？ | 可被配置覆盖？ | 生命周期 |
|------|----------|-------------|-------------|---------------|---------------|----------|
| **hard pin** | `IsHardPinned()` → 跳过 | 跳过 | 跳过 | ❌ 永久 | ❌ | 对象创建时设置，永不过期 |
| **refcnt > 0** | `can_evict_replicas?No` → 跳过，不进候选 | 跳过 | 跳过 | ✅ 操作完成后释放 | ❌ | 操作级临时（promotion / offload 执行期间） |
| **hard lease** | `IsLeaseExpired?No` → 跳过 | 跳过 | 跳过 | ✅ 到期后失效 | ❌ | `default_kv_lease_ttl_`（默认 5000ms），续约可刷新 |
| **soft pin** | `IsSoftPinned?Yes` → 跳过 | 跳过 | **可 evict** | ✅ 到期后失效 | ✅ `allow_evict_soft_pinned_objects_` | `PutEnd` 时设置，`GrantLease` 调用时续约 |

**注意**：`BatchEvict` 判定顺序和上表不完全一致——Phase 1 中是 `IsHardPinned → IsLeaseExpired → IsSoftPinned → can_evict_replicas(refcnt)`。但 Phase 2 中 `try_evict_group_or_object` 的四道防线检查顺序是 `IsHardPinned → IsLeaseExpired → IsSoftPinned → can_evict_replicas`——refcnt 总是在最后被检查（因为 `can_evict_replicas` 包含了 refcnt 判定）。

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
