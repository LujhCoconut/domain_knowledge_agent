#!/usr/bin/env python3
"""Auto-generate the README.md stats block from metadata.json.

Reads metadata.json, counts papers by conference/domain, and replaces the
section between the auto-update markers in README.md.

Usage:
    python3 scripts/generate_readme_stats.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
METADATA_PATH = _REPO / "history" / "metadata.json"
README_PATH = _REPO / "README.md"

# Domain label mapping: knowledge_locations path → human-readable Chinese label
DOMAIN_LABELS: dict[str, str] = {
    "performance/system-tuning/": "CXL/内存系统/stall 回收",
    "architecture/memory-storage-hierarchy/": "存储层次/体系结构",
    "operations/cloud-infrastructure/": "云基础设施/虚拟化",
    "architecture/cloud-native/": "云原生/解耦式服务",
    "performance/gpu-ai-performance/": "LLM 推理/GPU-AI/训练",
    "architecture/agent-native-design/": "Agent-Native 软件设计",
    "security/os-security/": "OS 安全/隐私/程序分析",
    "operations/os-testing/": "软件测试/DBMS/云服务",
    "operations/os-performance-tuning/": "OS 内核/调优",
    "operations/monitoring-observability/": "监控/可观测性",
    "performance/storage-filesystem/": "存储/文件系统",
    "operations/program-analysis/": "程序分析与动态优化",
    "algorithms/concurrent-data-structures/": "并发数据结构",
    "algorithms/resource-scheduling/": "资源调度与供给",
    "algorithms/distributed-consensus/": "分布式共识",
    "algorithms/graph-processing/": "图处理",
    "algorithms/cache-algorithms/": "缓存算法",
    "architecture/accelerators/": "加速器架构与编译",
    "network/os-networking/": "网络系统",
}

# Domain-specific KNOWLEDGE.md links
DOMAIN_LINKS: dict[str, str] = {
    "CXL/内存系统/stall 回收": "`performance/system-tuning/KNOWLEDGE.md`",
    "存储层次/体系结构": "`architecture/memory-storage-hierarchy/KNOWLEDGE.md`",
    "云基础设施/虚拟化": "`operations/cloud-infrastructure/KNOWLEDGE.md`",
    "云原生/解耦式服务": "`architecture/cloud-native/KNOWLEDGE.md`",
    "LLM 推理/GPU-AI/训练": "`performance/gpu-ai-performance/KNOWLEDGE.md`",
    "Agent-Native 软件设计": "`architecture/agent-native-design/KNOWLEDGE.md`",
    "OS 安全/隐私/程序分析": "`security/os-security/KNOWLEDGE.md`",
    "软件测试/DBMS/云服务": "`operations/os-testing/KNOWLEDGE.md`",
    "OS 内核/调优": "`operations/os-performance-tuning/KNOWLEDGE.md`",
    "监控/可观测性": "`operations/monitoring-observability/KNOWLEDGE.md`",
    "存储/文件系统": "`performance/storage-filesystem/KNOWLEDGE.md`",
    "程序分析与动态优化": "`operations/program-analysis/KNOWLEDGE.md`",
    "并发数据结构": "`algorithms/concurrent-data-structures/KNOWLEDGE.md`",
    "资源调度与供给": "`algorithms/resource-scheduling/KNOWLEDGE.md`",
    "分布式共识": "`algorithms/distributed-consensus/KNOWLEDGE.md`",
    "图处理": "`algorithms/graph-processing/KNOWLEDGE.md`",
    "缓存算法": "`algorithms/cache-algorithms/KNOWLEDGE.md`",
    "加速器架构与编译": "`architecture/accelerators/KNOWLEDGE.md`",
    "网络系统": "`network/os-networking/KNOWLEDGE.md`",
}


def generate_stats_block() -> str:
    """Return the markdown stats block to inject into README.md."""
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    papers = data.get("papers", [])
    total = len(papers)

    # Conference distribution
    conf_years: dict[str, list[int]] = defaultdict(list)
    for p in papers:
        y = p.get("year")
        c = p.get("conference", "Unknown")
        if y:
            conf_years[c].append(y)

    conf_lines: list[str] = []
    for conf in sorted(conf_years, key=lambda c: -len(conf_years[c])):
        years = sorted(set(conf_years[conf]))
        count = len(conf_years[conf])
        y_range = f"'{str(years[0])[-2:]}" if len(years) == 1 else f"'{str(years[0])[-2:]}–'{str(years[-1])[-2:]}"
        conf_lines.append(f"{conf} {count} 篇（{y_range}）")

    # Domain distribution
    domain_papers: dict[str, list[str]] = defaultdict(list)
    # Track which domains have had representative entries shown
    # so we avoid listing all papers, just a few representatives
    for p in papers:
        locs = p.get("knowledge_locations", [])
        cn = p.get("canonical_name", "?")
        primary = locs[0] if locs else None
        label = DOMAIN_LABELS.get(primary, "") if primary else ""
        if label:
            domain_papers[label].append(cn)

    domain_lines: list[str] = []
    for label in sorted(domain_papers, key=lambda d: -len(domain_papers[d])):
        papers_in_domain = domain_papers[label]
        count = len(papers_in_domain)
        link = DOMAIN_LINKS.get(label, "")
        # Show first 3 representative entries
        sample = papers_in_domain[:3]
        sample_str = "、".join(sample)
        suffix = "…" if len(papers_in_domain) > 3 else ""
        if link:
            domain_lines.append(
                f"  - {label}: {count} 篇（{sample_str}{suffix}） — 见 {link}"
            )
        else:
            domain_lines.append(
                f"  - {label}: {count} 篇（{sample_str}{suffix}）"
            )

    today = date.today().isoformat()

    return f"""- **总计**: {total} 篇
- **会议分布**: {'，'.join(conf_lines)}
- **领域分布**:
{chr(10).join(domain_lines)}
- **🚀 新增功能**: JSON 结构化元数据 (`history/metadata.json`) + 技术倒排索引 + 四轮递进阅读 (R1-R4) + 工业可用性评分 + DBLP 自动元数据补全 + BibTeX 收集导出
- **最后更新**: {today}"""


def update_readme() -> bool:
    """Replace the stats block in README.md. Returns True if successful."""
    if not README_PATH.exists():
        print(f"ERROR: {README_PATH} not found", file=sys.stderr)
        return False

    text = README_PATH.read_text(encoding="utf-8")

    # Markers
    start_marker = "<!-- 以下区域由 /domain-knowledge 后置操作自动更新，请勿手动编辑本节 -->"
    end_marker = "<!-- 自动更新区域结束 -->"

    start_idx = text.find(start_marker)
    end_idx = text.find(end_marker)

    if start_idx == -1 or end_idx == -1:
        print("ERROR: Could not find auto-update markers in README.md", file=sys.stderr)
        return False

    new_block = generate_stats_block()

    # Replace content between markers (markers stay)
    new_text = (
        text[: start_idx + len(start_marker)]
        + "\n\n"
        + new_block
        + "\n\n"
        + text[end_idx:]
    )

    README_PATH.write_text(new_text, encoding="utf-8")
    print(f"Updated stats in {README_PATH}")
    print(f"  Total papers: {len(json.loads(METADATA_PATH.read_text(encoding='utf-8')).get('papers', []))}")
    return True


def main() -> None:
    success = update_readme()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
