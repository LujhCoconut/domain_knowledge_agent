#!/usr/bin/env python3
"""Backfill empty title/authors in metadata.json via DBLP — resumable, batched.

Usage:
    python3 scripts/backfill_metadata.py              # full run
    python3 scripts/backfill_metadata.py --resume     # resume from last saved state
    python3 scripts/backfill_metadata.py --dry-run    # preview only

Saves progress to history/_backfill_progress.json every 5 entries.
Runs are idempotent — already-filled entries are skipped.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from datetime import date
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "common" / "knowledge-synthesis"))

import dblp_lookup  # noqa: E402

METADATA_PATH = _REPO / "history" / "metadata.json"
PROGRESS_PATH = _REPO / "history" / "_backfill_progress.json"
BATCH_SIZE = 5          # save every N entries
BATCH_PAUSE = 10.0      # seconds pause between batches
REQUEST_GAP = 5.0       # seconds between individual DBLP requests
MAX_RETRIES_BACKFILL = 1  # fewer retries — 503 just means DBLP is busy

# Override dblp_lookup settings for backfill mode
dblp_lookup.RATE_LIMIT_SEC = REQUEST_GAP
dblp_lookup.MAX_RETRIES = MAX_RETRIES_BACKFILL


def extract_search_query(canonical_name: str) -> tuple[str, str | None]:
    m = re.match(r"^(.+?)\([^(]+\)$", canonical_name)
    inner = m.group(1).strip() if m else canonical_name.strip()
    cleaned = inner.replace("/", " ").replace("+", " ").replace("_", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    acronym = None
    acr_match = re.match(r"^([A-Z]{2,}(?:[-\s][A-Z]{2,})*)", cleaned)
    if acr_match and len(acr_match.group(1)) >= 2:
        acronym = acr_match.group(1)
    return cleaned, acronym


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill metadata via DBLP (resumable)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Resume from last saved _backfill_progress.json")
    args = parser.parse_args()

    # Load progress if resuming
    done: set[int] = set()
    if args.resume and PROGRESS_PATH.exists():
        done = set(json.loads(PROGRESS_PATH.read_text()).get("done_indices", []))
        print(f"Resuming — {len(done)} already processed.\n")

    print(f"Loading {METADATA_PATH} ...")
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    papers = data["papers"]

    # Find entries needing backfill
    todo = []
    for i, p in enumerate(papers):
        if i in done:
            continue
        if not p.get("title") or not p.get("authors"):
            todo.append(i)

    if not todo:
        print("All entries complete. Nothing to do.")
        PROGRESS_PATH.unlink(missing_ok=True)
        return

    print(f"{len(todo)} entries to process ({len(done)} already done, {len(papers)} total).\n")

    # Backup (once, on first real run)
    backup_path = METADATA_PATH.parent / f"metadata.json.backup-{date.today().isoformat()}"
    if not args.dry_run and not args.resume:
        shutil.copy2(METADATA_PATH, backup_path)
        print(f"Backup: {backup_path}\n")

    matched = 0
    skipped = 0

    for idx, paper_idx in enumerate(todo):
        paper = papers[paper_idx]
        cn = paper.get("canonical_name", "?")
        year = paper.get("year")
        scheme_name, acronym = extract_search_query(cn)

        query = f"{scheme_name} {year}" if year else scheme_name
        results = dblp_lookup.fuzzy_title_search(query, threshold=0.5, max_results=5)

        if not results and acronym and acronym != scheme_name:
            time.sleep(REQUEST_GAP)  # gap between tries
            results = dblp_lookup.fuzzy_title_search(acronym, threshold=0.5, max_results=5)

        if results:
            best = results[0]
            score = best.get("_similarity", 0)
            if not args.dry_run:
                paper["title"] = best.get("title", "")
                paper["authors"] = best.get("authors", [])
                if best.get("doi"):
                    paper["doi"] = best["doi"]
                if best.get("dblp_key"):
                    paper["dblp_key"] = best["dblp_key"]
            matched += 1
            print(f"[{idx+1}/{len(todo)}] ✓ {cn}  score={score:.2f}  {best.get('title','')[:60]}")
        else:
            skipped += 1
            print(f"[{idx+1}/{len(todo)}] ✗ {cn}  no DBLP match")

        done.add(paper_idx)

        # Save progress every BATCH_SIZE
        if (idx + 1) % BATCH_SIZE == 0 and not args.dry_run:
            data["papers"] = papers
            with open(METADATA_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            PROGRESS_PATH.write_text(json.dumps({"done_indices": sorted(done)}, ensure_ascii=False))
            print(f"  ── saved ({matched} matched, {skipped} skipped) ──")
            time.sleep(BATCH_PAUSE)

        sys.stdout.flush()

    # Final save
    if not args.dry_run:
        data["papers"] = papers
        with open(METADATA_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        PROGRESS_PATH.write_text(json.dumps({"done_indices": sorted(done)}, ensure_ascii=False))
        print(f"\nSaved {METADATA_PATH}")

        # Rebuild index
        rebuild = _REPO / "history" / "rebuild_index.py"
        if rebuild.exists():
            import subprocess
            subprocess.run([sys.executable, str(rebuild)], check=False, cwd=str(_REPO))
    else:
        print(f"\n[DRY RUN] {matched} would match, {skipped} would skip")

    print(f"\n=== Results ===")
    print(f"  Matched : {matched}")
    print(f"  Skipped : {skipped}")
    print(f"  Total   : {len(todo)}")


if __name__ == "__main__":
    main()
