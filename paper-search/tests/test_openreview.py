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
