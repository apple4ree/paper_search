"""Search arXiv. Emits a JSON array of Paper records on stdout."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
import time

import arxiv
import requests

from scripts.common import Paper


def current_year() -> int:
    return _dt.datetime.now(_dt.timezone.utc).year


def _result_to_paper(r) -> Paper:
    return Paper(
        title=r.title.strip(),
        authors=[a.name for a in r.authors],
        year=r.published.year,
        venue=None,
        abstract=(r.summary or "").strip(),
        url=r.entry_id,
        pdf_url=r.pdf_url,
        arxiv_id=r.get_short_id(),
        doi=r.doi,
        source="arxiv",
    )


def _search(query: str, top: int) -> list:
    search = arxiv.Search(
        query=query,
        max_results=top,
        sort_by=arxiv.SortCriterion.Relevance,
    )
    client = arxiv.Client(page_size=min(top, 100), delay_seconds=3, num_retries=3)
    return list(client.results(search))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Search arXiv")
    parser.add_argument("--query", required=True)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--years", type=int, default=None,
                        help="Only keep papers from the last N years")
    parser.add_argument("--venue", default=None, help="Ignored (arXiv has no venue filter)")
    args = parser.parse_args(argv)

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            raw = _search(args.query, args.top)
            break
        except (arxiv.ArxivError, requests.exceptions.RequestException) as e:
            last_exc = e
            time.sleep(2 ** attempt)
    else:
        print(f"arxiv search failed: {last_exc}", file=sys.stderr)
        return 1

    papers = [_result_to_paper(r) for r in raw]
    if args.years is not None:
        cutoff = current_year() - args.years
        papers = [p for p in papers if p.year >= cutoff]

    json.dump([p.to_dict() for p in papers], sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
