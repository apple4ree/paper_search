"""Tests for scripts.extract_paper_content — full paper-package extraction."""
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "sample_paper.pdf"


@pytest.fixture(autouse=True)
def fixture_exists():
    assert FIXTURE.exists(), "fixture PDF missing"


def test_returns_summary_dict(tmp_path):
    from scripts.extract_paper_content import extract

    result = extract(FIXTURE, tmp_path)
    assert result["pdf_path"] == str(FIXTURE)
    assert result["out_dir"] == str(tmp_path)
    assert result["pages"] == 2
    assert result["main_figures"] >= 1
    assert isinstance(result["figures"], list)
    assert len(result["figures"]) >= 1


def test_writes_raw_md(tmp_path):
    from scripts.extract_paper_content import extract

    extract(FIXTURE, tmp_path)
    raw_md = (tmp_path / "raw.md").read_text()
    assert "Figure index" in raw_md
    assert "## p. 1" in raw_md
    assert "![fig1.png](figures/fig1.png)" in raw_md


def test_writes_page_fallback_images(tmp_path):
    from scripts.extract_paper_content import extract

    extract(FIXTURE, tmp_path)
    assert (tmp_path / "figures" / "_pages" / "p-01.png").exists()
    assert (tmp_path / "figures" / "_pages" / "p-02.png").exists()


def test_figure_files_match_figures_list(tmp_path):
    from scripts.extract_paper_content import extract

    result = extract(FIXTURE, tmp_path)
    for rec in result["figures"]:
        path = tmp_path / "figures" / rec["fname"]
        assert path.exists()
        assert path.stat().st_size > 0


def test_caption_text_contains_original(tmp_path):
    from scripts.extract_paper_content import extract

    result = extract(FIXTURE, tmp_path)
    captions = " ".join(r["caption"] for r in result["figures"])
    assert "Architecture" in captions or "Main results" in captions


def test_print_metadata_outputs_key_equals_value(tmp_path, capsys):
    from scripts.extract_paper_content import print_metadata

    print_metadata(FIXTURE)
    out = capsys.readouterr().out
    assert "pages=" in out
    assert "first_page_head=" in out


def test_cli_metadata_only_mode(tmp_path, capsys):
    from scripts import extract_paper_content as mod

    rc = mod.main(["--metadata-only", str(FIXTURE)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "pages=" in out


def test_diagnostics_go_to_stderr_not_stdout(tmp_path, capsys):
    """Logging must not corrupt stdout — downstream pipes (JSON) depend on it."""
    from scripts.extract_paper_content import extract

    extract(FIXTURE, tmp_path)
    cap = capsys.readouterr()
    assert "[info]" not in cap.out
    assert "[done]" not in cap.out
    assert "[info]" in cap.err
    assert "[done]" in cap.err


def test_appendix_boundary_detection(tmp_path):
    """A References heading on page 2 shifts the boundary."""
    import fitz

    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 50), "Title", fontsize=12)
    rect = fitz.Rect(72, 100, 272, 200)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 40, 30))
    pix.set_rect(fitz.IRect(0, 0, 40, 30), (120, 120, 120))
    p1.insert_image(rect, stream=pix.tobytes("png"))
    p1.insert_text((72, 220), "Figure 1: Main figure.", fontsize=10)

    p2 = doc.new_page()
    p2.insert_text((72, 50), "References", fontsize=14)
    rect2 = fitz.Rect(72, 100, 272, 200)
    p2.insert_image(rect2, stream=pix.tobytes("png"))
    p2.insert_text((72, 220), "Figure 2: Appendix figure.", fontsize=10)

    pdf = tmp_path / "src.pdf"
    doc.save(pdf)
    doc.close()

    from scripts.extract_paper_content import extract
    result = extract(pdf, tmp_path / "out")

    assert result["main_figures"] == 1
    assert result["appendix_figures"] == 1
    assert (tmp_path / "out" / "figures" / "fig1.png").exists()
    assert (tmp_path / "out" / "figures" / "figA1.png").exists()
