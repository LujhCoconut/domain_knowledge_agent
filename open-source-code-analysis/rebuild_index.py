#!/usr/bin/env python3
"""Rebuild technique_index and tag_index for open-source-code-analysis knowledge base."""
import json
from pathlib import Path
from datetime import date

METADATA_PATH = Path(__file__).parent / "metadata.json"

def rebuild():
    data = json.loads(METADATA_PATH.read_text())
    entries = data.get("entries", [])

    tech_idx = {}
    tag_idx = {}
    project_idx = {}

    for e in entries:
        name = e["name"]
        for t in e.get("techniques", []):
            tech_idx.setdefault(t, []).append(name)
        for t in e.get("tags", []):
            tag_idx.setdefault(t, []).append(name)
        proj = e["project"]
        project_idx.setdefault(proj, []).append(name)

    for k in tech_idx:
        tech_idx[k] = sorted(set(tech_idx[k]))
    for k in tag_idx:
        tag_idx[k] = sorted(set(tag_idx[k]))
    for k in project_idx:
        project_idx[k] = sorted(set(project_idx[k]))

    data["technique_index"] = tech_idx
    data["tag_index"] = tag_idx
    data["project_index"] = project_idx
    data["generated_at"] = str(date.today())
    data["total_entries"] = len(entries)

    METADATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"Rebuilt indices: {len(tech_idx)} techniques, {len(tag_idx)} tags, "
          f"{len(project_idx)} projects, {len(entries)} entries")

if __name__ == "__main__":
    rebuild()
