"""Tests for scripts.get_figures — end-to-end orchestrator."""
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def fake_paper():
    return {
        "title": "Sample Paper",
        "authors": ["Jane Smith"],
        "year": 2024,
        "venue": "NeurIPS",
        "abstract": "",
        "url": "",
        "pdf_url": None,
        "arxiv_id": "2401.12345",
        "doi": None,
        "source": "arxiv",
    }


def test_auto_picks_pdffigures_when_jar_available(tmp_path, monkeypatch, fake_paper):
    from scripts import get_figures as mod

    jar = tmp_path / "j.jar"
    jar.write_bytes(b"fake")
    monkeypatch.setenv("PDFFIGURES2_JAR", str(jar))

    monkeypatch.setattr(mod, "download_pdf",
                        lambda paper, dest: tmp_path / "paper.pdf")
    (tmp_path / "paper.pdf").write_bytes(b"%PDF-")

    calls = {"a": 0, "b": 0}
    monkeypatch.setattr(mod, "_extract_pymupdf",
                        lambda pdf, out: (calls.__setitem__("a", calls["a"] + 1) or []))
    monkeypatch.setattr(mod, "_extract_pdffigures",
                        lambda pdf, out: (calls.__setitem__("b", calls["b"] + 1) or [
                            {"page": 1, "number": 1, "caption": "F1", "image_path": "x.png"}
                        ]))

    result = mod.get_figures(fake_paper, tmp_path / "out", method="auto")

    assert calls["b"] == 1
    assert calls["a"] == 0
    assert len(result) == 1


def test_auto_falls_back_to_pymupdf_without_jar(tmp_path, monkeypatch, fake_paper):
    from scripts import get_figures as mod

    monkeypatch.delenv("PDFFIGURES2_JAR", raising=False)
    monkeypatch.setattr(mod, "download_pdf",
                        lambda paper, dest: tmp_path / "paper.pdf")
    (tmp_path / "paper.pdf").write_bytes(b"%PDF-")

    calls = {"a": 0, "b": 0}
    monkeypatch.setattr(mod, "_extract_pymupdf",
                        lambda pdf, out: (calls.__setitem__("a", calls["a"] + 1) or [
                            {"page": 1, "number": 1, "caption": "F", "image_path": "y.png"}
                        ]))
    monkeypatch.setattr(mod, "_extract_pdffigures",
                        lambda pdf, out: (calls.__setitem__("b", calls["b"] + 1) or []))

    result = mod.get_figures(fake_paper, tmp_path / "out", method="auto")

    assert calls["a"] == 1
    assert calls["b"] == 0
    assert len(result) == 1


def test_explicit_method_pymupdf_respected(tmp_path, monkeypatch, fake_paper):
    from scripts import get_figures as mod

    # Even with jar available, method=pymupdf should pick A
    jar = tmp_path / "j.jar"
    jar.write_bytes(b"fake")
    monkeypatch.setenv("PDFFIGURES2_JAR", str(jar))

    monkeypatch.setattr(mod, "download_pdf",
                        lambda paper, dest: tmp_path / "paper.pdf")
    (tmp_path / "paper.pdf").write_bytes(b"%PDF-")

    picked = {"a": 0, "b": 0}
    monkeypatch.setattr(mod, "_extract_pymupdf",
                        lambda pdf, out: (picked.__setitem__("a", 1) or []))
    monkeypatch.setattr(mod, "_extract_pdffigures",
                        lambda pdf, out: (picked.__setitem__("b", 1) or []))

    mod.get_figures(fake_paper, tmp_path / "out", method="pymupdf")

    assert picked["a"] == 1
    assert picked["b"] == 0


def test_returns_empty_when_download_fails(tmp_path, monkeypatch, fake_paper):
    from scripts import get_figures as mod

    monkeypatch.setattr(mod, "download_pdf", lambda paper, dest: None)

    result = mod.get_figures(fake_paper, tmp_path / "out", method="auto")
    assert result == []


def test_main_with_paper_json(tmp_path, monkeypatch, fake_paper, capsys):
    from scripts import get_figures as mod

    paper_file = tmp_path / "paper.json"
    paper_file.write_text(json.dumps(fake_paper))

    monkeypatch.setattr(mod, "download_pdf",
                        lambda paper, dest: tmp_path / "d.pdf")
    (tmp_path / "d.pdf").write_bytes(b"%PDF-")
    monkeypatch.setattr(mod, "_extract_pymupdf",
                        lambda pdf, out: [{"page": 1, "number": 1, "caption": "c", "image_path": "i"}])
    monkeypatch.delenv("PDFFIGURES2_JAR", raising=False)

    rc = mod.main(["--paper", str(paper_file), "--out-dir", str(tmp_path / "out")])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data[0]["caption"] == "c"
