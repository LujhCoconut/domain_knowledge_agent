# Cloud-Native Architecture

## 子主题

| 主题 | 关键词 | 来源 |
|------|--------|------|
| 解耦式 GC 服务 | disaggregated GC, RDMA paging, multi-tenant orchestration, peak shaving, concurrent marking | DGC(OSDI'26) |

---

## 解耦式垃圾回收服务 (DGC)

### 核心问题
并发 GC 的标记线程在多租户 CPU 受限环境中与 mutator 直接竞争 CPU → 应用可用 CPU 降至 60% → 平均延迟上升超过一个数量级。这是周期性资源消耗（标记 burst）+ 固定 CPU 限制的必然冲突。

### 关键洞察

1. **"Shaving the peaks"**：将周期性标记负载从原始运行时解耦为独立服务 → 消除与 mutator 的 CPU 竞争
2. **RDMA-based software paging** 消除远程执行的性能代价：按需页交换 → 远程标记引擎"接近本地性能"
3. **Global orchestrator 错峰调度**：多个运行时独立触发 GC → 错峰避免 burst 叠加 → 平滑总体负载
4. **资源池化**：独立的标记资源池被多运行时时间复用——提高整体资源利用率
- 来源：DGC(OSDI'26)

### 实践启发
- "Shaving the peaks" 策略适用于任何周期性资源消耗任务（日志刷新、索引构建、压缩、备份）
- 将"周期性任务"转变为"外部服务 + 错峰调度"是处理多租户环境中峰值问题的通用范式
- RDMA 不仅是数据传输工具——也是实现"远程执行但本地性能"的系统架构基础
