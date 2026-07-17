#!/usr/bin/env python3
"""Rebuild technique_index and tag_index in metadata.json from papers[].techniques and papers[].tags."""
import json
from pathlib import Path
from datetime import date

METADATA_PATH = Path(__file__).parent / "metadata.json"

def rebuild():
    data = json.loads(METADATA_PATH.read_text())
    papers = data.get("papers", [])

    tech_idx = {}
    tag_idx = {}
    for p in papers:
        name = p["canonical_name"]
        for t in p.get("techniques", []):
            tech_idx.setdefault(t, []).append(name)
        for t in p.get("tags", []):
            tag_idx.setdefault(t, []).append(name)

    # Sort all arrays for determinism
    for k in tech_idx:
        tech_idx[k] = sorted(set(tech_idx[k]))
    for k in tag_idx:
        tag_idx[k] = sorted(set(tag_idx[k]))

    data["technique_index"] = tech_idx
    data["tag_index"] = tag_idx
    data["generated_at"] = str(date.today())
    data["total_papers"] = len(papers)

    METADATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"Rebuilt indices: {len(tech_idx)} techniques, {len(tag_idx)} tags, {len(papers)} papers")

if __name__ == "__main__":
    rebuild()
