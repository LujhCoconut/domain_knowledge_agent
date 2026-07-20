# Mooncake TENT (Transfer Engine)

TENT 是 Mooncake 的新一代 Transfer Engine，从 Mooncake TE v1 的命令式接口演进到声明式编排架构。设计目标是解决异构互连环境（NVLink、RDMA、CXL、Ascend HIXL、io_uring 等多协议混合）中的通信孤岛、静态调度和运维脆弱性问题。

> 资料来源：Feng Ren 的 TENT Internal 系列博客（2026年4-5月，renfeng.org），【确信】— 作者是 Mooncake 核心开发者。

---

## TENT #1：架构设计概览

### 背景与问题

**AI 集群互连的三阶段演进**：
- 2024：P/D (Prefill/Decode) 分离——解耦计算密集型 Prefill 与访存密集型 Decode
- 2025：KVCache 大规模应用——"以存储换计算"范式，KVCache 成为核心状态资产
- 2026：智能体（Agent）爆发——推理中枢需要更长序列、更高频率交互

**三类状态资产**：
1. **KVCache**：由暂态数据演化为跨阶段复用的核心存储，Kimi 生产环境缓存命中率达 90%
2. **Online RL 权重更新**：Moonshot Checkpoint Engine 中以微秒级精度同步千亿参数的梯度/权重（"全量同步大象流"）
3. **MoE 专家并行（EP）流量**：Token 在 Expert 之间频繁穿梭，几十 KB 级的"老鼠流"，但在关键路径上

**三种互连链路**：
- Scale-up：NVLink/Ascend UB，机内或 rack 内，数百 GB/s
- Scale-out：RDMA（4-8 卡 × 400Gbps），机房内
- Cross-DC：以太网专线（PrfaaS 场景）

### Mooncake TE v1 的局限

**根源**：设计受 SMART (ASPLOS'24) 影响，以 RDMA 为中心的命令式接口。假设物理拓扑纯净、通信逻辑命令式。

**暴露的问题**：
1. Transport 目录臃肿——NVLink、国产平台（Ascend HIXL 等）各需手动适配，代码充斥条件编译
2. 互操作性差——"端点中心化"，传输元数据与后端绑定。无法混合 NVIDIA GPU + 国产芯片 + NVLink 在同一集群
3. 运维脆弱——硬件故障（链路闪断、坏卡）需应用层干预，容易扩散故障到整个集群

**命令式接口示例** (NIXL)：

```cpp
// ❌ NIXL 风格：agent、backend、segment、metadata 紧密绑定
NIXLAgent *agent = nixlCreateAgent("node_0");
NIXLBackend *ucx_be = nixlCreateBackend(agent, "UCX");  // 显式绑定
NIXLSegment *seg = nixlCreateSegment(agent, gpu_ptr, size, ucx_be);
NIXLMetadata md = nixlGetSegmentMetadata(seg);           // 需手动交换元数据
```

核心问题：agent、backend、segment 是紧绑定关系，无法混用。UCX 在编译时绑定单一 GPU 生态（CUDA vs ROCm vs 国产卡），运行时不同厂商的 IPC handle 不兼容。

### 三大困境

1. **通信孤岛**：传输元数据与特定后端绑定，互连是孤岛而非资源池
2. **状态盲调度**：静态哈希/轮询无法感知网络状态 → 带宽闲置、尾部延迟激增
3. **运维脆弱**：硬件故障视为异常，需应用层干预

### 声明式 API 接口

```cpp
struct tent_request {
    int opcode;
    void *source;
    tent_segment_id_t target_id;   // 只指定目标 segment，不关心传输路径
    uint64_t target_offset;
    uint64_t length;
    int priority;                   // QoS: TENT_PRIO_HIGH/MEDIUM/LOW
};

int tent_submit(tent_engine_t engine, tent_batch_id_t batch_id,
                 tent_request_t *entries, size_t count);
```

**关键差异**：
- 对外只暴露透明的 Segment 语义
- Segment 元数据和 Transport 调度完全是 TENT 内部的事
- 单次 `tent_submit` 可提交**异构**任务：RDMA 远端搬迁 + io_uring SSD 持久化，同批并发执行

### 四层架构

| 层 | 职责 |
|----|------|
| **声明接口层** | 应用层用声明式 API 表达 Segment 为核心的存取意图 + SLO 约束 |
| **编排决策层** | Segment Manager 检索多维元数据，"晚期绑定"动态求解最优路径 |
| **传输抽象层** | 统一后端接口，细粒度切片 + 切片喷淋并行分发到多物理链路 |
| **物理执行层** | RDMA、NVLink、io_uring 等多协议确定性执行 |

### 核心架构组件

**① 统一段表示（Unified Segment）**：
DRAM、HBM、Disk 全部抽象为逻辑 Segment。每个 Segment 包含三维：
- **Buffers 维度**：同一块内存同时维护多种 Transport 的凭证/元数据（NVLink、RDMA、TCP）
- **Topology 维度**：Tier-1（NVLink 直连）→ Tier-2（跨 PCIe root）→ Tier-3（跨 NUMA）
- **Devices 维度**：硬件设备标准化抽象，屏蔽 RDMA 网卡 vs 国产卡协议差异

**② 统一传输后端**：
插件化接入（NVLink、RDMA、io_uring 等），统一操作原语（全部抽象为针对 Segment Slice 的异步读写），运行时动态切换或并行使用多个后端。

**③ 编排器（Orchestrator）**：
晚期绑定（提交瞬间解析路径）、自主路径合成（无直连时自动合成多跳）、实时遥测驱动。

### 生产验证数据

| 指标 | 提升 |
|------|------|
| SGLang HiCache 吞吐量 | 1.36× |
| P90 TTFT | 降低 26% |
| Moonshot Checkpoint Engine 权重更新 | 加速 20-26% |
| 八轨 200Gbps RDMA 吞吐量 | 提升 33% |
| P99 延迟 | 降至基线 27.6% |
| 故障恢复 | 亚 50ms 自动愈合 |
| 跨平台 | 6 个硬件生态 + 7 种传输协议 |

---

## TENT #2：编排器核心设计

### 编排器职责

1. **认知构建**：通过统一 Segment 元数据 + 传输插件构建对集群物理拓扑的深度认知
2. **动态决策**：基于实时遥测和 SLO 约束求解最优传输计划
3. **路径管理**：晚期绑定 + 路径合成实现跨协议智能选路
4. **故障恢复**：将硬件故障从异常处理降级为常规路由事件

### 统一段数据结构

```cpp
// tent/include/tent/runtime/segment.h

struct SegmentDesc {
    std::string name;              // 全局唯一标识符
    SegmentType type;              // Memory | File
    std::string machine_id;        // 所属节点 ID
    std::string rpc_server_addr;   // 元数据服务地址
    std::variant<MemorySegmentDesc, FileSegmentDesc> detail;
};

struct MemorySegmentDesc {
    Topology topology;             // 设备互联关系
    std::vector<DeviceDesc> devices;   // NIC/GPU 列表
    std::vector<BufferDesc> buffers;   // 内存区域
    std::unordered_map<int, std::string> transport_attrs;  // ★ 传输协议相关字段统一封装
};

struct BufferDesc {
    uint64_t addr;                 // 起始偏移
    uint64_t length;               // 长度
    std::string location;          // 位置，与拓扑信息匹配
    std::vector<TransportType> transports;  // 支持的 Transport 列表
    std::unordered_map<TransportType, std::string> transport_attrs;  // ★ 统一封装
};
```

**与 Mooncake TE v1 的关键改进**：传输协议特定字段（rkey、lid、mnnvl_handle）不再散落在核心数据结构中，而是统一封装为 `transport_attrs`。核心引擎只通过 `transports` 列表查询能力，无需解析协议细节。新增协议只需扩展 `TransportType` 枚举。

### Topology 模型

```cpp
class Topology {
    static const size_t DevicePriorityRanks = 3;

    struct MemEntry {
        std::string name;          // 如 "cuda:0"，与 location 匹配
        std::string pci_bus_id;
        MemType type;              // MEM_CUDA / MEM_ROCM / MEM_ASCEND / MEM_HOST
        int numa_node;
        // 按 affinity tier 分层的设备列表
        std::vector<NicID> device_list[DevicePriorityRanks];
        // device_list[0]: Tier-1 (原生高速路径, NVLink 直连)
        // device_list[1]: Tier-2 (跨 PCIe 根节点)
        // device_list[2]: Tier-3 (跨 NUMA 节点, fallback)
    };
};
```

初始化时自动枚举 GPU、NIC、NUMA 关系，将互联链路按亲和性分层。编排器据此决定路径搜索优先级，优先匹配物理距离最短的互连。

### Transport 插件抽象

```cpp
// tent/include/tent/runtime/transport.h

struct Capabilities {
    bool dram_to_dram, dram_to_gpu, gpu_to_dram,
         gpu_to_gpu, dram_to_file, gpu_to_file;
};

class Transport {
    // 批次管理（SubBatch = 最小调度单元）
    Status allocateSubBatch(SubBatchRef &batch, size_t max_size);
    Status freeSubBatch(SubBatchRef &batch);

    // 核心传输操作
    Status submitTransferTasks(SubBatchRef batch,
                               const std::vector<Request> &request_list);
    Status getTransferStatus(SubBatchRef batch, int task_id,
                             TransferStatus &status);

    // 内存管理
    Status addMemoryBuffer(BufferDesc &desc, const MemoryOptions &options);
    Status removeMemoryBuffer(BufferDesc &desc);
    Status warmupMemory(void *addr, size_t length);

    // 通知机制（可选，支持 TCP 和 RDMA 两种模式）
    bool supportNotification() const;
    Status sendNotification(SegmentID target_id, const Notification &notify);

    // 能力查询
    const Capabilities capabilities() const;
    const char *getName() const;
};
```

**支持的传输协议**：

| 协议 | 覆盖范围 | 零拷贝 | CPU 参与度 | 适用介质 |
|------|----------|--------|-----------|----------|
| NVLink | 机内/超节点 | ✅ | 极低 | GPU HBM ↔ GPU HBM |
| SHM/CXL | 单机进程间 | ✅ | 中 | DRAM ↔ DRAM |
| RDMA (IB/RoCE) | 跨节点集群 | ✅ | 极低 | DRAM/HBM 混合 |
| AscendDirect | 昇腾专链 | ✅ | 极低 | NPU HBM ↔ NPU HBM |
| GDS | 本地/存储网 | ✅ | 极低 | GPU HBM ↔ NVMe SSD |
| IO_URING | 本地存储 | ❌ | 中 | DRAM ↔ NVMe/HDD |
| TCP | 全局通用 | ❌ | 高 | 最通用, fallback |

### 晚期绑定（Late Binding）

**核心思想**：路径解析推迟到传输请求提交的瞬间。

与 Mooncake TE v1 / NIXL 的"早期绑定"（初始化时确定路径）相比：

1. **取 Transport 交集**：获取源/目标 Segment 元数据，在 Transport 插件集合中找能同时满足两者的交集
2. **Tier-aware 排序**：检测到两台设备在同一 NVLink 域（Tier-1）→ 强制锁定高性能直连路径
3. **QoS 约束匹配**：根据 SLO 过滤当前排队深度过高的 NIC

**价值**：应用层不再持有 stateful 端点句柄 → 编排器有绝对自由度根据瞬时状态重写执行计划。如果某条 RDMA 轨道链路抖动，下一次请求提交时自动避开，无需应用感知或重新初始化。

### 自主路径合成（Path Synthesis）

当源/目标之间不存在任何直接路径时，不是返回错误，而是自动合成多跳路径。

**示例**（远程 DRAM → GPU HBM）：

```
阶段 A: GPU → 本地 NUMA 亲和 DRAM (Device-to-Host)
阶段 B: DRAM → 多轨 RDMA → 远端 DRAM (Host-to-Host)
阶段 C: 远端 DRAM → GPU HBM (Host-to-Device)
```

**流水线加速**：总数据 M 分 n 块，完成时间：
$$T_{total} \approx \sum T_{startup} + \max(T_{D2H}, T_{H2H}, T_{H2D}) \times n$$

关键：第 1 块的阶段 B 与第 2 块的阶段 A 并发 → 中间中转延迟被掩盖。

---

## TENT #3：切片喷射与 QoS 机制

### Slice Spraying 算法

**背景**：多租户、高并发分布式存储中，多轨 RDMA 如何高效利用带宽 + 保障不同优先级 QoS。Mooncake TE v1 用 Round-Robin——无法感知网络实际状态。

**核心思想**：将所有轨道视为统一资源池，拆分数据为细粒度分片，基于遥测感知的成本模型对每个分片动态调度。

#### 阶段一：简单轮询（基线）

```cpp
// Mooncake TE 基线：thread_local Round-Robin
thread_local int id = 0;
for (size_t rank = 0; rank < Topology::DevicePriorityRanks; ++rank) {
    auto &list = entry->device_list[rank];
    if (list.empty()) continue;
    chosen_dev_id = list[id % list.size()];
    id++;
    return Status::OK();
}
```

优势：零开销，确定性强。但无法感知链路质量差异和动态负载变化。

#### 阶段二：双参数模型（早期 TENT，已弃用）

$$predicted\_time = weight \times \left( \frac{inflight\_bytes + request\_bytes}{bandwidth} \times \beta_1 + \beta_0 \right)$$

- $\beta_0$：固定延迟（PCIe 传输开销、连接建立时间）
- $\beta_1$：有效带宽修正系数
- 每张网卡分别维护 $\beta_0$、$\beta_1$，用指数平滑更新

**失败原因**：双参数增加调优复杂性；参数敏感，实际性能某些情况不如基线。

#### 阶段三：EWMA 单参数模型（当前方案）

$$predicted\_time = \frac{inflight\_bytes + request\_bytes}{ewma\_bandwidth} \times weight$$

**改进**：
- 不再用 $\beta_0$、$\beta_1$，简化为单一 EWMA 带宽估计
- 每设备只维护一个 `ewma_bandwidth`，传输完成时用实际带宽观测值更新
- 边界保护：EWMA 值约束在理论带宽的 10%-1000%
- **按比例分配**：大请求不采用"每个 Slice 独立决策网卡"，而是按 `predicted_time` 反比分配份额

```cpp
// 按设备容量比例分配
double total_weight = sum(c.score for c in candidates);
for (const Candidate &c : candidates) {
    uint32_t allocation = (c.score / total_weight) * num_slices;
    // ...
}
// 剩余分片分配给最优设备
```

### QoS 机制

#### 单进程内：严格优先级 + 防饥饿

- **严格优先级**：高 > 中 > 低，工作线程始终先处理高优先级队列
- **防饥饿超时提升**：等待超过阈值（默认 10ms）→ 中→高、低→中逐步提升
- 实现：请求入队时记录 `enqueue_ts`，检查时比较 `now - enqueue_ts > threshold`

#### 跨进程：时隙协调机制

共享内存中维护全局时隙状态，后台线程定期旋转：

```
时隙 0 (2ms): 只允许 HIGH  → 高优先级独占窗口
时隙 1 (2ms): HIGH + MEDIUM
时隙 2 (2ms): ALL (HIGH + MEDIUM + LOW)
周期总长: 6ms (可配)
```

**设计效果**：
- 高优先级请求在每个时隙都能服务，时隙 0 为独占执行窗口 → 最低延迟
- 中优先级在 2/3 的时隙中可获得服务
- 低优先级在 1/3 的时隙中被允许执行
- 所有优先级都不会被无限期卡死

**可配置项**：时隙间隔（1ms–10ms）、防饥饿超时（默认 10ms）

#### 性能实测

H20 测试床，2 个并发进程 × 8 提交线程，4×400Gbps RoCE：

- 进程 1：64 KB 老鼠流（高优先级，MoE EP 流量）
- 进程 2：64 MB 大象流（低优先级，KVCache 迁移）

| 对比 | 老鼠流 P50 延迟 |
|------|----------------|
| No QoS vs QoS (High+Low) | 降低 15.1% |

P99 稳定——高优先级永远不会被后台流量无限期卡死。

---

## 架构总结

| 维度 | Mooncake TE v1 (旧) | TENT (新) |
|------|---------------------|-----------|
| 接口范式 | 命令式（直接 API 转译） | 声明式（意图 + SLO） |
| 路径绑定 | 早期绑定（初始化时） | 晚期绑定（提交瞬间） |
| 无直连处理 | 返回错误 | 自主路径合成（多跳 pipeline） |
| 传输后端 | 紧耦合（代码散落各协议字段） | 插件化（统一 `transport_attrs` + `Transport` 基类） |
| 链路调度 | 静态 Round-Robin | EWMA 感知的比例分配（Slice Spraying） |
| QoS | 无 | 严格优先级 + 防饥饿 + 跨进程时隙协调 |
| 故障处理 | 应用层感知 + 人工干预 | 亚 50ms 自动愈合（数据面路由事件） |
| 跨平台 | 条件编译 + 版本碎片化 | 单一二进制 + 运行时动态加载 `.so` 插件 |

### 来源

- Feng Ren, "TENT Internal #1: 架构设计概览", 2026-04-24, https://renfeng.org/zh/posts/tent-internal-arch/
- Feng Ren, "TENT Internal #2: 编排器核心设计", 2026-05-09, https://renfeng.org/zh/posts/tent-internal-orchestrator-part-1/
- Feng Ren, "TENT Internal #3: 切片喷射与 QoS 机制", 2026-05-20, https://renfeng.org/zh/posts/tent-internal-slice-spraying-and-qos/
