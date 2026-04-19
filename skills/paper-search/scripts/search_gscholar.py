"""Search Google Scholar. Emits a JSON array of Paper records on stdout.

Notes:
    Google Scholar routinely blocks scraping. This script retries once then
    fails with a non-zero exit code and a human-readable message.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
import time

from scholarly import scholarly, MaxTriesExceededException

from scripts.common import Paper


class BlockedError(RuntimeError):
    """Raised when Google Scholar blocks our request."""


def current_year() -> int:
    return _dt.datetime.now(_dt.timezone.utc).year


def run_search(query: str, top: int) -> list[dict]:
    """Perform the actual scholarly call. Factored out so tests can stub it."""
    results: list[dict] = []
    try:
        iterator = scholarly.search_pubs(query)
        for i, pub in enumerate(iterator):
            if i >= top:
                break
            results.append(pub)
    except MaxTriesExceededException as e:
        raise BlockedError(str(e)) from e
    except Exception as e:  # heuristic: most scrape failures look like blocks
        msg = str(e).lower()
        if "429" in msg or "captcha" in msg or "blocked" in msg:
            raise BlockedError(str(e)) from e
        raise
    return results


def _pub_to_paper(pub: dict) -> Paper:
    bib = pub.get("bib", {})
    author_raw = bib.get("author", "")
    if isinstance(author_raw, list):
        authors = [str(a).strip() for a in author_raw if str(a).strip()]
    else:
        authors = [a.strip() for a in str(author_raw).split(" and ") if a.strip()]
    year_raw = bib.get("pub_year") or bib.get("year") or "0"
    try:
        year = int(str(year_raw)[:4])
    except ValueError:
        year = 0
    return Paper(
        title=(bib.get("title") or "").strip(),
        authors=authors,
        year=year,
        venue=(bib.get("venue") or None),
        abstract=(bib.get("abstract") or "").strip(),
        url=pub.get("pub_url") or pub.get("eprint_url") or "",
        pdf_url=pub.get("eprint_url"),
        arxiv_id=None,
        doi=None,
        source="gscholar",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search Google Scholar")
    parser.add_argument("--query", required=True)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--years", type=int, default=None)
    parser.add_argument("--venue", default=None, help="Ignored")
    args = parser.parse_args(argv)

    last: Exception | None = None
    for attempt in range(2):  # initial + 1 retry
        try:
            raw = run_search(args.query, args.top)
            break
        except BlockedError as e:
            last = e
            time.sleep(3)
    else:
        print(f"gscholar blocked: {last}", file=sys.stderr)
        return 2

    papers = [_pub_to_paper(p) for p in raw]
    if args.years is not None:
        cutoff = current_year() - args.years
        papers = [p for p in papers if p.year and p.year >= cutoff]

    json.dump([p.to_dict() for p in papers], sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
