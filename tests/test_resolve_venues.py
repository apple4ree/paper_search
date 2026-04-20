"""Tests for scripts.resolve_venues — PDF-based venue reclassification."""
import io
import json
from pathlib import Path

import pytest


def _paper(**kw) -> dict:
    base = dict(
        title="T", authors=["A B"], year=2024, venue=None,
        abstract="", url="", pdf_url=None, arxiv_id=None, doi=None, source="arxiv",
    )
    base.update(kw)
    return base


def test_reclassifies_arxiv_only_when_pdf_reveals_venue(tmp_path, monkeypatch):
    from scripts import resolve_venues as mod

    paper = _paper(title="X", arxiv_id="2401.1", source="arxiv")
    deduped = {"arxiv_only": [paper]}

    # Pretend download succeeded and the PDF says ICLR
    monkeypatch.setattr(mod, "_download_pdf",
                        lambda p, cache: Path("/tmp/fake.pdf"))
    monkeypatch.setattr(mod, "detect_venue", lambda pdf: "ICLR")

    out = mod.resolve(deduped)

    assert "arxiv_only" not in out or not out["arxiv_only"]
    assert "ICLR" in out
    assert len(out["ICLR"]) == 1
    assert out["ICLR"][0]["venue"] == "ICLR"
    assert out["ICLR"][0].get("venue_resolution") == "pdf"


def test_keeps_papers_already_in_clean_bucket(tmp_path, monkeypatch):
    from scripts import resolve_venues as mod

    paper = _paper(title="T", venue="NeurIPS", source="openreview")
    deduped = {"NeurIPS": [paper]}

    called = {"n": 0}
    def fake_download(p, cache):
        called["n"] += 1
        return None
    monkeypatch.setattr(mod, "_download_pdf", fake_download)

    out = mod.resolve(deduped)

    # Clean bucket — should NOT attempt PDF fetch
    assert called["n"] == 0
    assert out["NeurIPS"][0]["venue"] == "NeurIPS"


def test_leaves_in_arxiv_only_when_pdf_unresolvable(tmp_path, monkeypatch):
    from scripts import resolve_venues as mod

    paper = _paper(title="T", arxiv_id="2401.9")
    deduped = {"arxiv_only": [paper]}

    monkeypatch.setattr(mod, "_download_pdf", lambda p, cache: None)

    out = mod.resolve(deduped)
    assert out["arxiv_only"][0]["title"] == "T"
    assert "ICLR" not in out


def test_handles_truncated_venue_strings(tmp_path, monkeypatch):
    """Papers with unrecognised venue strings (from gscholar) get re-probed."""
    from scripts import resolve_venues as mod

    paper = _paper(title="T", venue=None, pdf_url="http://x/paper.pdf")
    # Note: the bucket key is the raw gscholar string; paper.venue is None.
    deduped = {"Proceedings of the …": [paper]}

    monkeypatch.setattr(mod, "_download_pdf",
                        lambda p, cache: Path("/tmp/f.pdf"))
    monkeypatch.setattr(mod, "detect_venue", lambda pdf: "ACL")

    out = mod.resolve(deduped)

    assert "ACL" in out
    assert out["ACL"][0]["venue"] == "ACL"
    assert "Proceedings of the …" not in out


def test_respects_ambiguous_bucket_allowlist(tmp_path, monkeypatch):
    """Only buckets classified as ambiguous get re-probed; `workshop` stays."""
    from scripts import resolve_venues as mod

    workshop_paper = _paper(venue="workshop", source="openreview")
    deduped = {"workshop": [workshop_paper]}

    called = {"n": 0}
    monkeypatch.setattr(mod, "_download_pdf",
                        lambda p, cache: (called.__setitem__("n", called["n"] + 1) or None))

    out = mod.resolve(deduped)
    assert called["n"] == 0
    assert "workshop" in out


def test_main_reads_stdin_writes_stdout(tmp_path, monkeypatch, capsys):
    from scripts import resolve_venues as mod

    deduped = {
        "arxiv_only": [_paper(title="X", arxiv_id="2401.1")],
        "NeurIPS": [_paper(title="Y", venue="NeurIPS", source="openreview")],
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(deduped)))
    monkeypatch.setattr(mod, "_download_pdf",
                        lambda p, cache: Path("/tmp/d.pdf"))
    monkeypatch.setattr(mod, "detect_venue", lambda pdf: "ICLR")

    rc = mod.main([])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert "ICLR" in data
    assert "NeurIPS" in data
