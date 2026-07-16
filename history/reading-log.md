# Reading Log

本文件记录所有已被解析并归档到 skill 知识库的论文/资料。

| 日期 | 资料标题 | 类型 | 来源 | 解析 skill | 归档位置 | 备注 |
|------|----------|------|------|------------|----------|------|
| 2026-07-13 | PACT(ASPLOS'26) | 论文-系统 | ASPLOS '26, PACT_ASPLOS.pdf | knowledge-synthesis | performance/system-tuning/, algorithms/ | 提出 PAC 指标量化每页 CPU stall 代价，替代 hotness 驱动 tiered memory 管理，最高 61% 性能提升 + 50× 迁移减少 |
| 2026-07-13 | TMO(ASPLOS'22) | 论文-系统 | ASPLOS '22, tmo_asplos22.pdf | knowledge-synthesis | performance/system-tuning/ | Meta 透明内存 offloading，PSI + Senpai 实现 fleet-wide 20-32% 内存节省，已上游化 Linux 内核 |
| 2026-07-13 | M5(ASPLOS'25) | 论文-系统 | ASPLOS '25, DOI:10.1145/3676641.3711999 | knowledge-synthesis | performance/system-tuning/ | CXL 控制器集成 HPT/HWT 硬件追踪器，发现稀疏热页问题，47% 更热页面识别 + 14% 更高性能 |
| 2026-07-13 | CAMP(ASPLOS'26) | 论文-系统 | ASPLOS '26, DOI:10.1145/3779212.3790201 | knowledge-synthesis | performance/system-tuning/ | CXL slowdown 预测框架，12 PMU counters + 3-分量分解，91-97% 预测精度，Best-shot 交错提升 21% |
| 2026-07-13 | Strata(OSDI'26) | 论文-系统 | OSDI '26, osdi26-xie-zhiqiang.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | GPU 辅助 I/O + 缓存感知调度，长上下文 LLM 推理最高 5× 吞吐提升，集成 SGLang 生产部署 |
| 2026-07-13 | ECHO(OSDI'26) | 论文-系统 | OSDI '26, osdi26-liu-guangda.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | 面向稀疏注意力的 graph-friendly 动态 KV cache offloading + 无损 prefetching，DeepSeek-V3.2 最高 2.1× 吞吐提升 |
| 2026-07-13 | DirectKV(OSDI'26) | 论文-系统 | OSDI '26, osdi26-luo.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | 首个 GH200 zero-copy KV offloading，CPU-aware tiling + fused kernel，GPU 内存 -43%，传输 -50%，性能 +1.2× |
| 2026-07-13 | LMetric(OSDI'26) | 论文-系统 | OSDI '26, arXiv:2603.15202 | knowledge-synthesis | performance/gpu-ai-performance/ | 乘法调度 (P-token×BS)，无需调参，TTFT -92% vs vLLM，TPOT -51% vs 生产调度器，阿里百炼生产部署 |
| 2026-07-13 | Prism(OSDI'26) | 论文-系统 | OSDI '26, osdi26-yu-shan.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | GPU 显存 ballooning (kvcached) 统一 time/space sharing，3.3× SLO 达成率，10K+ GPU 生产部署 |
| 2026-07-13 | RamRyder(OSDI'26) | 论文-系统 | OSDI '26, osdi26-zhou-yanbo.pdf | knowledge-synthesis | architecture/cloud-native/, performance/system-tuning/ | 软件定义内存通道管理，容量+带宽独立分配，集群利用率 +28.6%(容量) +43.2%(带宽) |
| 2026-07-13 | MAC(OSDI'26) | 论文-系统 | OSDI '26, osdi26-lee.pdf | knowledge-synthesis | performance/system-tuning/ | CXL NMP 加速内核元数据回收，解决 metadata 溢出导致的尾延迟尖刺，p99.99 -98% |
| 2026-07-13 | NEMO(OSDI'26) | 论文-系统 | OSDI '26, osdi26-li-shihang.pdf | knowledge-synthesis | performance/system-tuning/ | MC 内可编程 telemetry pipeline，hot-set检测 5× 加速、THP拆分 10.4×、noisy neighbor检测 CPU开销 -350× |
| 2026-07-13 | OBASE(OSDI'26) | 论文-系统 | OSDI '26, osdi26-banakar.pdf | knowledge-synthesis | performance/system-tuning/ | 编译器辅助 address-space engineering，解耦 layout/tiering，page utilization 2-4×，内存节省 70%，overhead 2-5% |
| 2026-07-13 | MDK(OSDI'26) | 论文-系统 | OSDI '26, osdi26-patel.pdf | knowledge-synthesis | performance/system-tuning/ | 数据中心内存回收理论框架，OPP+MPC+性质+高效生成(12.5-208×)，3 个新策略最高 +10% 内存节省 |
| 2026-07-13 | USEC(OSDI'26) | 论文-系统 | OSDI '26, osdi26-jiang-yu.pdf | knowledge-synthesis | security/os-security/ | Resource-centric MAC 框架，策略代码 -10×, overhead -17.1%, 800 万+端点部署 |
| 2026-07-13 | Mohabi(OSDI'26) | 论文-系统 | OSDI '26, osdi26-sharma.pdf | knowledge-synthesis | security/os-security/ | 首个浏览器 JS engine SFI sandbox (SpiderMonkey/Firefox)，JetStream 24.82%, MH-LFI SPEC 5.9-6.6% |
| 2026-07-13 | Ichnaea(OSDI'26) | 论文-系统 | OSDI '26, osdi26-haque.pdf | knowledge-synthesis | security/os-security/ | MPK-based 对象级内存追踪，10-60× faster than Pin, per-access call stack + data diff |
| 2026-07-13 | Ote(OSDI'26) | 论文-系统 | OSDI '26, osdi26-zhang-wen.pdf | knowledge-synthesis | security/os-security/ | 从 web 应用自动提取 DB access-control policy (concolic+LLM)，发现手写 policy 中多个错误 |
| 2026-07-13 | iLand(OSDI'26) | 论文-系统 | OSDI '26, osdi26-xie-kaitao.pdf | knowledge-synthesis | security/os-security/ | 首个非越狱 iOS 指令级 DBI，21% 头部 app 仍调用私有 API，25% 通过 SVC 绕过 App Review |
| 2026-07-13 | Tessera(OSDI'26) | 论文-系统 | OSDI '26, osdi26-hu-weifang.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | 万亿参数 MoE 训练 PP 优化，overlap-aware partitioner + 合成 overlap scheduler + dynamic bubble optimizer，20-33% throughput 提升 |
| 2026-07-13 | Hetu-v2(OSDI'26) | 论文-系统 | OSDI '26, osdi26-li-haoyang.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | HSPMD 扩展 SPMD 支持非对称分片+层级通信，统一处理混合 GPU/故障/变长序列三种异质性 |
| 2026-07-13 | Syncopate(OSDI'26) | 论文-系统 | OSDI '26, osdi26-qiang.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | 编译器自动 chunk-centric compute-comm overlap，Triton 源码到源码，avg 1.3×, max 4.7× speedup |
| 2026-07-13 | ByteDance DataPipeline(OSDI'26) | 论文-系统 | OSDI '26, osdi26-chen-luofan.pdf | knowledge-synthesis | performance/storage-filesystem/ | LLM 预训练数据管线优化，30K job/90d trace 分析，GPU 浪费 -76%, checkpoint 加载 -40.8%, training stall -63.2% |
| 2026-07-13 | Cocoon(OSDI'26) | 论文-系统 | OSDI '26, osdi26-kim-donghwan.pdf | knowledge-synthesis | security/os-security/ | DIF 训练相关噪声的首个系统表征，CPU-GPU-NMP 三级噪声历史管理+稀疏嵌入优化，1.23-10.82× 加速 |
| 2026-07-13 | ValScope(OSDI'26) | 论文-系统 | OSDI '26, osdi26-lin-li.pdf | knowledge-synthesis | algorithms/ | 值语义感知的 metamorhpic testing，统一 set+value 语义推理，6 DBMS 发现 67 unique bugs |
| 2026-07-13 | CoreSec(OSDI'26) | 论文-系统 | OSDI '26, osdi26-gaikwad.pdf | knowledge-synthesis | operations/monitoring-observability/ | PAM 弃权代数驱动的 Clos 网络 RCA，确定性决策+显式弃权，Azure 超大规模部署 |
| 2026-07-13 | SPEX(OSDI'26) | 论文-系统 | OSDI '26, osdi26-zhong.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | 推测性探索打破 ToT reward barrier，1.2-3× 加速，与 token 级推测解码叠加达 4.1× |
| 2026-07-13 | try/semisolates(OSDI'26) | 论文-系统 | OSDI '26, osdi26-lamprou.pdf | knowledge-synthesis | security/os-security/ | 无特权半隔离执行任意 opaque 组件并捕获文件系统 effects，支持 inspect/selectively apply/revert |
| 2026-07-13 | SBB(OSDI'26) | 论文-系统 | OSDI '26, osdi26-hu-kang.pdf | knowledge-synthesis | network/os-networking/ | 去中心化用户态网络 runtime，消除集中式 timer/monitor/dispatcher 瓶颈，48核 1.7-5.2× 吞吐提升 |
| 2026-07-13 | Rakaia(OSDI'26) | 论文-系统 | OSDI '26, osdi26-yang-rui.pdf | knowledge-synthesis | network/os-networking/ | 内核级 TCP RPC 消息调度，消除 HOL blocking + 用户态线程开销，5× vs KCM, 1.56× vs gRPC-Go, 2.69× vs gRPC-C++ |
| 2026-07-13 | kSTEP(OSDI'26) | 论文-系统 | OSDI '26, osdi26-cao.pdf | knowledge-synthesis | operations/os-testing/ | 232 scheduler bug 表征+确定性测试框架+coverage-guided fuzzer，复现7个已知+发现4个新bug |
| 2026-07-13 | mwait-sched(OSDI'26) | 论文-系统 | OSDI '26, osdi26-wang-yun.pdf | knowledge-synthesis | operations/cloud-infrastructure/ | mwait-passthrough 在超卖场景下失效→mwait-sched 恢复 idle visibility，P99 latency -30%~50%, steal -30%~40%, 3.2M pCPUs |
| 2026-07-14 | Xkernel(OSDI'26) | 论文-系统 | OSDI '26, osdi26-chen-zhongjie.pdf | knowledge-synthesis | operations/os-performance-tuning/ | SIE（Scoped Indirect Execution）将任意内核 perf-const 转化为运行时安全可调 knob，无需重编译/重启，NIC tuning 50× 吞吐提升 |
| 2026-07-14 | Murakkab(OSDI'26) | 论文-系统 | OSDI '26, osdi26-chaudhry.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | 声明式 agentic workflow 编排，profile-guided cross-layer optimizer + adaptive runtime，GPU -2.8×, 能耗 -3.7×, 成本 -4.3× |
| 2026-07-14 | ECO(OSDI'26) | 论文-系统 | OSDI '26, osdi26-lin-hannah.pdf | knowledge-synthesis | operations/os-performance-tuning/ | LLM 驱动的生产代码优化，fleet profiling+embedding search+anti-pattern mining，6,400+ commits, 99.5% 无回滚 |
| 2026-07-14 | StriaTrace(OSDI'26) | 论文-系统 | OSDI '26, osdi26-wu-haonan.pdf | knowledge-synthesis | operations/monitoring-observability/ | LLM 推理在线 tracing/诊断，三原则（同步点+关键路径+异常详细追踪），overhead -97.8%, 19 种根因 |
| 2026-07-14 | gigiprofiler(OSDI'26) | 论文-系统 | OSDI '26, osdi26-hu-yigong.pdf | knowledge-synthesis | operations/monitoring-observability/ | LLM+静态分析混合方法诊断应用定义资源的性能问题，15/15 已知+2 新 MariaDB bug |
| 2026-07-14 | hS(OSDI'26) | 论文-系统 | OSDI '26, osdi26-liargkovas.pdf | knowledge-synthesis | operations/program-analysis/ | 推测性 shell 脚本乱序执行，动态 syscall tracing 替代手工 annotation，vs bash 9.3×, vs PaSh 7× |
| 2026-07-14 | Incr(OSDI'26) | 论文-系统 | OSDI '26, osdi26-xie-yizheng.pdf | knowledge-synthesis | operations/program-analysis/ | 自动增量 shell 重新执行，effect analysis+缓存复用，avg 34.2×, max 373.3×, 10K+ 测试用例行为等价 |
| 2026-07-14 | UCSan(OSDI'26) | 论文-系统 | OSDI '26, osdi26-yin.pdf | knowledge-synthesis | operations/program-analysis/ | 编译-based under-constrained 执行引擎，任意 C/C++ 函数集独立可执行，vs KLEE 15.06× 快 |
| 2026-07-14 | Aletheia(OSDI'26) | 论文-系统 | OSDI '26, osdi26-ferreira.pdf | knowledge-synthesis | operations/program-analysis/ | ER模型+关系代数静态检测微服务数据完整性违规，7 apps 发现 46 个未报告违规 |
| 2026-07-14 | Arctic(OSDI'26) | 论文-系统 | OSDI '26, osdi26-ni.pdf | knowledge-synthesis | algorithms/concurrent-data-structures/ | 首个同时实现高性能+lock-free+range scan 的自适应基数树，hazard keys SMR, RocksDB +40% |
| 2026-07-14 | Soul/GCP(OSDI'26) | 论文-系统 | OSDI '26, osdi26-yu-yanpeng.pdf | knowledge-synthesis | architecture/memory-storage-hierarchy/ | 泛化缓存一致性原生支持同步，disaggregated memory 上 1-2 orders magnitude 提升 |
| 2026-07-14 | DGC(OSDI'26) | 论文-系统 | OSDI '26, osdi26-lyu.pdf | knowledge-synthesis | architecture/cloud-native/ | 解耦式 GC 服务，标记阶段 RDMA offload 至远程引擎，P99 latency -64.4%, goodput +24% |
| 2026-07-14 | DeLFS(OSDI'26) | 论文-系统 | OSDI '26, osdi26-ahn.pdf | knowledge-synthesis | performance/storage-filesystem/ | 去中心化 LFS，per-core domain + decentralized locking，128 核上 vs F2FS 4.34× |
| 2026-07-14 | Weave(OSDI'26) | 论文-系统 | OSDI '26, osdi26-wu-tianyuan.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | RL 后训练 co-scheduling，co-execution group 消除 dependency bubble，成本效率 +1.84× |
| 2026-07-14 | RLinf(OSDI'26) | 论文-系统 | OSDI '26, osdi26-yu-chao.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | M2Flow 宏观→微观流变换，context switching+elastic pipelining，1.07-2.43× 加速 |
| 2026-07-14 | DynaRL(OSDI'26) | 论文-系统 | OSDI '26, osdi26-wang-yuanqing.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | 动态超图+资源迁移，首个运行时动态重分配 RL 资源调度，最高 1.98× 吞吐提升 |
| 2026-07-14 | RollArt(OSDI'26) | 论文-系统 | OSDI '26, osdi26-gao.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | 异构硬件映射+trajectory 级解耦，serverless reward，1.31-2.05× 训练时间减少, 3,000 GPU 验证 |
| 2026-07-14 | Seer(OSDI'26) | 论文-系统 | OSDI '26, osdi26-qin.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | 同步 RL rollout 优化，divided rollout+context-aware sched+adaptive grouped speculation，2.04× 吞吐，长尾延迟 -72-94% |
| 2026-07-14 | LiteSwitch(OSDI'26) | 论文-系统 | OSDI '26, osdi26-li-nanqinqin.pdf | knowledge-synthesis | performance/system-tuning/ | CXL sub-µs stall harvesting，硬件识别+20ns 超快软件切换，回收 CXL 延迟损失 80% |
| 2026-07-14 | Duhu(OSDI'26) | 论文-系统 | OSDI '26, osdi26-men.pdf | knowledge-synthesis | architecture/memory-storage-hierarchy/ | SDM pass-by-reference 对象存储，消除 DDF 数据复制开销，shuffle 3.39×, stage 3.59-13.81× |
| 2026-07-14 | Blowfish(OSDI'26) | 论文-系统 | OSDI '26, osdi26-zhang-yulong.pdf | knowledge-synthesis | architecture/memory-storage-hierarchy/ | 分离式内存 VM 超卖，半虚拟化 THP-aware 追踪+hypervisor 直通路径，回收 2.48×, 恢复 2.14× |
| 2026-07-14 | Espresso(OSDI'26) | 论文-系统 | OSDI '26, osdi26-yi.pdf | knowledge-synthesis | performance/storage-filesystem/ | CXL JBOF 跨 SSD 计算资源共享，去中心化 compute pooling，成本降低 19%, 性能退化可忽略 |
| 2026-07-14 | FORGE(OSDI'26) | 论文-系统 | OSDI '26, osdi26-yang-zhijun.pdf | knowledge-synthesis | performance/storage-filesystem/ | DM 缓存同步放大缓解，组级同步+惰性热度+RDNA NIC 卸载，吞吐 4.5×, P99 延迟 7.5× |
| 2026-07-14 | ZENO(OSDI'26) | 论文-系统 | OSDI '26, osdi26-huang-wenxuan.pdf | knowledge-synthesis | security/os-security/ | Crypto-free CDB 映射，解耦间接寻址与保护，TPC-H 53-95× vs HEDB, 集成 GaussDB |
| 2026-07-14 | Janus(OSDI'26) | 论文-系统 | OSDI '26, osdi26-lai.pdf | knowledge-synthesis | operations/cloud-infrastructure/ | 协同嵌套虚拟化安全容器，CPU/内存翻译解耦，VMFUNC EPTP switching + shadow-root |
| 2026-07-14 | Osprey(OSDI'26) | 论文-系统 | OSDI '26, osdi26-liu-yicheng.pdf | knowledge-synthesis | security/os-security/ | SC 透明虚拟内存，利用 obliviousness 实现 speculative paging，128× 数据扩展, <200 LOC/libs |
| 2026-07-14 | Nested SEV(OSDI'26) | 论文-系统 | OSDI '26, osdi26-takiguchi.pdf | knowledge-synthesis | operations/cloud-infrastructure/ | 嵌套机密VM通用支持，emulation-less multiplexing + SEV context decoupling，两种信任模型 |
| 2026-07-14 | µUSB(OSDI'26) | 论文-系统 | OSDI '26, osdi26-zhang-xuankai.pdf | knowledge-synthesis | security/os-security/ | record→lift→replay 从执行trace推导TrustZone精简USB驱动，首次in-TEE USB支持 |
| 2026-07-14 | CPU-GPU Hybrid MoE(OSDI'26) | 论文-系统 | OSDI '26, osdi26-wang-wenxin.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | 本地CPU-GPU混合MoE推理，SLP 1,200 tok/s, 45K prompt in 30s, CPU FP8 4-5× |
| 2026-07-14 | UEP(OSDI'26) | 论文-系统 | OSDI '26, osdi26-mao-ziming-uep.pdf | knowledge-synthesis | network/os-networking/ | 可移植EP通信，CPU proxy解耦GPU-NIC，O(m)取代O(m×n)，EFA上2.1×吞吐提升，SGLang推理+40% |
| 2026-07-14 | BatchGen(OSDI'26) | 论文-系统 | OSDI '26, osdi26-xu-tairan.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | 序列协程批量推理，yield/combine/partition/migrate，BCT降2.3×，唯一在8×H20跑Kimi-K2 |
| 2026-07-14 | UCCL-Tran(OSDI'26) | 论文-系统 | OSDI '26, osdi26-zhou-yang.pdf | knowledge-synthesis | network/os-networking/ | RDMA软件传输层可扩展，UC multipath+control coalescing，collectives最高4.5×，训练+7.5% |
| 2026-07-14 | PowerSight(OSDI'26) | 论文-系统 | OSDI '26, osdi26-li-ruihao.pdf | knowledge-synthesis | operations/cloud-infrastructure/ | 硬件生命周期电源规划，RPB oversubscription ~20%，PowerSight ML预测跨架构MAPE 7.89% |
| 2026-07-14 | Kareus(OSDI'26) | 论文-系统 | OSDI '26, osdi26-wu-ruofan.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | 训练能耗联合优化，partitioned overlap+MBO，比Perseus再省28.3%能耗或减27.5%时间 |
| 2026-07-14 | SPADE(OSDI'26) | 论文-系统 | OSDI '26, osdi26-lechowicz.pdf | knowledge-synthesis | algorithms/resource-scheduling/ | 信号感知DAG调度+动态供给，相对重要性+指数阈值，碳排减少32.9% |
| 2026-07-14 | Quota Marketplace(OSDI'26) | 论文-系统 | OSDI '26, osdi26-sivan.pdf | knowledge-synthesis | algorithms/resource-scheduling/ | Google部署的ML芯片市场机制，非零和credits+动态定价，保证Pareto效率+max-min公平 |
| 2026-07-14 | Bodega(OSDI'26) | 论文-协议 | OSDI '26, osdi26-hu-guanzhou.pdf | knowledge-synthesis | algorithms/distributed-consensus/ | 首个任意节点任意时间本地线性化读，roster leases，读加速5.6-13.1× |
| 2026-07-14 | Pompē-SRO(OSDI'26) | 论文-协议 | OSDI '26, osdi26-zhang-yunhao.pdf | knowledge-synthesis | algorithms/distributed-consensus/ | 排序共识公平性，equal opportunity+SRO随机性，缓解front-running/sandwich攻击 |
| 2026-07-14 | Jetpack(OSDI'26) | 论文-协议/系统 | OSDI '26, osdi26-tang.pdf | knowledge-synthesis | algorithms/distributed-consensus/ | 通用共识1-RTT fast-path插件，view change hazard，6系统+TLA+验证，延迟降60% |
| 2026-07-14 | Ambulance(OSDI'26) | 论文-协议 | OSDI '26, osdi26-giridharan.pdf | knowledge-synthesis | algorithms/distributed-consensus/ | protocol-rigged racing替代timeout，BFT slowdown恢复快1.6-10.8×，3 msg delay正常延迟 |
| 2026-07-14 | SDCHUNTER(OSDI'26) | 论文-运维系统 | OSDI '26, osdi26-zheng.pdf | knowledge-synthesis | operations/monitoring-observability/ | GPU SDC诊断，分层确定重放，23块缺陷GPU特征化，40次事件，诊断从数天降至<1h |
| 2026-07-14 | AEGIS(OSDI'26) | 论文-运维系统 | OSDI '26, osdi26-lei.pdf | knowledge-synthesis | operations/monitoring-observability/ | 在线GPU SDC检测，cSensor-cVerifier解耦，35M GPU-h检测18次SDC/13块缺陷GPU，0.86%开销 |
| 2026-07-14 | OpGuard(OSDI'26) | 论文-运维/调试 | OSDI '26, osdi26-zhou-ziming.pdf | knowledge-synthesis | operations/monitoring-observability/ | bitwise alignment调试原语，跨异构栈算子边界+调度容忍匹配，20+生产问题，天→分钟 |
| 2026-07-14 | RobustRL(OSDI'26) | 论文-系统 | OSDI '26, osdi26-chen-zhenqian.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | RL后训练角色化容错，Detect-Restart-Reconnect，256GPU 10%故障ETTR>80% vs ByteRobust 60% |
| 2026-07-14 | Oxbow(OSDI'26) | 论文-系统 | OSDI '26, osdi26-kim-jongyul.pdf | knowledge-synthesis | performance/storage-filesystem/ | 协调式多组件FS，semi-kernel-bypass+shared-ownership metadata+split journaling |
| 2026-07-14 | DINGO(OSDI'26) | 论文-系统 | OSDI '26, osdi26-athlur.pdf | knowledge-synthesis | performance/storage-filesystem/ | 声明式IO，维护任务45-70% IO但可跨任务复用，IO-26-51%，支持1.7×更大HDD |
| 2026-07-14 | Umap(OSDI'26) | 论文-运维系统 | OSDI '26, osdi26-he-yongchao.pdf | knowledge-synthesis | performance/storage-filesystem/ | mmap-IO DFS矩阵访问优化，消除livelock+OOM，吞吐up to 6.7×，生产部署18+月 |
| 2026-07-14 | CoPilotIO(OSDI'26) | 论文-系统 | OSDI '26, osdi26-chen-guanyi.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | CPU co-pilot GPU I/O，split SQ/CQ+自适应co-polling，I/O stall -55.5%, 应用+85% |
| 2026-07-14 | BALBOA(OSDI'26) | 论文-系统 | OSDI '26, osdi26-heer.pdf | knowledge-synthesis | network/os-networking/ | 开源100G RoCEv2 FPGA卸载引擎，decoupled state+streaming separation，匹配ASIC性能 |
| 2026-07-14 | DPA-Store(OSDI'26) | 论文-系统 | OSDI '26, osdi26-schimmelpfennig.pdf | knowledge-synthesis | network/os-networking/ | BF3 DPA on-path KV store，learned index+lock-free，33M lookup/s, 13M range/s |
| 2026-07-14 | FARLock(OSDI'26) | 论文-协议 | OSDI '26, osdi26-hu-yuehao.pdf | knowledge-synthesis | algorithms/concurrent-data-structures/ | 公平RDMA非对称锁，ticket+MCS handover，FCFS公平+高性能 |
| 2026-07-14 | Sepia(OSDI'26) | 论文-系统 | OSDI '26, osdi26-song.pdf | knowledge-synthesis | network/os-networking/ | DDIO页着色优化，冲突缺失识别，有效LLC容量+77-94%，3.5核饱和200Gbps |
| 2026-07-14 | FlowANN(OSDI'26) | 论文-系统 | OSDI '26, osdi26-zhao.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | node-level dep解耦图搜索，单GPU十亿ANNS，比SOTA快4-46× |
| 2026-07-14 | POEGA(OSDI'26) | 论文-系统 | OSDI '26, osdi26-zhang-yunmo.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | GPU演化图分析，proxy graph+fused kernel+adaptive compaction，3.7-23.5× |
| 2026-07-14 | Pluto(OSDI'26) | 论文-系统 | OSDI '26, osdi26-wu-ying-wei.pdf | knowledge-synthesis | algorithms/graph-processing/ | 分布式图partial mirroring，mirror heterogeneity消除非生产性复制，vs full mirroring up to 3.8× |
| 2026-07-14 | Helmsman(OSDI'26) | 论文-运维系统 | OSDI '26, osdi26-huang-yuchen.pdf | knowledge-synthesis | performance/storage-filesystem/ | 聚类ANNS+SSD替代全DRAM HNSW，成本-90%，40台替代35K核+0.35PB DRAM |
| 2026-07-14 | WiseCode(OSDI'26) | 论文-系统 | OSDI '26, osdi26-cai.pdf | knowledge-synthesis | performance/storage-filesystem/ | 首个实用宽条带矢量码，template-unfold+rep-min系数搜索，修复吞吐vs UCLRCs 1.41-2.18× |
| 2026-07-14 | LogDrive(OSDI'26) | 论文-系统 | OSDI '26, osdi26-vickers.pdf | knowledge-synthesis | algorithms/distributed-consensus/ | 云存储共享日志耐久层，durability-sequencing分离，metadata成本vs DynamoDB -10× |
| 2026-07-14 | Timelock Drive(OSDI'26) | 论文-系统/安全 | OSDI '26, osdi26-rosenblum.pdf | knowledge-synthesis | security/os-security/ | 物理块级timelock防御，~400LoC形式验证checker+delegate-but-verify，TCB极小化 |
| 2026-07-14 | S3 MBT(OSDI'26) | 论文-运维系统 | OSDI '26, osdi26-jaber.pdf | knowledge-synthesis | operations/os-testing/ | AWS S3 model-based testing+谓词抽象，300+回归阻止，指导S3 Express One Zone开发 |
| 2026-07-14 | M3U(OSDI'26) | 论文-系统 | OSDI '26, osdi26-xu-yizhe.pdf | knowledge-synthesis | operations/cloud-infrastructure/ | VM后拷贝迁移MMU可扩展性，lock relaxation+预分配+解耦pipeline，downtime -47%, post-copy -89.6% |
| 2026-07-14 | InfiniDefrag(OSDI'26) | 论文-系统 | OSDI '26, osdi26-zeng.pdf | knowledge-synthesis | architecture/memory-storage-hierarchy/ | GPA无限空间+remap消除guest compaction，compaction-free碎片整理 |
| 2026-07-14 | GOODKIT(OSDI'26) | 论文-系统 | OSDI '26, osdi26-teguia.pdf | knowledge-synthesis | security/os-security/ | VM自省新范式，observer共享VMM+lock-aware一致性，比LibVMI快110×，target slowdown仅1.06× |
| 2026-07-14 | vBOIDs(OSDI'26) | 论文-系统 | OSDI '26, osdi26-manakkal.pdf | knowledge-synthesis | performance/system-tuning/ | 容器粗粒度BOID调度抽象，inter-core migration降一个数量级，吞吐up to 3× |
| 2026-07-14 | EcoServe(OSDI'26) | 论文-系统 | OSDI '26, osdi26-du.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | 商品GPU集群LLM serving，PaDG+macro instance+稀疏化KV传输，goodput提升1.96-2.51× |
| 2026-07-14 | PipeP(OSDI'26) | 论文-系统 | OSDI '26, osdi26-hwang.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | 重新评估PP for LLM serving，动态chunk+delay scheduling消除bubbles，PCIe GPU上超越TP |
| 2026-07-14 | OpenTela(OSDI'26) | 论文-运维系统 | OSDI '26, osdi26-yao.pdf | knowledge-synthesis | architecture/cloud-native/ | 联邦LLM serving overlay，CRDT gossip+统一API跨HPC集群，22月13M请求142模型 |
| 2026-07-14 | Kairox(OSDI'26) | 论文-系统 | OSDI '26, osdi26-jiang-yapeng.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | 在线neuron均衡GPU-CPU推理，live pipeline+TAM cache，vs llama.cpp 3.15-3.93× |
| 2026-07-14 | ADAngel(OSDI'26) | 论文-系统 | OSDI '26, osdi26-liu-yao.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | DPR模型自适应混合精度GEMM，oracle policy map+lightweight dispatch，decode vs llama.cpp 5.10× |
| 2026-07-14 | Twill(OSDI'26) | 论文-编译器/系统 | OSDI '26, osdi26-soi.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | SWP+WS约束优化求解，Twill自动推导最优调度，证明FlashAttention手工调度最优 |
| 2026-07-14 | TileLoom(OSDI'26) | 论文-编译器/系统 | OSDI '26, osdi26-li-wei.pdf | knowledge-synthesis | architecture/accelerators/ | spatial dataflow加速器tile编译，MLIR自动dataflow planning，匹配vendor库性能 |
| 2026-07-14 | MPK(OSDI'26) | 论文-编译器/系统 | OSDI '26, osdi26-cheng.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | mega-kernel编译器+运行时，SM级任务图+去中心化调度，推理延迟-1.7× |
| 2026-07-14 | GraCE(OSDI'26) | 论文-编译器/系统 | OSDI '26, osdi26-ghosh.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | CUDA Graph编译器使能，auto code transform+indirect params，Graph收益2×于PyTorch2 |
| 2026-07-14 | VTC(OSDI'26) | 论文-编译器 | OSDI '26, osdi26-hu-muyan.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | virtual tensor+index mapping消除数据移动，vs现有编译器1.93×, 内存-60% |
| 2026-07-14 | Quark(OSDI'26) | 论文-运维系统 | OSDI '26, osdi26-chai.pdf | knowledge-synthesis | operations/cloud-infrastructure/ | 混布batch serverless化，消除4种闲置，有效利用率33%→100%，节省>10万核 |
| 2026-07-14 | Arca(OSDI'26) | 论文-OS设计 | OSDI '26, osdi26-srivatsan.pdf | knowledge-synthesis | architecture/cloud-native/ | continuation作为OS原语，2.55µs快照/恢复，serverless 50-60×加速 |
| 2026-07-14 | Spice(OSDI'26) | 论文-OS/系统 | OSDI '26, osdi26-holmes.pdf | knowledge-synthesis | architecture/cloud-native/ | SHELF+spliceVMA解耦物理-虚拟布局，冷启动0.6-18ms vs 3.6-1197ms，延迟7.5×改善 |
| 2026-07-14 | libDSE(OSDI'26) | 论文-系统 | OSDI '26, osdi26-li-tianyu.pdf | knowledge-synthesis | architecture/cloud-native/ | 分布式推测执行，durable execution抽象-物理解耦，延迟up to 10×改善 |
| 2026-07-14 | TrainMover(OSDI'26) | 论文-系统 | OSDI '26, osdi26-lao.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | 训练中断恢复~20s/1024GPU，delta通信重建+sandbox warmup+通用standby，GPU浪费-55% |
| 2026-07-15 | Nixie(OSDI'26) | 论文-系统 | OSDI '26, osdi26-xu-yechen.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | 消费者GPU时间复用，explicit swap替代UVM thrashing，MLFQ调度优先交互，延迟降3.8× |
| 2026-07-15 | μShell(OSDI'26) | 论文-系统/架构 | OSDI '26, osdi26-chen-jiyang.pdf | knowledge-synthesis | architecture/accelerators/ | microkernel FPGA shell，硬件IPC+capability隔离+组件感知调度，可组合加速器 |
| 2026-07-15 | vBPF(OSDI'26) | 论文-系统/安全 | OSDI '26, osdi26-zhang-jing.pdf | knowledge-synthesis | security/os-security/ | eBPF late-binding虚拟化，Sniffer+Dispatcher O(1)+编译隔离，多租户延迟降3.9× |
| 2026-07-15 | DVLA(OSDI'26) | 论文-运维系统 | OSDI '26, osdi26-zhang-zhengtong.pdf | knowledge-synthesis | operations/cloud-infrastructure/ | VM lifetime感知调度，placement debt+动态affinity+离线整流，Alibaba节省数千台 |
| 2026-07-15 | PIMS(OSDI'26) | 论文-运维系统 | OSDI '26, osdi26-leonhardi.pdf | knowledge-synthesis | operations/cloud-infrastructure/ | Meta五年维护系统，fault domain alignment+maintenance contract，buffer降15%，可预测SLO |
| 2026-07-15 | ASI-Heterogeneity(OSDI'26) | 论文-运维系统 | OSDI '26, osdi26-li-suyi.pdf | knowledge-synthesis | operations/cloud-infrastructure/ | Alibaba异构GPU集群trace分析，155K GPU，defrag+SpotGPU分配率68%→93% |
| 2026-07-15 | Mimesys(OSDI'26) | 论文-系统/测试 | OSDI '26, osdi26-kim-donghyun.pdf | knowledge-synthesis | operations/os-testing/ | 扩散模型trace→可执行workload合成，state-aware conditioning+execution alignment，相似度5.5× |
| 2026-07-15 | Merlin(OSDI'26) | 论文-算法/系统 | OSDI '26, osdi26-li-liujia.pdf | knowledge-synthesis | algorithms/cache-algorithms/ | 自适应缓存淘汰，per-object特征化解耦组件，5423 traces，吞吐1.4-7.8× |
| 2026-07-15 | S4-FIFO/LAH(OSDI'26) | 论文-算法/系统 | OSDI '26, osdi26-xia.pdf | knowledge-synthesis | algorithms/cache-algorithms/ | LAH解耦数据-控制面，cache级学习增强S3-FIFO，效率+26%，最差trace仅+0.8% |
| 2026-07-15 | WriteGuards(OSDI'26) | 论文-系统 | OSDI '26, osdi26-mao-ziming-writeguards.pdf | knowledge-synthesis | algorithms/distributed-consensus/ | key-range fencing解决delayed-writes，分布式强一致性缓存，read tail延迟降1000× |
| 2026-07-15 | Megalon(OSDI'26) | 论文-系统 | OSDI '26, osdi26-hu-jiyu.pdf | knowledge-synthesis | architecture/memory-storage-hierarchy/ | CXL部分一致性split metadata共享，large-LNR+small-SCR，vs Tigon支持更大数据集 |
| 2026-07-15 | Sereno(OSDI'26) | 论文-系统 | OSDI '26, osdi26-xin.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | 移动LLM推理NPU带宽不对称干扰，specDec yield+抢占式让出带宽，jank-92.6% |
| 2026-07-15 | LifeLine(OSDI'26) | 论文-系统 | OSDI '26, osdi26-huang-jiacheng.pdf | knowledge-synthesis | performance/system-tuning/ | 对象-页生存期对齐GC，bimodal liveness+page remapping替代copy，GC copy-57.4%, GC time-22.7% |
| 2026-07-15 | SANI(OSDI'26) | 论文-系统 | OSDI '26, osdi26-sang.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | AMP CPU不对称感知DNN推理，adaptive granularity+core-kernel affinity，延迟-17.6-23.7% |
| 2026-07-15 | MUSCHED(OSDI'26) | 论文-运维系统 | OSDI '26, osdi26-xiao.pdf | knowledge-synthesis | performance/system-tuning/ | Honor语义感知CPU调度，VIP类+IPC依赖链跟踪+eBPF可插拔策略，20M+设备部署 |
| 2026-07-15 | qTPU(OSDI'26) | 论文-系统/加速器 | OSDI '26, osdi26-tornow.pdf | knowledge-synthesis | architecture/accelerators/ | 混合量子-经典张量网络，hTN统一抽象+编译器平衡cost vs error，端到端20×加速 |
| 2026-07-15 | Acumen(OSDI'26) | 论文-系统/安全 | OSDI '26, osdi26-cottone.pdf | knowledge-synthesis | security/os-security/ | 加密协作编辑，密码学累加器+secure GC，首个snapshot consistency+edit-history隐私 |
| 2026-07-15 | Drs.NAS(OSDI'26) | 论文-系统/ML | OSDI '26, osdi26-wang-ruixuan.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | 推荐系统NAS，superproxy度量替代训练验证，搜索5-18GPU-h→2min CPU，模型108×更小 |
| 2026-07-15 | Svalinn(OSDI'26) | 论文-系统 | OSDI '26, osdi26-pardeshi.pdf | knowledge-synthesis | operations/cloud-infrastructure/ | 多资源瓶颈过载控制，credit admission+per-resource AQM+m_semaphore，goodput up to 6.51× |
| 2026-07-15 | PeeR(OSDI'26) | 论文-系统 | OSDI '26, osdi26-carin.pdf | knowledge-synthesis | performance/system-tuning/ | eBPF可抢占调度，verifier helper call抢占点+hybrid softirq-kthread+sched_ext，p99降3-19.8× |
| 2026-07-15 | TypeCraft(OSDI'26) | 论文-系统/性能工具 | OSDI '26, osdi26-li-zecheng.pdf | knowledge-synthesis | operations/monitoring-observability/ | 类型感知perf，DWARF→mem指令标注type+field，Linux内核优化，已上游化perf |
| 2026-07-15 | DiTing(OSDI'26) | 论文-运维系统 | OSDI '26, osdi26-ren.pdf | knowledge-synthesis | operations/monitoring-observability/ | 统一可观测性，logs-metrics-traces统一+harvest闲置资源，CapEx低65×，Alibaba生产部署 |
| 2026-07-15 | jwmalloc(OSDI'26) | 论文-系统 | OSDI '26, osdi26-wang-jiawei.pdf | knowledge-synthesis | performance/system-tuning/ | 形式验证移动内存分配器，weak memory bounded MC，替换jemalloc CPU-10%，300亿用户时 |
| 2026-07-15 | NeuroSym-Prover(OSDI'26) | 论文-验证/AI | OSDI '26, osdi26-he-baoding.pdf | knowledge-synthesis | security/os-security/ | 神经-符号proof生成，best-first search+LLM+ITP修复，seL4证明77.6%定理 |
| 2026-07-15 | Spain(OSDI'26) | 论文-安全/密码学 | OSDI '26, osdi26-destefano.pdf | knowledge-synthesis | security/os-security/ | 数值succinct proofs，近似约束+新协议，prover overhead <1000× first for numerical |
| 2026-07-15 | RT(OSDI'26) | 论文-编程语言/系统 | OSDI '26, osdi26-li-zekai.pdf | knowledge-synthesis | operations/program-analysis/ | Shell管道静态类型检查，regular types+FST，多项式时间TC，91%精度，0.02s avg |
| 2026-07-15 | LithOS(SOSP'25) | 论文-系统/GPU OS | SOSP '25, DOI:10.1145/3731569.3764818 | knowledge-synthesis | performance/gpu-ai-performance/ | 首个GPU OS，TPC级调度+kernel原子化+hardware right-sizing+DVFS，13×尾延迟下降vs MPS，25%节能 |
| 2026-07-15 | μFork(SOSP'25) | 论文-系统/OS安全 | SOSP '25, DOI:10.1145/3731569.3764809 | knowledge-synthesis | security/os-security/ | 单地址空间OS fork，CHERI能力+CoPA延迟重定位，54μs fork(3.7× faster)，24%更高FaaS吞吐 |
| 2026-07-16 | Latte(FAST'26) | 论文-系统（工业经验） | FAST '26, fast26-yang.pdf | knowledge-synthesis | performance/storage-filesystem/, architecture/cloud-native/ | 阿里云三代本地存储演进（Espresso→Doppio→Ristretto）+ 本地-云盘混合 Latte，ML I/O dispatch 实现近物理性能+高可用+1/5-1/10 EBSX 成本 |
| 2026-07-16 | TapeOBS(FAST'26) | 论文-系统（工业部署） | FAST '26, fast26-wang.pdf | knowledge-synthesis | performance/storage-filesystem/, architecture/cloud-native/ | 华为云磁带归档存储，全异步磁带池+HDD缓冲+批量EC+专用驱动器+生存期分组写入+TCO 4.95× 低于 HDD |
| 2026-07-16 | RubikFS(FAST'26) | 论文-系统 | FAST '26, fast26-huang.pdf | knowledge-synthesis | performance/storage-filesystem/ | 排序增强压缩只读FS，相似度图+子图分割聚类+hotness分组，压缩比+42.60%，读放大-70.70% |
| 2026-07-16 | ACOS(FAST'26) | 论文-系统（工业部署） | FAST '26, fast26-baron-updated.pdf | knowledge-synthesis | architecture/cloud-native/, performance/storage-filesystem/ | Apple EB 级跨地域对象存储，两代演进，XOR-5 parity+LRC 将 RF 从 2.40 降至 1.50，十年生产部署 |
| 2026-07-16 | SolidAttention(FAST'26) | 论文-系统 | FAST '26, fast26-zheng.pdf | knowledge-synthesis | performance/gpu-ai-performance/, performance/storage-filesystem/ | 本地低并发 SSD-based LLM 推理，KV 交织+推测预取+SSD 感知调度，加速 3.1×，KV 内存 -98% |
| 2026-07-16 | CacheSlide(FAST'26) | 论文-系统 | FAST '26, fast26-liu-yang.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | Agent KV cache 复用，RPDC 范式+CoPE 位置编码+加权校正注意力+SLIDE 脏页感知淘汰，延迟 -3.11-4.3×，吞吐 +3.5-5.8× |
| 2026-07-16 | Bidaw(FAST'26) | 论文-系统 | FAST '26, fast26-hu-shipeng.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | 交互式对话 LLM serving 双向感知 KV cache，I/O 感知调度+回答长度淘汰+存储高效张量，延迟 -3.58×，吞吐 +1.83× |
| 2026-07-16 | PPC+MAIO(FAST'26) | 论文-系统 | FAST '26, fast26-liu-yubo.pdf | knowledge-synthesis | performance/gpu-ai-performance/, operations/os-performance-tuning/ | 华为可编程页缓存框架+模型加载加速，I/O 模板+可中断预取+XPU 亲和+BAR 淘汰，加载延迟 -79%，推理启动吞吐 +36% |
| 2026-07-16 | OdinANN(FAST'26) | 论文-系统 | FAST '26, fast26-guo.pdf | knowledge-synthesis | performance/storage-filesystem/ | 十亿级图-based ANNS direct insert，GC-free overprovision+近似并发控制+delta pruning，搜索延迟波动仅 1.07×，内存 -~70% |
| 2026-07-16 | DMTree(FAST'26) | 论文-系统 | FAST '26, fast26-wei.pdf | knowledge-synthesis | architecture/memory-storage-hierarchy/ | DM 树索引计算侧协同设计，fingerprint+locks 卸载到 CS 间 RDMA，搜索/插入/扫描吞吐最高 5.7× SOTA |
| 2026-07-16 | CloudTS(FAST'26) | 论文-系统 | FAST '26, fast26-zhang-kai.pdf | knowledge-synthesis | operations/monitoring-observability/ | 云原生时序存储模型，metadata-data分离+Patricia Trie tag字典+CSR bitmap时序-tag映射，消除读放大，1.43× Cortex |
| 2026-07-16 | RASK(FAST'26) | 论文-系统 | FAST '26, fast26-zhao.pdf | knowledge-synthesis | performance/storage-filesystem/ | 云块存储 range-as-a-key 树索引，log-structured leaf+ablation search+two-stage GC, 内存 -98.9%, 吞吐 +31.0× |
| 2026-07-16 | HATS(FAST'26) | 论文-系统 | FAST '26, fast26-ren.pdf | knowledge-synthesis | operations/cloud-infrastructure/, algorithms/resource-scheduling/ | 分布式 LSM-tree KV 协同调度，粗/细粒度副本选择+压缩速率控制+replica decoupling, P99 -58.6%, 吞吐 +2.41× |
| 2026-07-16 | Seneca(FAST'26) | 论文-系统 | FAST '26, fast26-desai.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | ML 训练 DSI pipeline 缓存分区+机会主义采样，makespan -45%, 吞吐 3.45× |
| 2026-07-16 | GCR(FAST'26) | 论文-系统 | FAST '26, fast26-zeng.pdf | knowledge-synthesis | performance/gpu-ai-performance/ | GPU 系统级 C/R，hybrid control/data 分离+dirty template 增量 ckpt，ckpt -72%, restore -87%, 开销 <1% |
<!-- 追加新记录时，复制上面一行并修改即可。 -->
