"""Search OpenReview. Emits a JSON array of Paper records on stdout."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys

import openreview

from scripts.common import Paper


VENUE_NAME_RE = re.compile(r"^\s*([A-Za-z]+)")


def current_year() -> int:
    return _dt.datetime.now(_dt.timezone.utc).year


def make_client():
    # Anonymous read-only access is sufficient for public metadata.
    return openreview.api.OpenReviewClient(baseurl="https://api2.openreview.net")


def _extract_year(note) -> int:
    ts = getattr(note, "pdate", None) or getattr(note, "cdate", None)
    if ts is None:
        return 0
    return _dt.datetime.fromtimestamp(ts / 1000.0, tz=_dt.timezone.utc).year


def _venue_label(raw: str | None) -> str | None:
    """Normalise OpenReview venue string to short venue name or 'workshop'."""
    if not raw:
        return None
    if "workshop" in raw.lower():
        return "workshop"
    m = VENUE_NAME_RE.match(raw)
    return m.group(1) if m else raw


def _get(note, key: str, default=None):
    val = note.content.get(key, default)
    if isinstance(val, dict) and "value" in val:
        return val["value"]
    return val if val is not None else default


def _note_to_paper(note) -> Paper:
    title = (_get(note, "title", "") or "").strip()
    authors = _get(note, "authors", []) or []
    abstract = (_get(note, "abstract", "") or "").strip()
    venue_raw = _get(note, "venue", None)
    pdf = _get(note, "pdf", None)
    forum_id = note.forum or note.id
    return Paper(
        title=title,
        authors=list(authors),
        year=_extract_year(note),
        venue=_venue_label(venue_raw),
        abstract=abstract,
        url=f"https://openreview.net/forum?id={forum_id}",
        pdf_url=(f"https://openreview.net{pdf}" if pdf and pdf.startswith("/") else pdf),
        arxiv_id=None,
        doi=None,
        source="openreview",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search OpenReview")
    parser.add_argument("--query", required=True)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--years", type=int, default=None)
    parser.add_argument("--venue", required=True,
                        help="OpenReview group prefix, e.g. NeurIPS.cc")
    args = parser.parse_args(argv)

    try:
        client = make_client()
        notes = client.search_notes(
            term=args.query,
            group=args.venue,
            limit=max(args.top * 2, args.top),  # over-fetch before year filter
        )
    except Exception as e:
        print(f"openreview search failed ({args.venue}): {e}", file=sys.stderr)
        return 1

    papers = [_note_to_paper(n) for n in notes]
    if args.years is not None:
        cutoff = current_year() - args.years
        papers = [p for p in papers if p.year and p.year >= cutoff]
    papers = papers[: args.top]

    json.dump([p.to_dict() for p in papers], sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
