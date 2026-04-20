"""Resolve a paper record to a PDF URL and download it to disk.

Library usage: `resolve_pdf_url(paper)` and `download_pdf(paper, dest_dir)`.
CLI usage:
    python -m scripts.download_pdf --paper paper.json --out-dir ./cache
    echo '<paper.json>' | python -m scripts.download_pdf --out-dir ./cache

Never raises on network failures — returns None and logs to stderr.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

import requests

from scripts.common import title_slug, first_author_lastname


_ARXIV_VERSION_RE = re.compile(r"v\d+$")
_OPENREVIEW_FORUM_RE = re.compile(r"openreview\.net/forum", re.IGNORECASE)


def resolve_pdf_url(paper: dict) -> Optional[str]:
    """Pick the best PDF URL from a paper record, or None if unresolvable.

    Priority: arxiv_id > pdf_url > openreview forum URL.
    """
    arxiv_id = paper.get("arxiv_id")
    if arxiv_id:
        clean = _ARXIV_VERSION_RE.sub("", arxiv_id).strip()
        if clean:
            return f"https://arxiv.org/pdf/{clean}.pdf"

    pdf_url = paper.get("pdf_url")
    if pdf_url:
        return pdf_url

    url = paper.get("url") or ""
    if _OPENREVIEW_FORUM_RE.search(url):
        parsed = urlparse(url)
        forum_id = parse_qs(parsed.query).get("id", [""])[0]
        if forum_id:
            return f"https://openreview.net/pdf?id={forum_id}"

    return None


def _paper_filename(paper: dict) -> str:
    if paper.get("arxiv_id"):
        return f"{paper['arxiv_id'].replace('/', '_')}.pdf"
    year = paper.get("year", "NA")
    author = first_author_lastname(paper.get("authors", [])) or "anon"
    slug = title_slug(paper.get("title", "untitled"), max_len=40)
    return f"{year}-{author}-{slug}.pdf"


def download_pdf(paper: dict, dest_dir: Path, *, timeout: int = 30) -> Optional[Path]:
    """Fetch the paper's PDF into dest_dir. Returns the saved Path or None."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    url = resolve_pdf_url(paper)
    if not url:
        print(f"download_pdf: no resolvable URL for {paper.get('title', '?')!r}",
              file=sys.stderr)
        return None

    out = dest_dir / _paper_filename(paper)
    if out.exists() and out.stat().st_size > 0:
        return out

    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=timeout, allow_redirects=True,
                                headers={"User-Agent": "paper-search/0.1"})
            resp.raise_for_status()
            ctype = resp.headers.get("Content-Type", "").lower()
            if "pdf" not in ctype and not resp.content.startswith(b"%PDF"):
                print(f"download_pdf: {url} returned non-PDF ({ctype})",
                      file=sys.stderr)
                return None
            out.write_bytes(resp.content)
            return out
        except requests.RequestException as e:
            print(f"download_pdf: attempt {attempt+1} failed for {url}: {e}",
                  file=sys.stderr)
            time.sleep(2 ** attempt)

    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download paper PDFs.")
    parser.add_argument("--paper", help="Path to a single paper JSON file")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)

    if args.paper:
        paper = json.loads(Path(args.paper).read_text())
    else:
        paper = json.load(sys.stdin)

    p = download_pdf(paper, Path(args.out_dir))
    if p is None:
        return 1
    print(str(p))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
