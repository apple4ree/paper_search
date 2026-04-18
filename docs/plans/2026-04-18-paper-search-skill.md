# paper-search Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Claude Code skill that analyses a research project, runs paper searches against arXiv / OpenReview / Google Scholar, and emits a venue-organised related-work directory.

**Architecture:** Skill = Markdown procedure (`SKILL.md`) + four Python scripts (`search_arxiv.py`, `search_openreview.py`, `search_gscholar.py`, `dedupe.py`) sharing a common `Paper` schema. Claude orchestrates: read project → generate queries → call scripts in parallel → pipe to `dedupe.py` → rank → write Markdown.

**Tech Stack:** Python ≥ 3.10, `arxiv`, `openreview-py` (API v2), `scholarly`, `pyyaml`; dev: `pytest`, `pytest-mock`, `responses`.

**Working directory:** `/home/dgu/skill_paper_search/`. The skill package is developed under `paper-search/` and later symlinked into `~/.claude/skills/paper-search/` (Task 12).

---

## File Structure

```
/home/dgu/skill_paper_search/
├── .gitignore
├── README.md
├── docs/
│   └── superpowers/
│       ├── specs/2026-04-18-paper-search-skill-design.md
│       └── plans/2026-04-18-paper-search-skill.md   # this file
└── paper-search/
    ├── SKILL.md
    ├── requirements.txt
    ├── requirements-dev.txt
    ├── pyproject.toml                 # pytest config only
    ├── config/
    │   └── venues.yaml
    ├── references/
    │   └── query_generation.md
    ├── scripts/
    │   ├── __init__.py
    │   ├── common.py                  # Paper dataclass, normalisation, dedup key
    │   ├── search_arxiv.py
    │   ├── search_openreview.py
    │   ├── search_gscholar.py
    │   └── dedupe.py
    └── tests/
        ├── __init__.py
        ├── conftest.py
        ├── test_common.py
        ├── test_arxiv.py
        ├── test_openreview.py
        ├── test_gscholar.py
        ├── test_dedupe.py
        └── test_integration.py        # real arXiv call
```

**Responsibility per file:**
- `common.py` — `Paper` dataclass, `normalize_title`, `title_slug`, `first_author_lastname`, `dedup_key` (single source of truth for schema + key logic).
- `search_*.py` — one source per file, identical CLI, emits JSON on stdout.
- `dedupe.py` — reads combined JSON from stdin, applies venue-wins merge, emits classified JSON on stdout.
- `SKILL.md` — procedure Claude follows; references scripts and `query_generation.md`.
- `venues.yaml` — config data, no logic.

---

## Task 1: Project Bootstrap

**Files:**
- Create: `/home/dgu/skill_paper_search/.gitignore`
- Create: `/home/dgu/skill_paper_search/README.md`
- Create: `/home/dgu/skill_paper_search/paper-search/requirements.txt`
- Create: `/home/dgu/skill_paper_search/paper-search/requirements-dev.txt`
- Create: `/home/dgu/skill_paper_search/paper-search/pyproject.toml`
- Create: `/home/dgu/skill_paper_search/paper-search/scripts/__init__.py`
- Create: `/home/dgu/skill_paper_search/paper-search/tests/__init__.py`

- [ ] **Step 1: Initialise git**

```bash
cd /home/dgu/skill_paper_search
git init
git add docs/
git commit -m "chore: add design spec and implementation plan"
```

- [ ] **Step 2: Write `.gitignore`**

Path: `/home/dgu/skill_paper_search/.gitignore`
```
__pycache__/
*.pyc
.pytest_cache/
.venv/
venv/
*.egg-info/
.DS_Store
```

- [ ] **Step 3: Write top-level `README.md`**

Path: `/home/dgu/skill_paper_search/README.md`
```markdown
# paper-search skill

Claude Code skill that analyses a research project and builds a venue-organised related-work directory from arXiv, OpenReview, and Google Scholar.

See `docs/superpowers/specs/2026-04-18-paper-search-skill-design.md` for design and `docs/superpowers/plans/2026-04-18-paper-search-skill.md` for the implementation plan.

## Install (after implementation)

    ln -s /home/dgu/skill_paper_search/paper-search ~/.claude/skills/paper-search
    cd paper-search && python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
```

- [ ] **Step 4: Write `paper-search/requirements.txt`**

Path: `/home/dgu/skill_paper_search/paper-search/requirements.txt`
```
arxiv>=2.1.0
openreview-py>=1.42.0
scholarly>=1.7.11
pyyaml>=6.0
```

- [ ] **Step 5: Write `paper-search/requirements-dev.txt`**

Path: `/home/dgu/skill_paper_search/paper-search/requirements-dev.txt`
```
-r requirements.txt
pytest>=8.0
pytest-mock>=3.12
responses>=0.25
```

- [ ] **Step 6: Write `paper-search/pyproject.toml`** (pytest config only, no packaging)

Path: `/home/dgu/skill_paper_search/paper-search/pyproject.toml`
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
markers = [
    "integration: real network calls, skipped by default",
]
addopts = "-m 'not integration'"
```

- [ ] **Step 7: Create empty `__init__.py` files**

```bash
cd /home/dgu/skill_paper_search
touch paper-search/scripts/__init__.py paper-search/tests/__init__.py
```

- [ ] **Step 8: Create and activate venv, install dev deps**

```bash
cd /home/dgu/skill_paper_search/paper-search
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```
Expected: all four runtime deps + pytest/mock/responses installed without error.

- [ ] **Step 9: Commit bootstrap**

```bash
cd /home/dgu/skill_paper_search
git add .gitignore README.md paper-search/
git commit -m "chore: scaffold paper-search skill package"
```

---

## Task 2: Common Schema & Helpers (`common.py`)

**Files:**
- Create: `paper-search/tests/test_common.py`
- Create: `paper-search/scripts/common.py`

Provides the `Paper` dataclass used by all search scripts and the key helpers for slug generation, title normalisation, and dedup key selection.

- [ ] **Step 1: Write the failing tests**

Path: `paper-search/tests/test_common.py`
```python
import pytest
from scripts.common import (
    Paper,
    normalize_title,
    title_slug,
    first_author_lastname,
    dedup_key,
)


def test_paper_round_trip_dict():
    p = Paper(
        title="Chain-of-Thought Distillation",
        authors=["Jane Smith", "Bob Lee"],
        year=2024,
        venue="NeurIPS",
        abstract="We distill reasoning...",
        url="https://openreview.net/forum?id=abc",
        pdf_url=None,
        arxiv_id="2401.12345",
        doi=None,
        source="openreview",
    )
    d = p.to_dict()
    assert d["title"] == "Chain-of-Thought Distillation"
    assert d["authors"] == ["Jane Smith", "Bob Lee"]
    assert Paper.from_dict(d) == p


def test_normalize_title_strips_punct_and_lowercases():
    assert normalize_title("Chain-of-Thought: Reasoning!") == "chain of thought reasoning"
    assert normalize_title("  Multi  Spaces  ") == "multi spaces"


def test_title_slug_truncates_and_hyphenates():
    s = title_slug("Chain-of-Thought Distillation for Small Language Models")
    assert s == "chain-of-thought-distillation-for-small-language-models"
    long_title = "A " * 60
    assert len(title_slug(long_title)) <= 60


def test_first_author_lastname_handles_comma_and_space_forms():
    assert first_author_lastname(["Jane Smith", "Bob Lee"]) == "smith"
    assert first_author_lastname(["Smith, Jane", "Lee, Bob"]) == "smith"
    assert first_author_lastname(["Plato"]) == "plato"
    assert first_author_lastname([]) == ""


def test_dedup_key_prefers_doi_then_arxiv_then_title_author():
    p_doi = Paper(
        title="T", authors=["A B"], year=2024, venue="X",
        abstract="", url="", pdf_url=None,
        arxiv_id="2401.1", doi="10.1/abc", source="arxiv",
    )
    p_arxiv = Paper(
        title="T", authors=["A B"], year=2024, venue="X",
        abstract="", url="", pdf_url=None,
        arxiv_id="2401.1", doi=None, source="arxiv",
    )
    p_title = Paper(
        title="Cool Paper!", authors=["Alice Zed"], year=2024, venue="X",
        abstract="", url="", pdf_url=None,
        arxiv_id=None, doi=None, source="arxiv",
    )
    assert dedup_key(p_doi) == ("doi", "10.1/abc")
    assert dedup_key(p_arxiv) == ("arxiv", "2401.1")
    assert dedup_key(p_title) == ("title", "cool paper", "zed")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/dgu/skill_paper_search/paper-search
source .venv/bin/activate
pytest tests/test_common.py -v
```
Expected: FAIL with `ModuleNotFoundError: scripts.common`.

- [ ] **Step 3: Implement `common.py`**

Path: `paper-search/scripts/common.py`
```python
"""Shared schema and helpers for paper-search scripts."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Optional


@dataclass(frozen=True)
class Paper:
    title: str
    authors: list[str]
    year: int
    venue: Optional[str]
    abstract: str
    url: str
    pdf_url: Optional[str]
    arxiv_id: Optional[str]
    doi: Optional[str]
    source: str  # "arxiv" | "openreview" | "gscholar"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Paper":
        return cls(
            title=d["title"],
            authors=list(d["authors"]),
            year=d["year"],
            venue=d.get("venue"),
            abstract=d.get("abstract", ""),
            url=d["url"],
            pdf_url=d.get("pdf_url"),
            arxiv_id=d.get("arxiv_id"),
            doi=d.get("doi"),
            source=d["source"],
        )


_PUNCT_RE = re.compile(r"[^\w\s-]")
_WS_RE = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation (except hyphens), collapse whitespace."""
    t = _PUNCT_RE.sub(" ", title.lower())
    t = t.replace("-", " ")
    t = _WS_RE.sub(" ", t).strip()
    return t


def title_slug(title: str, max_len: int = 60) -> str:
    """Produce a filesystem-safe slug, hyphen-separated, at most max_len chars."""
    t = _PUNCT_RE.sub("", title.lower())
    t = _WS_RE.sub("-", t).strip("-")
    if len(t) <= max_len:
        return t
    cut = t[:max_len].rsplit("-", 1)[0] or t[:max_len]
    return cut


def first_author_lastname(authors: list[str]) -> str:
    """Return the first author's last name, lowercased."""
    if not authors:
        return ""
    first = authors[0].strip()
    if "," in first:
        return first.split(",", 1)[0].strip().lower()
    parts = first.split()
    return (parts[-1] if parts else first).lower()


def dedup_key(paper: Paper) -> tuple:
    """Priority: doi > arxiv_id > (normalized title, first-author last name)."""
    if paper.doi:
        return ("doi", paper.doi.lower())
    if paper.arxiv_id:
        return ("arxiv", paper.arxiv_id.lower())
    return ("title", normalize_title(paper.title), first_author_lastname(paper.authors))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_common.py -v
```
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/dgu/skill_paper_search
git add paper-search/scripts/common.py paper-search/tests/test_common.py
git commit -m "feat: add Paper schema and dedup helpers"
```

---

## Task 3: arXiv Search Script

**Files:**
- Create: `paper-search/tests/test_arxiv.py`
- Create: `paper-search/scripts/search_arxiv.py`

Uses the `arxiv` Python library. Converts `arxiv.Result` → `Paper` and prints a JSON array on stdout.

- [ ] **Step 1: Write the failing tests**

Path: `paper-search/tests/test_arxiv.py`
```python
import json
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest


def _fake_result(
    title="Sample Paper",
    authors_raw=("Jane Smith", "Bob Lee"),
    year=2024,
    arxiv_id="2401.12345",
    summary="An abstract.",
    pdf_url="http://arxiv.org/pdf/2401.12345v1",
    abs_url="http://arxiv.org/abs/2401.12345",
    doi=None,
):
    r = MagicMock()
    r.title = title
    r.authors = [MagicMock(name=f"a{i}") for i in range(len(authors_raw))]
    for m, name in zip(r.authors, authors_raw):
        m.name = name
    r.published.year = year
    r.summary = summary
    r.entry_id = abs_url
    r.pdf_url = pdf_url
    r.doi = doi
    r.get_short_id.return_value = arxiv_id
    return r


def test_search_arxiv_main_prints_json(monkeypatch, capsys):
    from scripts import search_arxiv

    fake_results = [_fake_result(title="A", arxiv_id="2401.1"),
                    _fake_result(title="B", arxiv_id="2401.2")]

    class FakeSearch:
        def __init__(self, *a, **kw): pass

    class FakeClient:
        def results(self, search):
            return iter(fake_results)

    monkeypatch.setattr(search_arxiv.arxiv, "Search", FakeSearch)
    monkeypatch.setattr(search_arxiv.arxiv, "Client", lambda *a, **kw: FakeClient())

    rc = search_arxiv.main(["--query", "transformer", "--top", "2"])
    assert rc == 0

    out = capsys.readouterr().out
    data = json.loads(out)
    assert len(data) == 2
    assert data[0]["title"] == "A"
    assert data[0]["arxiv_id"] == "2401.1"
    assert data[0]["source"] == "arxiv"
    assert data[0]["authors"] == ["Jane Smith", "Bob Lee"]
    assert data[0]["year"] == 2024
    assert data[0]["venue"] is None


def test_search_arxiv_filters_by_years(monkeypatch, capsys):
    from scripts import search_arxiv

    fake_results = [_fake_result(title="Old", year=2018, arxiv_id="1801.1"),
                    _fake_result(title="New", year=2024, arxiv_id="2401.1")]

    class FakeClient:
        def results(self, search):
            return iter(fake_results)

    monkeypatch.setattr(search_arxiv.arxiv, "Search", lambda *a, **kw: None)
    monkeypatch.setattr(search_arxiv.arxiv, "Client", lambda *a, **kw: FakeClient())
    # Freeze "current year" so the filter is deterministic.
    monkeypatch.setattr(search_arxiv, "current_year", lambda: 2026)

    rc = search_arxiv.main(["--query", "x", "--top", "5", "--years", "3"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    titles = [d["title"] for d in data]
    assert titles == ["New"]


def test_search_arxiv_network_error_exits_nonzero(monkeypatch, capsys):
    from scripts import search_arxiv

    class FakeClient:
        def results(self, search):
            raise ConnectionError("boom")

    monkeypatch.setattr(search_arxiv.arxiv, "Search", lambda *a, **kw: None)
    monkeypatch.setattr(search_arxiv.arxiv, "Client", lambda *a, **kw: FakeClient())
    monkeypatch.setattr(search_arxiv.time, "sleep", lambda s: None)

    rc = search_arxiv.main(["--query", "x", "--top", "2"])
    assert rc != 0
    assert "boom" in capsys.readouterr().err
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_arxiv.py -v
```
Expected: FAIL with `ModuleNotFoundError: scripts.search_arxiv`.

- [ ] **Step 3: Implement `search_arxiv.py`**

Path: `paper-search/scripts/search_arxiv.py`
```python
"""Search arXiv. Emits a JSON array of Paper records on stdout."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
import time

import arxiv

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
        except Exception as e:  # arxiv lib raises a few distinct exceptions
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_arxiv.py -v
```
Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/dgu/skill_paper_search
git add paper-search/scripts/search_arxiv.py paper-search/tests/test_arxiv.py
git commit -m "feat: add arXiv search script with year filter and retry"
```

---

## Task 4: OpenReview Search Script

**Files:**
- Create: `paper-search/tests/test_openreview.py`
- Create: `paper-search/scripts/search_openreview.py`

Uses `openreview.api.OpenReviewClient` (API v2) anonymously. Given a `--venue` (e.g., `NeurIPS.cc`), uses `search_notes(term=query, group=<venue>)`, filters by year if requested, maps to `Paper`.

- [ ] **Step 1: Write the failing tests**

Path: `paper-search/tests/test_openreview.py`
```python
import json
from unittest.mock import MagicMock


def _fake_note(title="T", authors=("A B",), abstract="abs", year=2024,
               forum_id="xyz", venue="NeurIPS 2024 Conference", pdf="/pdf/xyz"):
    n = MagicMock()
    n.content = {
        "title": {"value": title},
        "authors": {"value": list(authors)},
        "abstract": {"value": abstract},
        "venue": {"value": venue},
        "pdf": {"value": pdf},
    }
    n.pdate = None
    n.cdate = int(__import__("datetime").datetime(year, 6, 1).timestamp() * 1000)
    n.forum = forum_id
    n.id = forum_id
    return n


def test_search_openreview_main_prints_json(monkeypatch, capsys):
    from scripts import search_openreview

    notes = [_fake_note(title="Paper A", forum_id="a1"),
             _fake_note(title="Paper B", forum_id="b1")]

    fake_client = MagicMock()
    fake_client.search_notes.return_value = notes

    monkeypatch.setattr(search_openreview, "make_client", lambda: fake_client)

    rc = search_openreview.main(["--query", "reasoning", "--top", "2",
                                  "--venue", "NeurIPS.cc"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data) == 2
    assert data[0]["title"] == "Paper A"
    assert data[0]["source"] == "openreview"
    assert data[0]["venue"] == "NeurIPS"   # stripped from "NeurIPS 2024 Conference"
    assert data[0]["year"] == 2024
    assert data[0]["authors"] == ["A B"]
    assert data[0]["url"].endswith("forum?id=a1")


def test_search_openreview_filters_workshop_into_venue(monkeypatch, capsys):
    from scripts import search_openreview

    notes = [_fake_note(title="W", forum_id="w1",
                        venue="NeurIPS 2024 Workshop on X")]
    fake_client = MagicMock()
    fake_client.search_notes.return_value = notes
    monkeypatch.setattr(search_openreview, "make_client", lambda: fake_client)

    rc = search_openreview.main(["--query", "x", "--top", "1",
                                  "--venue", "NeurIPS.cc"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data[0]["venue"] == "workshop"


def test_search_openreview_year_filter(monkeypatch, capsys):
    from scripts import search_openreview

    notes = [_fake_note(title="Old", forum_id="o1", year=2018),
             _fake_note(title="New", forum_id="n1", year=2024)]
    fake_client = MagicMock()
    fake_client.search_notes.return_value = notes
    monkeypatch.setattr(search_openreview, "make_client", lambda: fake_client)
    monkeypatch.setattr(search_openreview, "current_year", lambda: 2026)

    rc = search_openreview.main(["--query", "x", "--top", "5",
                                  "--venue", "NeurIPS.cc", "--years", "3"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert [d["title"] for d in data] == ["New"]


def test_search_openreview_error_returns_nonzero(monkeypatch, capsys):
    from scripts import search_openreview

    fake_client = MagicMock()
    fake_client.search_notes.side_effect = RuntimeError("api down")
    monkeypatch.setattr(search_openreview, "make_client", lambda: fake_client)

    rc = search_openreview.main(["--query", "x", "--top", "2",
                                  "--venue", "NeurIPS.cc"])
    assert rc != 0
    assert "api down" in capsys.readouterr().err
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_openreview.py -v
```
Expected: FAIL with `ModuleNotFoundError: scripts.search_openreview`.

- [ ] **Step 3: Implement `search_openreview.py`**

Path: `paper-search/scripts/search_openreview.py`
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_openreview.py -v
```
Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/dgu/skill_paper_search
git add paper-search/scripts/search_openreview.py paper-search/tests/test_openreview.py
git commit -m "feat: add OpenReview search script with venue and workshop handling"
```

---

## Task 5: Google Scholar Search Script

**Files:**
- Create: `paper-search/tests/test_gscholar.py`
- Create: `paper-search/scripts/search_gscholar.py`

Uses `scholarly`. Google Scholar is fragile: one retry, fail fast with clear error.

- [ ] **Step 1: Write the failing tests**

Path: `paper-search/tests/test_gscholar.py`
```python
import json
from unittest.mock import MagicMock


def _fake_publication(title="T", authors=("Jane Smith",), year=2024,
                     venue="NeurIPS", abstract="abs", url="http://g/p"):
    return {
        "bib": {
            "title": title,
            "author": " and ".join(authors),
            "pub_year": str(year),
            "venue": venue,
            "abstract": abstract,
        },
        "pub_url": url,
        "eprint_url": None,
    }


def test_gscholar_main_prints_json(monkeypatch, capsys):
    from scripts import search_gscholar

    fake = [_fake_publication(title="A"), _fake_publication(title="B")]
    monkeypatch.setattr(search_gscholar, "run_search",
                        lambda query, top: fake)

    rc = search_gscholar.main(["--query", "reasoning", "--top", "2"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data) == 2
    assert data[0]["title"] == "A"
    assert data[0]["source"] == "gscholar"
    assert data[0]["authors"] == ["Jane Smith"]
    assert data[0]["venue"] == "NeurIPS"
    assert data[0]["year"] == 2024


def test_gscholar_blocked_fails_loudly(monkeypatch, capsys):
    from scripts import search_gscholar

    calls = {"n": 0}

    def blocked(query, top):
        calls["n"] += 1
        raise search_gscholar.BlockedError("429 from Google Scholar")

    monkeypatch.setattr(search_gscholar, "run_search", blocked)

    rc = search_gscholar.main(["--query", "x", "--top", "3"])
    assert rc != 0
    err = capsys.readouterr().err
    assert "blocked" in err.lower()
    assert calls["n"] == 2  # initial + 1 retry


def test_gscholar_year_filter(monkeypatch, capsys):
    from scripts import search_gscholar

    fake = [_fake_publication(title="Old", year=2018),
            _fake_publication(title="New", year=2024)]
    monkeypatch.setattr(search_gscholar, "run_search",
                        lambda query, top: fake)
    monkeypatch.setattr(search_gscholar, "current_year", lambda: 2026)

    rc = search_gscholar.main(["--query", "x", "--top", "5", "--years", "3"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert [d["title"] for d in data] == ["New"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_gscholar.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `search_gscholar.py`**

Path: `paper-search/scripts/search_gscholar.py`
```python
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

from scholarly import scholarly
from scholarly._proxy_generator import MaxTriesExceededException

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
    authors = [a.strip() for a in author_raw.split(" and ") if a.strip()]
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_gscholar.py -v
```
Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/dgu/skill_paper_search
git add paper-search/scripts/search_gscholar.py paper-search/tests/test_gscholar.py
git commit -m "feat: add Google Scholar search script with block detection"
```

---

## Task 6: Dedupe & Classify Script

**Files:**
- Create: `paper-search/tests/test_dedupe.py`
- Create: `paper-search/scripts/dedupe.py`

Reads a JSON array from stdin (combined results from all sources). Applies **venue-wins** merge by `dedup_key`. Classifies each surviving record into `<venue>` / `arxiv_only` / `workshop`. Emits a JSON object mapping category → list of papers on stdout.

- [ ] **Step 1: Write the failing tests**

Path: `paper-search/tests/test_dedupe.py`
```python
import io
import json

from scripts.common import Paper


def _p(**kw) -> dict:
    base = dict(title="T", authors=["A B"], year=2024, venue=None,
                abstract="", url="u", pdf_url=None,
                arxiv_id=None, doi=None, source="arxiv")
    base.update(kw)
    return Paper(**base).to_dict()


def run_dedupe(input_papers, argv=None, monkeypatch=None, capsys=None):
    from scripts import dedupe as mod
    payload = json.dumps(input_papers)
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    rc = mod.main(argv or [])
    out = capsys.readouterr().out
    return rc, json.loads(out)


def test_dedupe_venue_wins_over_arxiv(monkeypatch, capsys):
    papers = [
        _p(title="Same Paper", authors=["Jane Smith"], year=2024,
           venue=None, arxiv_id="2401.1", source="arxiv",
           url="http://arxiv.org/abs/2401.1"),
        _p(title="Same Paper", authors=["Jane Smith"], year=2024,
           venue="NeurIPS", arxiv_id=None, source="openreview",
           url="https://openreview.net/forum?id=abc"),
    ]
    rc, result = run_dedupe(papers, monkeypatch=monkeypatch, capsys=capsys)
    assert rc == 0
    # Exactly one paper, under NeurIPS
    assert "NeurIPS" in result
    assert len(result["NeurIPS"]) == 1
    assert result["NeurIPS"][0]["venue"] == "NeurIPS"
    # arXiv URL carried over
    assert "http://arxiv.org/abs/2401.1" in result["NeurIPS"][0].get("alt_urls", [])


def test_dedupe_arxiv_only_category(monkeypatch, capsys):
    papers = [
        _p(title="Only Preprint", authors=["Al Bee"], year=2025,
           venue=None, arxiv_id="2501.9", source="arxiv",
           url="http://arxiv.org/abs/2501.9"),
    ]
    rc, result = run_dedupe(papers, monkeypatch=monkeypatch, capsys=capsys)
    assert rc == 0
    assert "arxiv_only" in result
    assert len(result["arxiv_only"]) == 1


def test_dedupe_workshop_category(monkeypatch, capsys):
    papers = [
        _p(title="Workshop Paper", venue="workshop", source="openreview",
           url="https://openreview.net/forum?id=w1"),
    ]
    rc, result = run_dedupe(papers, monkeypatch=monkeypatch, capsys=capsys)
    assert rc == 0
    assert "workshop" in result
    assert len(result["workshop"]) == 1


def test_dedupe_same_title_different_authors_are_distinct(monkeypatch, capsys):
    papers = [
        _p(title="Attention Is All You Need", authors=["Ashish Vaswani"],
           year=2017, venue=None, arxiv_id="1706.03762", source="arxiv",
           url="http://arxiv.org/abs/1706.03762"),
        _p(title="Attention Is All You Need", authors=["Someone Else"],
           year=2024, venue=None, arxiv_id="9999.9999", source="arxiv",
           url="http://arxiv.org/abs/9999.9999"),
    ]
    rc, result = run_dedupe(papers, monkeypatch=monkeypatch, capsys=capsys)
    assert rc == 0
    assert len(result["arxiv_only"]) == 2


def test_dedupe_preserves_arxiv_id_when_merging(monkeypatch, capsys):
    papers = [
        _p(title="Dup", authors=["X Y"], year=2024, arxiv_id="2401.1",
           source="arxiv", url="http://arxiv.org/abs/2401.1"),
        _p(title="Dup", authors=["X Y"], year=2024, venue="ICLR",
           source="openreview", url="https://openreview.net/forum?id=z"),
    ]
    rc, result = run_dedupe(papers, monkeypatch=monkeypatch, capsys=capsys)
    assert rc == 0
    merged = result["ICLR"][0]
    assert merged["arxiv_id"] == "2401.1"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_dedupe.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `dedupe.py`**

Path: `paper-search/scripts/dedupe.py`
```python
"""Merge paper lists, apply venue-wins dedup, classify into categories.

Input : JSON array of Paper dicts on stdin.
Output: JSON object {category: [paper dicts with optional alt_urls]} on stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Iterable

from scripts.common import Paper, dedup_key


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

    for p in papers:
        k = dedup_key(p)
        if k not in best:
            best[k] = p
            alts[k] = []
            continue
        current = best[k]
        if _SOURCE_PRIORITY[p.source] > _SOURCE_PRIORITY[current.source]:
            merged, extra = _merge(p, current)
        else:
            merged, extra = _merge(current, p)
        best[k] = merged
        alts[k].extend(extra)

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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_dedupe.py -v
```
Expected: all 5 tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```
Expected: all unit tests PASS (15+ tests total).

- [ ] **Step 6: Commit**

```bash
cd /home/dgu/skill_paper_search
git add paper-search/scripts/dedupe.py paper-search/tests/test_dedupe.py
git commit -m "feat: add dedupe/classify script with venue-wins merging"
```

---

## Task 7: Integration Test (arXiv real network)

**Files:**
- Create: `paper-search/tests/test_integration.py`

Single integration test that hits the real arXiv API. Marked `integration` so it's skipped by default but runnable via `pytest -m integration`.

- [ ] **Step 1: Write the test**

Path: `paper-search/tests/test_integration.py`
```python
import json

import pytest

from scripts import search_arxiv


@pytest.mark.integration
def test_real_arxiv_search(capsys):
    rc = search_arxiv.main(["--query", "transformer attention", "--top", "3"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert isinstance(data, list)
    for d in data:
        assert "title" in d and d["source"] == "arxiv"
        assert "authors" in d and isinstance(d["authors"], list)
```

- [ ] **Step 2: Verify default run skips it**

```bash
pytest -v
```
Expected: `test_real_arxiv_search` is deselected (not run).

- [ ] **Step 3: Run the integration test explicitly**

```bash
pytest -m integration -v
```
Expected: PASS (real network).

- [ ] **Step 4: Commit**

```bash
cd /home/dgu/skill_paper_search
git add paper-search/tests/test_integration.py
git commit -m "test: add opt-in arXiv integration test"
```

---

## Task 8: venues.yaml

**Files:**
- Create: `paper-search/config/venues.yaml`

Final venue list based on the spec. The user may extend this before or after install; the skill reads it at runtime.

- [ ] **Step 1: Write `venues.yaml`**

Path: `paper-search/config/venues.yaml`
```yaml
# Target venues for paper-search.
# Entries with openreview_id are queried via search_openreview.py;
# others are picked up from arxiv / gscholar results only.

venues:
  - { name: NeurIPS, openreview_id: NeurIPS.cc }
  - { name: ICLR,    openreview_id: ICLR.cc }
  - { name: ICML,    openreview_id: ICML.cc }
  - { name: COLM,    openreview_id: colmweb.org }
  - { name: ACL }
  - { name: EMNLP }
  - { name: NAACL }
  - { name: CVPR }
  - { name: ICCV }
  - { name: ECCV }
  - { name: AAAI }

special_categories:
  - arxiv_only
  - workshop
```

- [ ] **Step 2: Commit**

```bash
cd /home/dgu/skill_paper_search
git add paper-search/config/venues.yaml
git commit -m "chore: add venues.yaml with ML/AI top venues"
```

---

## Task 9: Query Generation Reference

**Files:**
- Create: `paper-search/references/query_generation.md`

Reference Claude reads during step 2 of the pipeline. Concise — principles + examples, no boilerplate.

- [ ] **Step 1: Write `query_generation.md`**

Path: `paper-search/references/query_generation.md`
```markdown
# Generating Paper Search Queries

## Goal

Produce **2–4 English queries** that collectively cover the project's central
topic. Each query is a phrase, not a question. They are sent verbatim to
arXiv / OpenReview / Google Scholar keyword search.

## Principles

1. **Be concrete.** "reasoning" is too broad; "chain-of-thought reasoning
   distillation small language models" is searchable.
2. **Cover multiple angles.** If the project has a method and a benchmark,
   make one query per angle.
3. **Prefer the terminology a paper author would use.** e.g.,
   "retrieval-augmented generation" > "RAG with extra knowledge".
4. **Drop stop words.** No "the", "a", "how to".
5. **Keep each query 3–10 content words.**

## Good examples

- `chain-of-thought reasoning distillation small language models`
- `tool-augmented LLM agent planning benchmark`
- `constrained decoding structured output LLM`
- `retrieval-augmented generation long context evaluation`

## Bad examples (and why)

- `LLM` — too broad, will flood with unrelated work.
- `how do I distill reasoning into smaller models` — natural-language,
  search engines down-weight filler words.
- `Chen et al 2024 method` — cites a specific author; use the concept.

## When to ask the user first

If the working-directory signal is weak or mixes unrelated topics, present
the draft analysis and query list for one-time confirmation before running
the search (see `SKILL.md` §Ambiguity Gate).
```

- [ ] **Step 2: Commit**

```bash
cd /home/dgu/skill_paper_search
git add paper-search/references/query_generation.md
git commit -m "docs: add query generation reference"
```

---

## Task 10: SKILL.md (Main Procedure)

**Files:**
- Create: `paper-search/SKILL.md`

Claude's entry point. Frontmatter + ordered procedure covering the six pipeline stages, error handling, and output contract. Kept focused — implementation detail stays in the scripts.

- [ ] **Step 1: Write `SKILL.md`**

Path: `paper-search/SKILL.md`
```markdown
---
name: paper-search
description: Analyse the current project, search arXiv + OpenReview + Google Scholar for related papers, and write a venue-organised related-work directory. Use when the user runs /paper-search or asks to find papers related to the current project.
---

# paper-search

Given a research project in the current working directory (or a text
description from the user), build `./papers/` containing per-venue
Markdown indexes and per-paper summaries.

## Prerequisites

The skill bundles Python scripts that require `arxiv`, `openreview-py`,
`scholarly`, and `pyyaml`. If `python -c "import arxiv, openreview, scholarly, yaml"`
fails, tell the user to run:

    cd <skill-dir> && python -m venv .venv && source .venv/bin/activate \
        && pip install -r requirements.txt

and stop until they confirm.

## Arguments

Parse from the user's invocation:

| Arg | Default | Notes |
|-----|---------|-------|
| `--top N` | 10 | Max per category after ranking |
| `--years Y` | none | Restrict to last Y years |
| `--output <path>` | `./papers/` | Output root |
| `--venues <csv>` | all in `config/venues.yaml` | Restrict venues |
| `--force` | off | Overwrite without prompt |

Free-form topic override (no flag): `/paper-search "topic phrase"` — use
the phrase as the project description instead of reading the directory.

## Pipeline

### 1. Context gathering

Read the working directory: `README.md`, `docs/`, top-level source files,
any notes. If content is sparse (< ~200 words of signal), ask the user for
a 2–3 sentence project description.

### 2. Analysis & query generation

Analyse the context freely and produce 2–4 English queries per
`references/query_generation.md`. Write them to a temp file or keep them in
memory for step 3.

**Ambiguity gate:** if the context signals multiple unrelated topics (e.g.,
CV + NLP + systems all in one repo), show the user your draft analysis and
queries, and wait for confirmation before continuing.

### 3. Parallel search

Load `config/venues.yaml`. For each query Q, launch in parallel:

- `python scripts/search_arxiv.py --query "Q" --top <top*2>`
- For each venue V with `openreview_id`:
  `python scripts/search_openreview.py --query "Q" --top <top*2> --venue <openreview_id>`
- `python scripts/search_gscholar.py --query "Q" --top <top*2>`

Apply `--years` if specified. Concurrency caps: arXiv ≤ 3, OpenReview ≤ 2,
Google Scholar ≤ 1. Collect all stdouts; concatenate JSON arrays into one
combined array. Warn (do not abort) on per-source failures; abort only if
every source fails.

### 4. Dedupe & classify

Pipe the combined array into `dedupe.py`:

    echo "<combined.json>" | python scripts/dedupe.py

Receive `{category: [paper, ...]}` back. Categories that are not in
`venues.yaml` (i.e., venues learned only from arXiv/gscholar metadata that
don't match our list) should be folded into `arxiv_only`.

### 5. Relevance ranking

For each category, read titles + abstracts and pick the top N (default 10)
most relevant to the project context and original queries. Drop the rest.

### 6. Output

Root = `--output` (default `./papers/`). If it exists and `--force` is off,
ask the user before overwriting.

Create:

    papers/
      README.md               # project summary (Korean), queries (English),
                              # per-venue counts, run metadata
      <venue>/
        index.md              # Markdown table: # | Title | Year | Authors | 관련성
        refs.bib              # all BibTeX entries, concatenated
        YYYY-<firstauthor>-<slug>.md   # per paper, see template below

Categories with zero selected papers: no directory created; count 0 in
README table.

### Per-paper template

```markdown
# <Title>

**Authors:** <comma-separated>
**Venue:** <Venue Year>
**Links:** [OpenReview](...) · [arXiv](...) · [PDF](...)

## Abstract
<English abstract, verbatim>

## 한줄 요약
<Korean, 1 sentence>

## 왜 이 프로젝트와 관련 있는가
<Korean, 2–4 sentences referencing specific aspects of the project>

## BibTeX
​```bibtex
@inproceedings{...}
​```
```

Use the `title_slug` and `first_author_lastname` helpers from
`scripts/common.py` for filename generation if you shell out to Python; or
reproduce their logic directly (lowercase, punctuation stripped, hyphens,
≤ 60 chars).

## Failure reporting

End the run with a short status summary: which sources returned data,
which were blocked, per-venue counts. If Google Scholar was blocked,
say so plainly — the user needs to know that category may be under-covered.
```

- [ ] **Step 2: Commit**

```bash
cd /home/dgu/skill_paper_search
git add paper-search/SKILL.md
git commit -m "feat: add SKILL.md orchestrating the paper-search pipeline"
```

---

## Task 11: Manual Smoke Test

**Files:** (no new files — verification only)

- [ ] **Step 1: Build a fixture project**

```bash
mkdir -p /tmp/paper-search-smoke
cat > /tmp/paper-search-smoke/README.md <<'EOF'
# Project: CoT distillation for small LMs

We're studying whether chain-of-thought traces from large models can be
distilled into sub-3B parameter language models for multi-step reasoning
benchmarks.
EOF
```

- [ ] **Step 2: Run the full pipeline manually**

From within `/tmp/paper-search-smoke/`, invoke each script stage as Claude
would:

```bash
cd /home/dgu/skill_paper_search/paper-search
source .venv/bin/activate
python scripts/search_arxiv.py --query "chain-of-thought distillation small language models" --top 5 > /tmp/arxiv.json
python scripts/search_openreview.py --query "chain-of-thought distillation small language models" --top 5 --venue NeurIPS.cc > /tmp/or_neurips.json
jq -s 'add' /tmp/arxiv.json /tmp/or_neurips.json | python scripts/dedupe.py > /tmp/deduped.json
```

Expected: `/tmp/deduped.json` is valid JSON with keys including `NeurIPS`
and/or `arxiv_only`.

- [ ] **Step 3: End-to-end skill invocation**

Start Claude Code in `/tmp/paper-search-smoke/` (after Task 12 install)
and run `/paper-search --top 3`. Verify:
- `papers/README.md` exists with project summary + queries.
- At least one venue directory contains `index.md`, one paper `.md`, `refs.bib`.
- Per-paper file has all six sections filled.

- [ ] **Step 4: Record smoke test results (no commit needed unless fixes found)**

If a fix is needed, create a follow-up task; otherwise this step is
complete when the checks pass.

---

## Task 12: Install & Documentation

**Files:**
- Modify: `/home/dgu/skill_paper_search/README.md`

- [ ] **Step 1: Symlink the skill**

```bash
mkdir -p ~/.claude/skills
ln -s /home/dgu/skill_paper_search/paper-search ~/.claude/skills/paper-search
ls -la ~/.claude/skills/paper-search
```
Expected: symlink resolves to the repo path.

- [ ] **Step 2: Verify Claude Code picks it up**

Open a fresh Claude Code session; confirm the system-reminder lists
`paper-search` as an available skill.

- [ ] **Step 3: Expand README with usage**

Path: `/home/dgu/skill_paper_search/README.md`

Append an `## Usage` section:
```markdown
## Usage

Inside Claude Code, in any project directory:

    /paper-search                        # default: top 10 per venue
    /paper-search --top 15 --years 3     # restrict by recency
    /paper-search "LLM agent planning"   # explicit topic override

Output lands in `./papers/<venue>/` with per-paper `.md`, `index.md`, and
`refs.bib`.

## Development

    cd paper-search
    source .venv/bin/activate
    pytest                       # unit tests
    pytest -m integration        # opt-in, hits arXiv
```

- [ ] **Step 4: Commit**

```bash
cd /home/dgu/skill_paper_search
git add README.md
git commit -m "docs: add usage and development instructions"
```

---

## Self-Review

**Spec coverage check:**
- §1 Purpose → Tasks 2–12 collectively implement it.
- §2 Scope (in/out) → In-scope items covered; out-of-scope (PDF, citation graph, Semantic Scholar, scheduling) not implemented.
- §3 Invocation (args, natural language, topic override) → Task 10 (SKILL.md).
- §4 Skill package layout → Task 1 scaffolds; Tasks 2–10 populate.
- §4.1 Script I/O contract → Enforced by Paper schema (Task 2) + CLI in each script (Tasks 3–5).
- §4.2 venues.yaml → Task 8.
- §5 Pipeline (6 stages) → Task 10 (orchestration) + Tasks 3–6 (individual stages).
- §6 Output layout (tree, README, index.md, per-paper template, refs.bib, naming, idempotency) → Task 10.
- §7 Error handling (per-source failure, zero results, ambiguity gate, total failure, rate limits) → Tasks 3–5 (per-source) + Task 10 (orchestration-level behaviour).
- §8 Testing → Tasks 2–7.
- §9 Open items → venues finalised (Task 8), Python minimum noted in plan header (≥ 3.10), `SKILL.md` shape defined (Task 10).

**Placeholder scan:** No "TBD", "TODO", "fill in later", or "add appropriate error handling". Each step contains concrete code or a concrete command.

**Type consistency:** `Paper` dataclass field names used consistently across `common.py`, `search_*.py`, `dedupe.py`, and test fixtures. Helper signatures (`normalize_title`, `title_slug`, `first_author_lastname`, `dedup_key`) match their test usage. `make_client` is defined and monkeypatched under the same name. `current_year` is stubbed identically in each script's tests.
