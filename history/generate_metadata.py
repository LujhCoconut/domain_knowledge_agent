#!/usr/bin/env python3
"""Parse reading-log.md and generate history/metadata.json with all paper entries."""
import json
import re
import sys
from datetime import date
from pathlib import Path

BASE = Path("/Users/coconut/.claude/skills/domain-knowledge")
LOG_PATH = BASE / "history" / "reading-log.md"
OUT_PATH = BASE / "history" / "metadata.json"

def parse_reading_log():
    """Parse reading-log.md table rows into structured paper entries."""
    text = LOG_PATH.read_text()
    papers = []

    # Match table rows: | date | title | type | source | skill | locations | notes |
    # Skip header and separator rows
    in_table = False
    for line in text.split('\n'):
        line = line.strip()
        if not line.startswith('|'):
            continue
        # Skip header and separator
        if '资料标题' in line or line.startswith('|------'):
            in_table = True
            continue
        if not in_table:
            continue
        if '追加新记录' in line or '<!--' in line:
            continue

        parts = [p.strip() for p in line.split('|')[1:-1]]  # strip leading/trailing |
        if len(parts) < 7:
            continue

        date_str, canonical_name, ptype, source, skill, locations, notes = parts[:7]

        # Parse canonical name: 方案名(会议'年份)
        # e.g., "PithTrain(arXiv'26)" -> name="PithTrain", conference="arXiv", year=2026
        match = re.match(r'(.+?)\((.+?)\'(\d{2,4})\)', canonical_name)
        if not match:
            # Try without year: "方案名(会议)"
            match = re.match(r'(.+?)\((.+?)\)', canonical_name)

        scheme_name = ""
        conference = ""
        year = 0
        if match:
            scheme_name = match.group(1)
            conf_year = match.group(2)
            if len(match.groups()) >= 3:
                year_str = match.group(3)
                year = 2000 + int(year_str) if len(year_str) == 2 else int(year_str)
            # Extract conference from conf_year: "OSDI'26" -> "OSDI"
            conf_match = re.match(r'([A-Za-z]+)', conf_year)
            if conf_match:
                conference = conf_match.group(1)
            else:
                conference = conf_year

        # Parse date
        try:
            year_val, month_val, day_val = map(int, date_str.split('-'))
        except:
            year_val, month_val, day_val = 2026, 7, 1

        # Extract tags from notes and locations
        tags = extract_tags(canonical_name, notes, locations, source)

        # Determine industrial_applicability from notes
        ind_app, ind_why = guess_applicability(notes, locations, conference)

        # Parse knowledge locations
        loc_list = [l.strip() for l in locations.split(',') if l.strip()]

        paper = {
            "canonical_name": canonical_name,
            "title": "",
            "authors": [],
            "conference": conference,
            "year": year,
            "url": extract_url(source),
            "date_read": date_str,
            "type": ptype,
            "tags": tags,
            "techniques": [],
            "builds_on": [],
            "contrasts_with": [],
            "industrial_applicability": ind_app,
            "applicability_why": ind_why,
            "prerequisites": "",
            "knowledge_locations": loc_list,
            "review_rounds": {
                "r1_tldr": notes,
                "r2_insights": "",
                "r3_relations": "",
                "r4_refute": ""
            }
        }
        papers.append(paper)

    return papers

def extract_url(source):
    """Extract URL or DOI from source field."""
    if 'arxiv.org' in source:
        match = re.search(r'arXiv[:.\s]*(\d+\.\d+)', source, re.IGNORECASE)
        if match:
            return f"https://arxiv.org/abs/{match.group(1)}"
    if 'http' in source:
        match = re.search(r'(https?://\S+)', source)
        if match:
            return match.group(1)
    return source

def extract_tags(name, notes, locations, source):
    """Extract keyword tags from notes, locations, and canonical name."""
    tags = set()
    notes_lower = notes.lower()

    # Domain tags from locations
    loc_map = {
        'performance/system-tuning': 'memory tiering',
        'performance/gpu-ai-performance': 'GPU',
        'performance/storage-filesystem': 'storage',
        'architecture/cloud-native': 'cloud-native',
        'architecture/memory-storage-hierarchy': 'memory hierarchy',
        'architecture/agent-native-design': 'agent-native design',
        'architecture/accelerators': 'accelerators',
        'network/os-networking': 'networking',
        'security/os-security': 'OS security',
        'operations/cloud-infrastructure': 'cloud infrastructure',
        'operations/monitoring-observability': 'observability',
        'operations/os-performance-tuning': 'kernel tuning',
        'operations/os-testing': 'testing',
        'operations/program-analysis': 'program analysis',
        'algorithms/concurrent-data-structures': 'concurrency',
        'algorithms/distributed-consensus': 'distributed consensus',
        'algorithms/resource-scheduling': 'scheduling',
        'algorithms/cache-algorithms': 'caching',
        'algorithms/graph-processing': 'graph processing',
    }
    for loc, tag in loc_map.items():
        if loc in locations:
            tags.add(tag)

    # Content tags from notes
    keyword_map = [
        ('MoE', 'MoE'),
        ('CXL', 'CXL'),
        ('KV cache', 'KV cache'),
        ('LLM', 'LLM'),
        ('推理', 'inference'),
        ('训练', 'training'),
        ('offloading', 'offloading'),
        ('GPU', 'GPU'),
        ('FP8', 'FP8'),
        ('RDMA', 'RDMA'),
        ('DPU', 'DPU'),
        ('RDMA|NIC', 'RDMA'),
        ('SSD', 'SSD'),
        ('NVMe', 'NVMe'),
        ('内存', 'memory'),
        ('eBPF', 'eBPF'),
        ('内核', 'kernel'),
        ('pipeline', 'pipeline parallelism'),
        ('调度', 'scheduling'),
        ('RL', 'reinforcement learning'),
        ('agent', 'agent'),
        ('量化', 'quantization'),
        ('编译器', 'compiler'),
        ('文件系统', 'filesystem'),
        ('Kubernetes|k8s', 'Kubernetes'),
        ('SGLang|vLLM', 'LLM serving'),
        ('DeepSeek', 'DeepSeek'),
        ('VM', 'virtualization'),
        ('安全|sandbox|isolate', 'security'),
        ('共识|consensus', 'consensus'),
        ('swap', 'swap'),
        ('移动|mobile', 'mobile'),
        ('加密|crypto', 'cryptography'),
        ('容器|container', 'containers'),
        ('生产部署|production|生产', 'production'),
    ]
    for pattern, tag in keyword_map:
        if re.search(pattern, notes_lower) or re.search(pattern, name, re.IGNORECASE):
            tags.add(tag)

    # Always add conference tag
    if 'OSDI' in source:
        tags.add('OSDI')
    elif 'ASPLOS' in source:
        tags.add('ASPLOS')
    elif 'FAST' in source:
        tags.add('FAST')
    elif 'SOSP' in source:
        tags.add('SOSP')

    return sorted(list(tags))

def guess_applicability(notes, locations, conference):
    """Guess industrial applicability from notes and locations."""
    notes_lower = notes.lower()

    # High indicators
    high_patterns = [
        '生产部署', 'production', '已上游化', 'upstream', '集成.*SGLang',
        '集成.*vLLM', '阿里.*生产', 'Azure', 'AWS', 'Google', 'Meta',
        '20M\+.*部署', '10K\+.*GPU.*生产', 'Alibaba.*生产'
    ]
    for p in high_patterns:
        if re.search(p, notes_lower):
            return "high", "已在生产环境中验证部署"

    # Low indicators
    low_patterns = [
        '需要.*定制.*硬件', 'CXL.*仿真', '仿真器', 'simulator',
        '纯理论', '形式验证', 'formal', '需要.*特殊.*硬件',
        'CXL.*控制器', 'FPGA', 'RDMA.*NIC.*卸载', 'CHERI'
    ]
    for p in low_patterns:
        if re.search(p, notes_lower):
            return "low", "需要特殊硬件或为理论/仿真工具"

    # Medium by default
    if '开源' in notes_lower or 'open.source' in notes_lower or 'github' in notes_lower:
        return "medium", "有开源代码但需要适配"

    return "medium", "核心思想可复用但需根据场景适配"

def build_indices(papers):
    """Build technique and tag inverted indices."""
    tech_idx = {}
    tag_idx = {}
    for p in papers:
        name = p['canonical_name']
        for t in p.get('techniques', []):
            tech_idx.setdefault(t, []).append(name)
        for t in p.get('tags', []):
            tag_idx.setdefault(t, []).append(name)
    return {
        "technique_index": tech_idx,
        "tag_index": tag_idx
    }

def main():
    papers = parse_reading_log()

    # Build indices
    indices = build_indices(papers)

    # Assemble final structure
    metadata = {
        "$schema": "metadata.schema.json",
        "generated_at": str(date.today()),
        "total_papers": len(papers),
        "papers": papers,
        **indices
    }

    # Write output
    OUT_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    print(f"Generated {OUT_PATH} with {len(papers)} papers")
    print(f"Technique index: {len(indices['technique_index'])} entries")
    print(f"Tag index: {len(indices['tag_index'])} entries")

    # Stats
    confs = {}
    for p in papers:
        c = p['conference']
        confs[c] = confs.get(c, 0) + 1
    print(f"Conference distribution: {confs}")

    ind_stats = {'high': 0, 'medium': 0, 'low': 0}
    for p in papers:
        ind_stats[p['industrial_applicability']] += 1
    print(f"Industrial applicability: {ind_stats}")

if __name__ == '__main__':
    main()
