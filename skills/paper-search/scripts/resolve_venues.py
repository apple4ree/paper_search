"""Re-classify papers whose venue is ambiguous by reading their PDF.

Input  (stdin): JSON object mapping bucket → list of paper dicts — the output
                of `dedupe.py`.
Output (stdout): JSON object with ambiguous-bucket entries moved to the
                 correct venue bucket when PDF headers reveal one.

"Ambiguous" buckets are:
  - `arxiv_only`  — likely missed conference publication
  - any bucket whose name is NOT in `venues.yaml` `venues[*].name` and is NOT
    in `special_categories` — i.e. a truncated gscholar string like
    "Proceedings of the …".

Each paper re-probed is annotated with `"venue_resolution": "pdf"` so
downstream stages can distinguish PDF-confirmed venues from dedupe-assigned
ones.

Library usage:
    resolved = resolve(deduped_dict, cache_dir=...)

CLI usage:
    cat deduped.json | python -m scripts.resolve_venues > resolved.json
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

from scripts.download_pdf import download_pdf as _download_pdf
from scripts.venue_from_pdf import detect_venue


_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "venues.yaml"


@lru_cache(maxsize=1)
def _known_buckets() -> set[str]:
    data = yaml.safe_load(_CONFIG_PATH.read_text())
    return {v["name"] for v in data.get("venues", [])} | set(
        data.get("special_categories", [])
    )


def _is_ambiguous(bucket: str) -> bool:
    if bucket == "arxiv_only":
        return True
    return bucket not in _known_buckets()


def resolve(deduped: dict, cache_dir: Optional[Path] = None) -> dict:
    """Return a new dict with ambiguous-bucket papers reclassified via PDF."""
    if cache_dir is None:
        cache_dir = Path(tempfile.mkdtemp(prefix="paper-search-venue-"))
    cache_dir = Path(cache_dir)

    out: dict[str, list[dict]] = {}

    # First pass: papers in non-ambiguous buckets stay put.
    for bucket, papers in deduped.items():
        if _is_ambiguous(bucket):
            continue
        out.setdefault(bucket, []).extend(papers)

    # Second pass: try to resolve each ambiguous paper.
    for bucket, papers in deduped.items():
        if not _is_ambiguous(bucket):
            continue
        for paper in papers:
            resolved_venue: Optional[str] = None
            pdf_path = _download_pdf(paper, cache_dir)
            if pdf_path is not None:
                resolved_venue = detect_venue(pdf_path)

            if resolved_venue:
                paper = dict(paper)  # don't mutate input
                paper["venue"] = resolved_venue
                paper["venue_resolution"] = "pdf"
                out.setdefault(resolved_venue, []).append(paper)
            else:
                out.setdefault("arxiv_only", []).append(paper)

    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reclassify ambiguous-bucket papers via PDF header inspection."
    )
    parser.add_argument("--cache-dir", default=None,
                        help="Directory for cached PDFs (default: tempdir).")
    args = parser.parse_args(argv)

    try:
        deduped = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"resolve_venues: invalid JSON on stdin: {e}", file=sys.stderr)
        return 1

    cache = Path(args.cache_dir) if args.cache_dir else None
    resolved = resolve(deduped, cache_dir=cache)

    json.dump(resolved, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
