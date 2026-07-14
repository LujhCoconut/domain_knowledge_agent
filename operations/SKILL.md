# Operations & SRE

运维与站点可靠性工程相关技能。

## 子目录

| 目录 | 主题 | 适合归档的内容 |
|------|------|----------------|
| `linux-system-admin/` | Linux 系统管理 | 文件系统、进程、systemd、权限、内核参数、常用命令行技巧 |
| `os-testing/` | OS 内核测试与调试 | 调度器测试、确定性重放、coverage-guided fuzzing、静默 bug 表征 |
| `os-performance-tuning/` | OS 性能调优 | 内核常量在线调优 (perf-const)、Scoped Indirect Execution、side-effect safety |
| `monitoring-observability/` | 监控与可观测性 | Metrics/Logs/Traces、Prometheus/Grafana、告警规则、日志聚合、网络 RCA、根因分析 |
| `container-k8s/` | 容器与 Kubernetes | Docker、K8s 资源对象、调度、网络、存储、排错 |
| `ci-cd-devops/` | CI/CD 与 DevOps | GitHub Actions、GitLab CI、制品管理、发布策略、IaC |
| `storage-infrastructure/` | 存储基础设施与数据管线 | HDFS、大规模数据供给、checkpoint 管理、跨 DC 数据复制、训练数据预处理 |
| `incident-response/` | 故障响应 | On-call、故障定位流程、复盘模板、应急止血 |
| `cloud-infrastructure/` | 云基础设施与虚拟化 | 超卖、CPU idle 管理、mwait/vCPU 调度、VM exit 优化、SLO 保障、内核在线调优 |
| `sre-practices/` | SRE 实践 | SLI/SLO/SLA、容量规划、混沌工程、变更管理 |

## 新增 skill 建议

- 按“系统/工具 + 场景”命名，例如 `nginx-troubleshooting`、`kafka-ops`。
- 每个 skill 应包含可执行命令或检查清单，避免纯理论堆砌。
