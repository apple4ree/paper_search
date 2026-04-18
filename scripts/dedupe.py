"""Merge paper lists, apply venue-wins dedup, classify into categories.

Input : JSON array of Paper dicts on stdin.
Output: JSON object {category: [paper dicts with optional alt_urls]} on stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Iterable

from scripts.common import Paper, dedup_key, normalize_title, first_author_lastname


# Priority of source when merging: higher wins.
_SOURCE_PRIORITY = {"openreview": 3, "gscholar": 2, "arxiv": 1}


def _category(p: Paper) -> str:
    if p.venue == "workshop":
        return "workshop"
    if not p.venue:
        return "arxiv_only"
    return p.venue


def _merge(primary: Paper, other: Paper) -> tuple[Paper, list[str]]:
    """Return a merged paper plus accumulated alt_urls."""
    new_arxiv = primary.arxiv_id or other.arxiv_id
    new_doi = primary.doi or other.doi
    new_pdf = primary.pdf_url or other.pdf_url
    new_abstract = primary.abstract or other.abstract
    merged = Paper(
        title=primary.title,
        authors=primary.authors,
        year=primary.year or other.year,
        venue=primary.venue,
        abstract=new_abstract,
        url=primary.url,
        pdf_url=new_pdf,
        arxiv_id=new_arxiv,
        doi=new_doi,
        source=primary.source,
    )
    alts = [other.url] if other.url and other.url != primary.url else []
    return merged, alts


def dedupe(papers: Iterable[Paper]) -> dict[str, list[dict]]:
    best: dict[tuple, Paper] = {}
    alts: dict[tuple, list[str]] = {}
    # Secondary index: (normalized_title, first_author_lastname) -> primary key in best.
    # Lets an incoming paper match a previously stored paper with the same title,
    # regardless of whether it's keyed by doi/arxiv/title.
    _title_index: dict[tuple, tuple] = {}

    for p in papers:
        k = dedup_key(p)
        title_sig = (normalize_title(p.title), first_author_lastname(p.authors))

        existing_key: tuple | None = None
        if k in best:
            existing_key = k
        elif title_sig in _title_index:
            existing_key = _title_index[title_sig]

        if existing_key is None:
            best[k] = p
            alts[k] = []
            # Index all papers by title signature for future matching
            _title_index[title_sig] = k
            continue

        current = best[existing_key]
        if _SOURCE_PRIORITY[p.source] > _SOURCE_PRIORITY[current.source]:
            merged, extra = _merge(p, current)
        else:
            merged, extra = _merge(current, p)
        best[existing_key] = merged
        alts[existing_key].extend(extra)

    out: dict[str, list[dict]] = {}
    for k, paper in best.items():
        d = paper.to_dict()
        if alts[k]:
            d["alt_urls"] = alts[k]
        out.setdefault(_category(paper), []).append(d)
    return out


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="Dedupe paper search results").parse_args(argv)
    try:
        raw = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"dedupe: invalid JSON on stdin: {e}", file=sys.stderr)
        return 1
    papers = [Paper.from_dict(d) for d in raw]
    result = dedupe(papers)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
