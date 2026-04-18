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
