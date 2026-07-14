# vBOIDs(OSDI'26)

- **来源**: https://www.usenix.org/system/files/osdi26-manakkal.pdf
- **类型**: 论文-系统
- **一句话 TL;DR**: 粗粒度 BOID 抽象将容器线程打包为少量调度单元 + 两级负载均衡，消除高密度容器部署的调度混沌（inter-core migration 降低一个数量级），吞吐 up to 3×。

## 重要术语解释

| 术语 | 解释 | 在本文中的作用 |
|------|------|----------------|
| Scheduling chaos | 高密度容器产生大量线程→CFS 频繁负载均衡→inter-core migration 比 VM 高一个数量级→硬件局部性崩溃 | 核心问题定义 |
| BOID | 将每个容器的线程打包为少量虚拟 CPU 调度单元 | 核心抽象——Bundled cOntaIner thread scheDuling |
| Two-level balancing | 全局层：host scheduler 迁移 BOID；本地层：BOID 内线程重分配 | 保持负载均衡同时消除跨核颠簸 |
| Container thread leakage | 容器将内部并发直接暴露给 host 内核——一个微服务可能展开为数百个 host-visible 线程 | VM 通过 vCPU 抽象掩盖了这一点 |
| Inter-core migration amplification | 容器的跨核迁移率比 VM **高一个数量级** | 调度混沌的机制根源 |

## 核心问题

云运行时每台机器部署数千容器（Alibaba RunD: 2500+/node, Junction: 3000+）。容器 "轻量"但比 VM 表现更差（**低 80%+**）。根本原因：容器将内部并发直接暴露给 host 内核——一个微服务（如 Hotel Reservation 24 个服务）展开为 **500+ host-visible 线程**。VM 通过 vCPU 抽象掩盖了这一点（仅 50 个 vCPU），而容器没有这个抽象层→inter-core migration 比 VM 高一个数量级→TLB shootdown + cache invalidation + branch predictor disruption → **scheduling chaos**。

## 关键洞察

1. **"缺少 vCPU 等效的粗粒度调度抽象是根本问题"**：VM 性能较好不是因为隔离更重，而是因为 vCPU 将内部并发折叠为少量调度单元。vBOIDs 为容器提供了等效的 BOID 抽象。
2. **"两级均衡解耦全局和局部负载管理"**：host scheduler 只管理少量 BOID（粗粒度），内部 balancer 在 BOID 内分配线程（细粒度、局部）→消除跨核颠簸的同时保持利用效率。
3. **"纯内核实现，零应用/编排框架修改"**：对 Kubernetes/容器 runtime 完全透明。

- 来源：vBOIDs(OSDI'26)

### 实践启发
- **"粗粒度抽象不是更弱——是更稳定"**：VM 的 vCPU 抽象恰好在高密度场景下提供了稳定性。容器的 "透明性" 在这里变成了诅咒。适当的抽象 > 完全的透明
- **"不要给调度器太多选择"**：CFS 在数千线程面前过度反应→减少选择空间（只调度少量 BOID）→调度器表现更好
