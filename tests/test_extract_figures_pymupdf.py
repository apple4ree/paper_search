"""Tests for scripts.extract_figures_pymupdf (approach A)."""
import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "sample_paper.pdf"


@pytest.fixture(autouse=True)
def fixture_exists():
    assert FIXTURE.exists(), "fixture PDF missing — run tests/build_fixture.py"


def test_extracts_two_figures(tmp_path):
    from scripts.extract_figures_pymupdf import extract

    figures = extract(FIXTURE, tmp_path)

    assert len(figures) == 2
    for fig in figures:
        assert Path(fig["image_path"]).exists()
        assert Path(fig["image_path"]).stat().st_size > 0
        assert fig["page"] in (1, 2)
        assert fig["number"] in (1, 2)


def test_captions_match_figure_numbers(tmp_path):
    from scripts.extract_figures_pymupdf import extract

    figures = extract(FIXTURE, tmp_path)
    by_num = {f["number"]: f for f in figures}

    assert "Architecture" in by_num[1]["caption"]
    assert "Main results" in by_num[2]["caption"]


def test_writes_caption_sidecar(tmp_path):
    from scripts.extract_figures_pymupdf import extract

    figures = extract(FIXTURE, tmp_path)
    for fig in figures:
        cap_path = Path(fig["image_path"]).with_suffix(".txt")
        assert cap_path.exists()
        assert cap_path.read_text().strip() == fig["caption"]


def test_main_writes_json_summary(tmp_path, capsys, monkeypatch):
    from scripts import extract_figures_pymupdf as mod

    rc = mod.main(["--pdf", str(FIXTURE), "--out-dir", str(tmp_path)])
    assert rc == 0

    out = capsys.readouterr().out
    data = json.loads(out)
    assert len(data) == 2
    assert all("image_path" in d and "caption" in d and "number" in d for d in data)


def test_no_figures_graceful(tmp_path, monkeypatch):
    """PDF with no images should return empty list, not crash."""
    import fitz
    from scripts.extract_figures_pymupdf import extract

    empty_pdf = tmp_path / "empty.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Text only, no figures.", fontsize=10)
    doc.save(empty_pdf)
    doc.close()

    figures = extract(empty_pdf, tmp_path / "out")
    assert figures == []
