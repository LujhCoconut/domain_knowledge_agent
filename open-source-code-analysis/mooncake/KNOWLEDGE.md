# Mooncake 源码分析

Mooncake (Apache-2.0) 是 kvcache-ai 开源的分布式 KV cache store，为 LLM 推理提供高性能的 KV cache 传输和存储。核心组件包括 Transfer Engine（RDMA 加速的数据传输）和 Mooncake Store（三层存储 + SSD offload/prefetch）。

> 分析版本：PR #2646（`huangdong2022/main_prefetch_pr`），设计文档 `docs/source/design/ssd-prefetch.md`

---

## 三层存储模型

| 层级 | Replica Type | 介质 | 访问延迟 | 访问方式 |
|------|-------------|------|----------|----------|
| L0 | MEMORY | DRAM（RDMA 可达） | ~μs | Transfer Engine (RDMA/GPU Direct) |
| L1 | LOCAL_DISK | 本地 NVMe SSD | ~ms | Offload RPC（RDMA scatter-gather） |
| L2 | DISK | 远程磁盘/网络文件系统 | ~10ms+ | `storage_backend::vector_read` + H2D copy |

- MEMORY replica 存储一个 key 的 KV 数据的完整副本
- LOCAL_DISK replica 在 DRAM 不够时通过 `BatchOffload` 写入 SSD，保留在 object metadata 中
- 一个 key 可以同时有 MEMORY + LOCAL_DISK 副本（DRAM 未 evict 时），或只有 LOCAL_DISK（DRAM 已被 evict）

---

## Promotion-on-Hit（已有的 promotion 机制）

### 触发路径

```
get(key) → Client::Query(key) → MasterClient::GetReplicaList(key, tenant)
  └─ MasterService::GetReplicaList(key, tenant):
       1. shared_lock(snapshot_mutex_)
       2. MetadataAccessorRO → 读取 replicas
       3. inc_valid_get_nums / inc_cache_hit_nums (metrics 副作用)
       4. GrantLease / GrantLeaseForGroup (lease 保护)
       5. TryPushPromotionQueue(object_id):  ← 准入控制
            ├── Count-Min Sketch 频率门控 (promotion_admission_threshold_)
            ├── DRAM watermark 门控 (eviction_high_watermark_ratio_)
            ├── Dedup (promotion_tasks 已有?)
            ├── Cap 检查 (promotion_in_flight_ < promotion_queue_limit_)
            ├── inc_refcnt on LOCAL_DISK source replica
            ├── PushPromotionQueue → 推到 holder client 的 promotion_objects heartbeat 队列
            └── promotion_tasks.emplace → promotion_in_flight_++
```

### 执行路径

```
FileStorage heartbeat loop (固定周期, ~10s):
  └─ ProcessPromotionTasks():
       1. PromotionObjectHeartbeat → 从 master pull promotion_objects
       2. 对每个 task:
            PromotionAllocStart  → master 分配 PROCESSING MEMORY replica
            AllocateBatch        → 本地 staging buffer
            BatchLoad            → SSD read
            PromotionWrite       → Transfer Engine (RDMA) 写 DRAM
            NotifyPromotionSuccess → master: PROCESSING → COMPLETE
```

### 局限性（5 个问题）

1. **Count-Min Sketch 频率门控**：首次 get 时 freq < threshold 不触发 → "首次预热" 场景下 promotion 永远不会发生
2. **Query() 的副作用**：grant lease（误 pin 对象）、更新 sketch、污染 metrics
3. **Heartbeat 周期过长（~10s）**：promotion 任务在 heartbeat 队列中等待，无法 sub-second 完成
4. **双路径冲突**：如果同时通过 `Query` 入队和直接调用 `PrefetchKeys`，同一 key 触发两次 promotion → `REPLICA_IS_NOT_READY`
5. **全局配额共享**：与正常 promotion 共用 `promotion_queue_limit_`

---

## SSD Prefetch-on-Exist（PR #2646）

### 设计动机

vLLM 调度器中 `exists()` 到 `get()` 有 15-17s 窗口（详见 `vllm/KNOWLEDGE.md`）。利用这个窗口异步将 SSD-only key 预热到 DRAM。

### 完整机制（12 步）

```
Step 1: 触发
  is_exist(key, ExistOptions{prefetch_to_memory=true})
  / batch_is_exist(keys, ExistOptions{prefetch_to_memory=true})
    └─ RealClient::batchIsExist(keys, options)
         ├─ 1. batchIsExist_internal(keys) → Master RPC (原本的 exist 逻辑)
         ├─ 2. 收集 prefetch_candidates: exists=true 且 prefetch_to_memory=true
         └─ 3. triggerSsdPrefetch(candidates) → 异步入队，立即返回

Step 2: 第一层防护 — Cooldown 检查
  PrefetchThrottle::inCooldown()
    → cooldown_until_ms_ > NowMs() ? skip : 继续
    → 当之前 PrefetchKeys 因 NO_AVAILABLE_HANDLE 失败时激活

Step 3: 入队 — prefetch_pool_
  submitPrefetchJob(job)
    → ThreadPool(4).enqueue(job)
    → pool 满或 shutdown → DROP（绝不 fallback detach thread）

Step 4: 元数据查询 — BatchQueryForPrefetch（Chunked + Pipelined）
  对每 128 key chunk:
    Client::BatchQueryForPrefetch(chunk)
      → MasterClient::BatchGetReplicaListForPrefetch(chunk)
        → MasterService::GetReplicaListForPrefetch(key) per key  ← 只读，无副作用
           shared_lock(snapshot_mutex_) → 读 replicas → 返回
           不 grant lease、不 inc metrics、不 enqueue promotion

Step 5: SSD-Only 分类 — ClassifySsdPrefetchRoute
  for each replica in replicas:
    if MEMORY → 不是 SSD-only，跳过
    if LOCAL_DISK → 记录 size + holder_endpoint
  返回: SSD-only = 有 LOCAL_DISK 且无 MEMORY

Step 6: 第二层防护 — PrefetchThrottle::reserve（延迟 reserve）
  注意：reserve() 在此处调用，而非在 exist 同步路径
  → 只在 BatchQuery 确认 SSD-only 后才创建 trigger entry
  → 避免 DRAM-resident key 的 false trigger (B7 fix)

  对每个 key:
    if key 在 entries_ 中（dedup TTL 内已触发过）→ skip
    else → entries_[key] = {state=kTriggered, trigger_ms=now}
    同时清理 TTL 过期 entry

Step 7: Master 注册 — RegisterPrefetchTask
  Client::RegisterPrefetchTask(key) → RPC → MasterService::RegisterPrefetchTask(client_id, key)
    1. 如果已有 MEMORY 副本 → 返回 OK（race 保护）
    2. 如果已在 promotion_tasks → 去重
    3. 检查 promotion_in_flight_ < promotion_queue_limit_（共享配额）
    4. 找 LOCAL_DISK source → inc_refcnt
    5. ★ 验证 holder_id == client_id（只有 SSD 持有者能注册）
    6. promotion_tasks.emplace(key, PromotionTask{
         .source_id, .object_size, .holder_id,
         .from_prefetch = true  ← ★ 标志位
       })
    7. promotion_in_flight_++

  对比 TryPushPromotionQueue:
    | 维度                  | TryPushPromotionQueue | RegisterPrefetchTask   |
    |-----------------------|-----------------------|------------------------|
    | Count-Min Sketch 频率 | ✅ 需要               | ❌ 不需要              |
    | DRAM watermark 门控   | ✅ 需要               | ❌ 不需要              |
    | 推 heartbeat 队列     | ✅ PushPromotionQueue  | ❌ 不推                |
    | 创建 promotion_tasks  | ✅                    | ✅                     |
    | promotion_in_flight_++| ✅                    | ✅ (共享)              |
    | from_prefetch         | false                 | true                   |

Step 8: 数据搬迁 — FileStorage::PrefetchKeys
  对每个 key（串行）:
    8a. PromotionAllocStart(key, size)
        → master: 在 DRAM segment 中分配 PROCESSING MEMORY replica
        → 记录 alloc_id 到 promotion_tasks
        → 返回 MemoryDescriptor (RDMA addr, rkey 等)

    8b. AllocateBatch(storage_key, size)  ← 注意用 tenant-scoped key (B8 fix)
        + BatchLoad(slices)               ← SSD read → staging buffer

    8c. PromotionWrite(memory_descriptor, slices)  ← Transfer Engine (RDMA) write to DRAM

    8d. NotifyPromotionSuccess(key)
        → master: PROCESSING → COMPLETE
        → dec_refcnt on source LOCAL_DISK
        → promotion_in_flight_--
        → ★ if from_prefetch: GrantLeaseForGroup(key)
           → GrantLease(default_kv_lease_ttl_, default_kv_soft_pin_ttl_)
           → 与 exist/get 的 lease 对齐（~5s 保护，可配）

    如果任何步骤失败 → NotifyPromotionFailure → release master 状态
    如果 NO_AVAILABLE_HANDLE → *dram_pressure = true → 触发 cooldown

Step 9: Lease 保护（对 prefetch 特化）
  普通 promotion: NotifyPromotionSuccess → GrantLease(0, soft_pin_ttl)  ← hard lease 立即过期
  Prefetch promotion: NotifyPromotionSuccess → GrantLease(default_kv_lease_ttl_, ...)  ← 有 hard lease

  效果: prefetch 后的 DRAM 副本在 default_kv_lease_ttl（默认 5s）内不会被 capacity eviction 回收

Step 10: 跨节点 Delegation — prefetch_offload_object RPC
  当 LOCAL_DISK 在远程节点时：
    节点 A (requester)                节点 B (holder)
        │                                │
        ├─ prefetch_offload_object(      │
        │    endpoint_B, keys, sizes) ──▶│
        │                                ├─ runLocalPrefetch(keys, sizes)
        │                                │   └─ submitPrefetchJob → prefetch_pool_
        │                                │       ├─ RegisterPrefetchTask (用 B 的 client_id)
        │                                │       └─ PrefetchKeys → B 的 SSD → B 的 DRAM
        │                                └─ return true (fire-and-forget)

  关键: 数据不搬到 requester 节点。Holder 自己的 SSD → Holder 自己的 DRAM。
  后续 requester 通过正常的跨节点 RDMA get() 从 holder DRAM 拉取。

  远程 delegation 在所有 chunk 完成后才执行（非 pipeline）← 已知优化点

Step 11: get 侧等待 — batch_get_into_multi_buffers_internal
  当 get() 发现 best_replica 是 LOCAL_DISK 且 ssd_get_wait_ms_ > 0:

  模式 A: local wait (TP0 — 本进程在 exist 时 trigger 了 prefetch)
    prefetch_wait_mode = "local"
    throttle->waitForCompletion(key, ssd_get_wait_ms_, poll=1ms)
    → poll throttle 本地状态，等待 kCompleted
    TryRefreshBestMemoryReplica(client, key) → client->Query(key)
    → 如果 MEMORY replica 出现了 → refreshed_qr = new QueryResult

  模式 B: master poll (TP1~7 — exist 在 TP0 触发，自己无 trigger 记录)
    prefetch_wait_mode = "master"
    while NowMs() < deadline:
      TryRefreshBestMemoryReplica(client, key)  ← 循环调用 Query master
      → 如果 MEMORY replica 出现 → break
      sleep(1ms)

  注意: TryRefreshBestMemoryReplica 内部调用 client->Query(key) — 走了完整的 GetReplicaList
  → 会 grant lease、更新 metrics、触发 TryPushPromotionQueue
  → 这意味着如果 prefetch 失败，正常 promotion-on-hit 作为后备自动启动

Step 12: Observability — [GET-SRC] + [PREFETCH-OUTCOME]
  PrefetchReplicaSource: kDram / kSsd / kDisk / kUnknown
  PrefetchOutcome:
    dram_resident — 从未参与 prefetch，天然 DRAM 命中
    prefetch_hit — ★ promotion 在 get 前完成且 source=DRAM
    prefetch_dram_was_resident — key 本来在 DRAM，false trigger
    prefetch_promoted_untracked — promotion 成功但 throttle 未记录 done
    prefetch_miss_race — prefetch 触发但没赶上 get（source 仍是 SSD）
    prefetch_evicted_after_exist — 无 trigger/promote，get 时已是 SSD
    prefetch_failed — PrefetchKeys 执行失败
```

### 节流与并发控制全景

```
                 exist() 触发
                     │
                     ▼
         ┌──────────────────────┐
         │  PrefetchThrottle    │
         │  .inCooldown()?      │──yes──▶ DROP (DRAM 压力回退, 5s default)
         └──────────────────────┘
                     │ no
                     ▼
         ┌──────────────────────┐
         │  prefetch_pool_      │
         │  ThreadPool(4)       │──full─▶ DROP (不 block exist)
         └──────────────────────┘
                     │
                     ▼ (异步, 1 of 4 threads)
    ┌─────────────────────────────────────────┐
    │ BatchQueryForPrefetch(chunk=128)          │  ← 1 RPC/chunk
    │ → Master 只读 replica list（无副作用）     │
    └─────────────────────────────────────────┘
                     │
                     ▼
    ┌─────────────────────────────────────────┐
    │ ClassifySsdPrefetchRoute                  │
    │ → 有 MEMORY? 跳过                         │
    │ → local vs remote holder                  │
    └─────────────────────────────────────────┘
                     │
           ┌─────────┴──────────┐
           ▼                    ▼
    ┌─────────────┐    ┌──────────────────┐
    │ local keys  │    │ remote keys       │
    │ (pipelined) │    │ (deferred to end) │
    └─────────────┘    └──────────────────┘
           │
           ▼
    ┌─────────────────────────────────────────┐
    │ PrefetchThrottle::reserve()              │  ← dedup TTL (30s default)
    │ → same key already in TTL window? skip   │
    └─────────────────────────────────────────┘
           │
           ▼
    ┌─────────────────────────────────────────┐
    │ per-key RegisterPrefetchTask             │  ← Master: PromotionTask{from_prefetch=true}
    │ + throttle->markInFlight()               │     promotion_in_flight_++
    └─────────────────────────────────────────┘
           │
           ▼
    ┌─────────────────────────────────────────┐
    │ PrefetchKeys(all local keys)             │  ← 串行 per-key:
    │   PromotionAllocStart → AllocateBatch    │
    │   → BatchLoad → PromotionWrite           │
    │   → NotifyPromotionSuccess               │
    │ → NO_AVAILABLE_HANDLE → enterCooldown()  │
    └─────────────────────────────────────────┘
```

### 已知 Bug 修复清单 (B1-B10)

| ID | 症状 | 根因 | 修复 |
|----|------|------|------|
| B1 | Prefetch storm → offload 饿死 | vLLM 对同一批 key 每步调 exists() → 大量 detach thread 抢占 SSD IOPS/DRAM | dedup TTL (30s) + ThreadPool(4) |
| B2 | REPLICA_IS_NOT_READY | 双路径（Query 入队 + PrefetchKeys 直接调用）都在 promote 同一 key | RegisterPrefetchTask 不推 heartbeat 队列 |
| B7 | 串行 metadata Query + exist 同步 reserve → prefetch_hit 仅 40% | 全量 Query 后才 register → 首轮 get 已到达；reserve 在 exist 同步路径 → DRAM key 的 false trigger | BatchQuery(128) + 延迟 reserve（BatchQuery 后） |
| B8 | PrefetchKeys INVALID_KEY | AllocateBatch 的 map key 不是 tenant-scoped storage key | 使用 MakeTenantScopedStorageKey |
| B10 | get 路径 INVALID_KEY（与 prefetch 无关） | BatchOffload 的 NotifyOffloadSuccess（Master 注册 LOCAL_DISK）早于 commit 本地 object_bucket_map_ | commit local index 提前到 Notify 前 + RollbackCommittedBucket 回滚 |

### 设计上的已知局限

1. **`promotion_in_flight_` 共享**：prefetch 和正常 promotion 共用计数器 + `promotion_queue_limit_`（50000），大 batch prefetch 可能挤占正常 promotion 配额
2. **Master 假批处理**：`BatchGetReplicaListForPrefetch` 在 master 端循环 per-key 调 `GetReplicaListForPrefetch`，128 key → 128 次独立锁获取
3. **PrefetchKeys 串行**：per-key PromotionAllocStart → SSD read → PromotionWrite 是严格串行的
4. **Remote delegation 推迟**：所有 chunk 完成后才 delegate remote keys，不如本地 keys 的 pipelined
5. **无 tenant 感知**：prefetch RPC 硬编码 `"default"` tenant
6. **`PrefetchThrottle::entries_` 无界**：TTL 清理只在 `reserve()` 中触发。cooldown 长期激活时永不清理

### 关键源码位置

| 文件 | 关键内容 |
|------|----------|
| `mooncake-store/include/real_client.h:70-287` | `PrefetchThrottle` 完整实现 |
| `mooncake-store/include/real_client.h:80-287` | `PrefetchThrottle::reserve()`、`markInFlight()`、`waitForCompletion()` |
| `mooncake-store/src/real_client.cpp:2044-2080` | `isExist` / `batchIsExist` with ExistOptions |
| `mooncake-store/src/real_client.cpp:2104-2250` | `ClassifySsdPrefetchRoute`、`RunLocalPrefetchRegisterAndPromote`、`TryRefreshBestMemoryReplica` |
| `mooncake-store/src/real_client.cpp:2240-2520` | `triggerSsdPrefetch`（chunk batch + pipeline）、`initPrefetchRuntime`、`submitPrefetchJob` |
| `mooncake-store/src/real_client.cpp:2520-2560` | `runLocalPrefetch`（RPC delegation entry） |
| `mooncake-store/src/real_client.cpp:5323-5560` | `batch_get_into_multi_buffers_internal`：get 侧 wait + [GET-SRC]/[PREFETCH-OUTCOME] |
| `mooncake-store/src/file_storage.cpp:833-806` | `FileStorage::PrefetchKeys`：完整 promotion 执行链 |
| `mooncake-store/src/master_service.cpp:1445-1466` | `GetReplicaListForPrefetch`：只读 metadata（无 lease/sketch/enqueue 副作用） |
| `mooncake-store/src/master_service.cpp:1473-1526` | `RegisterPrefetchTask`：Master 侧注册 + holder 授权 |
| `mooncake-store/src/master_service.cpp:3483-3588` | `TryPushPromotionQueue`：对比——正常 promotion 的准入控制 |
| `mooncake-store/src/master_service.cpp:3615-3706` | `PromotionAllocStart`：分配 PROCESSING MEMORY replica |
| `mooncake-store/src/master_service.cpp:3709-3790` | `NotifyPromotionSuccess`：from_prefetch → GrantLeaseForGroup |
| `mooncake-store/src/master_service.cpp:726-800` | `GrantLeaseForGroup`：lease 保护（支持 grouped keys） |
| `mooncake-store/src/storage_backend.cpp:1329-1386` | B10 fix: `BatchOffload` commit local index before NotifyOffloadSuccess |
| `mooncake-store/include/types.h:216-229` | 配置常量 + 默认值 |
| `mooncake-store/include/replica.h:143-167` | `ExistOptions` 结构体 |
| `docs/source/design/ssd-prefetch.md` | 完整设计文档（331 行） |
