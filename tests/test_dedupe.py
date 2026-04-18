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
