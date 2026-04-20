"""Detect a paper's venue by reading the PDF's first-page header.

Used when gscholar returns a truncated venue string (e.g. "Proceedings of the …")
and the `dedupe.py` rule-based classification can't place the paper. We download
the first page only, extract its text, and match against `pdf_patterns` in
`config/venues.yaml`.

Library usage:
    from scripts.venue_from_pdf import detect_venue
    venue = detect_venue(Path("paper.pdf"))   # returns "ICLR" | "NeurIPS" | ... | None

CLI usage:
    python -m scripts.venue_from_pdf --pdf path/to/paper.pdf
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

import fitz
import yaml

# Silence MuPDF diagnostic messages. PyMuPDF writes color-profile warnings and
# other non-fatal notes to stdout/stderr at the C level, which corrupts our
# JSON-on-stdout pipeline (resolve_venues.py). Safe to suppress: we already
# handle all recoverable errors in Python.
try:
    fitz.TOOLS.mupdf_display_errors(False)
    fitz.TOOLS.mupdf_display_warnings(False)
except (AttributeError, Exception):
    pass


_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "venues.yaml"


@lru_cache(maxsize=1)
def _load_patterns() -> dict[str, list[str]]:
    """Return {venue_name: [regex_pattern, ...]} from venues.yaml."""
    data = yaml.safe_load(_CONFIG_PATH.read_text())
    out: dict[str, list[str]] = {}
    for v in data.get("venues", []):
        patterns = v.get("pdf_patterns") or []
        if patterns:
            out[v["name"]] = patterns
    return out


def _first_page_text(pdf_path: Path) -> Optional[str]:
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return None
    try:
        if doc.page_count == 0:
            return None
        return doc[0].get_text()
    except Exception:
        return None
    finally:
        doc.close()


def detect_venue(pdf_path: Path) -> Optional[str]:
    """Return a canonical venue name, or None when nothing matches.

    If multiple venues' patterns match, returns the venue with the earliest
    match offset — that's typically the most specific/prominent mention.
    Ties broken by pattern order (more specific patterns first within a venue).
    """
    text = _first_page_text(Path(pdf_path))
    if not text:
        return None

    patterns = _load_patterns()
    if not patterns:
        return None

    # Normalise whitespace so multi-line headers match single-line patterns.
    flat = re.sub(r"\s+", " ", text.lower())

    best: Optional[tuple[int, str]] = None   # (match_start, venue_name)
    for venue, pats in patterns.items():
        for pat in pats:
            m = re.search(pat, flat, re.IGNORECASE)
            if m is None:
                continue
            if best is None or m.start() < best[0]:
                best = (m.start(), venue)
            break  # first matching pattern per venue is enough
    return best[1] if best else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect venue from PDF first page.")
    parser.add_argument("--pdf", required=True)
    args = parser.parse_args(argv)

    venue = detect_venue(Path(args.pdf))
    print(json.dumps({"venue": venue}))
    return 0 if venue else 1


if __name__ == "__main__":
    raise SystemExit(main())
