#!/usr/bin/env python3
"""Lightweight DBLP API wrapper — urllib + TLS 1.2 for dblp.org compatibility.

dblp.org requires TLS 1.2; Python 3.13 on macOS negotiates a higher version
by default, causing "record layer failure".  We force TLS 1.2 in the SSL context.

Intended to be imported from common/knowledge-synthesis/ and called via
python3 -c "from dblp_lookup import fuzzy_title_search; ..."

DBLP API docs: https://dblp.org/faq/How+can+I+access+DBLP+data+programmatically.html
"""

from __future__ import annotations

import difflib
import json
import os
import random
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# SSL — force TLS 1.2 for dblp.org compatibility
# ---------------------------------------------------------------------------

_SSL_CTX = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)  # type: ignore[attr-defined]
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DBLP_SEARCH_URL = "https://dblp.org/search/publ/api"
DBLP_BIBTEX_BASE = "https://dblp.org/rec"
REQUEST_TIMEOUT = 45  # seconds
RATE_LIMIT_SEC = 2.5   # minimum seconds between requests
MAX_RETRIES = 0        # no retries on server errors — DBLP is fragile

HEADERS = {
    "User-Agent": "domain-knowledge-skill/1.0",
    "Accept": "application/json",
}

# Paths
_MODULE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _MODULE_DIR.parent.parent
BIBTEX_BUFFER_PATH = _REPO_ROOT / "history" / "bibtex-buffer.json"

_last_request_ts = 0.0


def _rate_limit() -> None:
    global _last_request_ts
    now = time.monotonic()
    wait = RATE_LIMIT_SEC - (now - _last_request_ts)
    if wait > 0:
        time.sleep(wait + random.uniform(0, 1.0))
    _last_request_ts = time.monotonic()


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _api_get(url: str) -> Any:
    """GET *url*, return parsed JSON.  Retries with backoff on 429/503."""
    last_error: Optional[str] = None
    for attempt in range(MAX_RETRIES + 1):
        _rate_limit()
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=_SSL_CTX) as resp:
                raw = resp.read()
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            last_error = f"HTTP {exc.code}"
            if exc.code == 429:
                backoff = 10 * (2**attempt)
                if attempt < MAX_RETRIES:
                    print(f"  [dblp] HTTP 429, retrying in {backoff}s", file=sys.stderr)
                    time.sleep(backoff)
                    continue
            elif exc.code in (503, 500):
                backoff = 20 * (2**attempt)
                if attempt < MAX_RETRIES:
                    print(f"  [dblp] HTTP {exc.code}, retrying in {backoff}s", file=sys.stderr)
                    time.sleep(backoff)
                    continue
        except (urllib.error.URLError, OSError, ssl.SSLError) as exc:
            last_error = str(exc)[:80]
            if attempt < MAX_RETRIES:
                time.sleep(3 * (2**attempt))
                continue
    if last_error:
        print(f"  [dblp] API error after {MAX_RETRIES+1} tries: {last_error}", file=sys.stderr)
    return {}


def _parse_hits(data: Any) -> list[dict[str, Any]]:
    hits = data.get("result", {}).get("hits", {})
    total = int(hits.get("@total", "0"))
    if total == 0:
        return []

    publications = hits.get("hit", [])
    if not isinstance(publications, list):
        publications = [publications]

    results: list[dict[str, Any]] = []
    for pub in publications:
        info = pub.get("info", {})

        authors_data = info.get("authors", {}).get("author", [])
        if not isinstance(authors_data, list):
            authors_data = [authors_data]
        authors = []
        for a in authors_data:
            if isinstance(a, dict):
                name = a.get("text", "")
                if name:
                    authors.append(name)
            elif isinstance(a, str) and a.strip():
                authors.append(a)

        dblp_url = info.get("url", "")
        dblp_key = dblp_url.replace("https://dblp.org/rec/", "") if dblp_url else pub.get("@id", "").replace("dblp:", "")

        results.append({
            "title": info.get("title", ""),
            "authors": authors,
            "venue": info.get("venue", ""),
            "year": int(info.get("year", 0)) if info.get("year") else None,
            "type": info.get("type", ""),
            "doi": info.get("doi", ""),
            "url": dblp_url or info.get("url", ""),
            "dblp_key": dblp_key,
        })
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def search(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    if not query or not query.strip():
        return []
    params = urllib.parse.urlencode({"q": query.strip(), "format": "json", "h": max_results})
    return _parse_hits(_api_get(f"{DBLP_SEARCH_URL}?{params}"))


def fuzzy_title_search(title: str, threshold: float = 0.25, max_results: int = 10) -> list[dict[str, Any]]:
    """Fuzzy-match DBLP titles. Uses whole-word overlap scoring.

    DBLP titles are much longer than scheme-name queries, so raw difflib
    ratios are misleadingly low (e.g. 0.28 for "PithTrain 2026" vs a 58-char
    title).  Instead we use a whole-word-overlap score: each word from the
    query that appears as a whole word in the title contributes ~0.25.
    """
    if not title or not title.strip():
        return []
    title_clean = title.strip()
    query_lower = title_clean.lower()
    # Split into words, keeping only meaningful tokens (len >= 2)
    query_words = [w.strip(".,:;!?()[]") for w in query_lower.split() if len(w) > 1]

    candidates = search(title_clean, max_results * 3)

    scored = []
    for pub in candidates:
        pub_title = pub.get("title", "")
        if not pub_title:
            continue
        pub_lower = pub_title.lower()

        # Count query words found as WHOLE words in the title
        found = 0
        for qw in query_words:
            # Check as whole-word boundary match
            import re as _re
            if _re.search(r'\b' + _re.escape(qw) + r'\b', pub_lower):
                found += 1

        if len(query_words) > 0:
            score = found / len(query_words)
        else:
            score = 0.0

        if score >= threshold:
            pub["_similarity"] = round(score, 4)
            scored.append(pub)

    scored.sort(key=lambda x: x["_similarity"], reverse=True)  # type: ignore[arg-type,return-value]
    return scored[:max_results]


def get_bibtex(dblp_key: str) -> Optional[str]:
    if not dblp_key or not dblp_key.strip():
        return None
    dblp_key = dblp_key.strip()
    urls = [f"{DBLP_BIBTEX_BASE}/{dblp_key}.bib"]
    for url in urls:
        _rate_limit()
        try:
            req = urllib.request.Request(url, headers={**HEADERS, "Accept": "text/plain"})
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=_SSL_CTX) as resp:
                text = resp.read().decode("utf-8", errors="replace")
                if text.strip() and not text.strip().startswith("{"):
                    return text.strip()
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# BibTeX buffer
# ---------------------------------------------------------------------------

def _load_bibtex_buffer() -> dict[str, str]:
    try:
        os.makedirs(BIBTEX_BUFFER_PATH.parent, exist_ok=True)
        if BIBTEX_BUFFER_PATH.exists():
            return json.loads(BIBTEX_BUFFER_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save_bibtex_buffer(data: dict[str, str]) -> None:
    os.makedirs(BIBTEX_BUFFER_PATH.parent, exist_ok=True)
    BIBTEX_BUFFER_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def collect_bibtex(dblp_key: str, citation_key: str) -> bool:
    bibtex = get_bibtex(dblp_key)
    if not bibtex:
        return False
    bibtex = re.sub(r'^@(\w+)\{([^,]+),', rf'@\1{{{citation_key},', bibtex, count=1)
    buf = _load_bibtex_buffer()
    buf[citation_key] = bibtex
    _save_bibtex_buffer(buf)
    print(json.dumps({"message": f"Added {citation_key}", "count": len(buf), "buffer_path": str(BIBTEX_BUFFER_PATH)}, ensure_ascii=False, indent=2))
    return True


def export_bibtex(output_path: str) -> int:
    buf = _load_bibtex_buffer()
    entries = list(buf.values())
    if not entries:
        raise SystemExit("Buffer is empty.")
    path = Path(output_path)
    if not path.suffix:
        path = path.with_suffix(".bib")
    os.makedirs(path.parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(entry + "\n\n")
    _save_bibtex_buffer({})
    print(json.dumps({"message": f"Exported {len(entries)} references", "path": str(path)}, ensure_ascii=False, indent=2))
    return len(entries)


def bibtex_buffer_count() -> int:
    return len(_load_bibtex_buffer())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="DBLP lookup")
    sp = p.add_subparsers(dest="cmd", required=True)
    s1 = sp.add_parser("search"); s1.add_argument("--query", required=True); s1.add_argument("--max-results", type=int, default=5)
    s2 = sp.add_parser("fuzzy"); s2.add_argument("--title", required=True); s2.add_argument("--threshold", type=float, default=0.6); s2.add_argument("--max-results", type=int, default=5)
    s3 = sp.add_parser("get-bibtex"); s3.add_argument("--dblp-key", required=True)
    s4 = sp.add_parser("collect-bibtex"); s4.add_argument("--dblp-key", required=True); s4.add_argument("--citation-key", required=True)
    s5 = sp.add_parser("export-bibtex"); s5.add_argument("--path", required=True)

    args = p.parse_args()
    if args.cmd == "search":
        print(json.dumps(search(query=args.query, max_results=args.max_results), ensure_ascii=False, indent=2))
    elif args.cmd == "fuzzy":
        print(json.dumps(fuzzy_title_search(title=args.title, threshold=args.threshold, max_results=args.max_results), ensure_ascii=False, indent=2))
    elif args.cmd == "get-bibtex":
        bib = get_bibtex(args.dblp_key)
        print(bib if bib else "(not found)")
    elif args.cmd == "collect-bibtex":
        collect_bibtex(dblp_key=args.dblp_key, citation_key=args.citation_key)
    elif args.cmd == "export-bibtex":
        export_bibtex(args.path)
