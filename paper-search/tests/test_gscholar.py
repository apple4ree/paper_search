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
    monkeypatch.setattr(search_gscholar.time, "sleep", lambda s: None)

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
