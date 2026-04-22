"""Tests for scripts.build_paper_folder — unified per-paper folder builder."""
import json
from pathlib import Path

import pytest


def _paper(**kw) -> dict:
    base = dict(
        title="Attention Is All You Need",
        authors=["Ashish Vaswani", "et al."],
        year=2017,
        venue="NeurIPS",
        abstract="",
        url="",
        pdf_url=None,
        arxiv_id="1706.03762",
        doi=None,
        source="arxiv",
    )
    base.update(kw)
    return base


def test_folder_name_pattern_with_method(tmp_path):
    from scripts.build_paper_folder import folder_name

    p = _paper()
    assert folder_name(p, index=1, method="TRANSFORMER") \
        == "01_vaswani2017TRANSFORMER(NeurIPS2017)"


def test_folder_name_pattern_without_method(tmp_path):
    from scripts.build_paper_folder import folder_name

    p = _paper()
    assert folder_name(p, index=3, method=None) \
        == "03_vaswani2017(NeurIPS2017)"


def test_folder_name_defaults_to_arxiv_preprint(tmp_path):
    from scripts.build_paper_folder import folder_name

    p = _paper(venue=None)
    assert folder_name(p, index=5, method="LoRA") \
        == "05_vaswani2017LoRA(preprint2017)"


def test_folder_name_handles_comma_authors(tmp_path):
    from scripts.build_paper_folder import folder_name

    p = _paper(authors=["Smith, Jane"], year=2024, venue="ICLR")
    assert folder_name(p, index=1, method="X") == "01_smith2024X(ICLR2024)"


def test_build_writes_paper_meta_json(tmp_path, monkeypatch):
    from scripts import build_paper_folder as mod

    p = _paper()
    fake_pdf = tmp_path / "cache.pdf"
    fake_pdf.write_bytes(b"%PDF-fake")

    monkeypatch.setattr(mod, "_download_pdf",
                        lambda paper, cache: fake_pdf)
    monkeypatch.setattr(mod, "_extract",
                        lambda pdf, out: {
                            "pages": 5,
                            "main_figures": 2,
                            "appendix_figures": 0,
                            "figures": [],
                            "raw_md": str(out / "raw.md"),
                            "pdf_path": str(pdf),
                            "out_dir": str(out),
                            "boundary_page": 6,
                        })

    result = mod.build(p, tmp_path, index=1, method="TRANSFORMER")

    folder = tmp_path / "01_vaswani2017TRANSFORMER(NeurIPS2017)"
    assert folder.is_dir()
    meta = json.loads((folder / "paper_meta.json").read_text())
    assert meta["title"] == p["title"]
    assert meta["folder"] == folder.name
    assert meta["index"] == 1
    assert meta["method"] == "TRANSFORMER"
    assert result["folder"] == str(folder)
    assert result["pages"] == 5


def test_build_returns_empty_on_download_failure(tmp_path, monkeypatch):
    from scripts import build_paper_folder as mod

    p = _paper()
    monkeypatch.setattr(mod, "_download_pdf", lambda paper, cache: None)

    result = mod.build(p, tmp_path, index=1, method="X")
    assert result.get("status") == "failed"
    assert "reason" in result


def test_build_cleans_up_pdf_cache_by_default(tmp_path, monkeypatch):
    from scripts import build_paper_folder as mod

    p = _paper()
    cache_file = tmp_path / "cache_test.pdf"
    cache_file.write_bytes(b"%PDF-")

    def fake_dl(paper, cache_dir):
        # Put a file inside cache_dir so cleanup can be observed
        dest = Path(cache_dir) / "downloaded.pdf"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"%PDF-")
        return dest

    monkeypatch.setattr(mod, "_download_pdf", fake_dl)
    monkeypatch.setattr(mod, "_extract",
                        lambda pdf, out: {
                            "pages": 1, "main_figures": 0, "appendix_figures": 0,
                            "figures": [], "raw_md": str(out / "raw.md"),
                            "pdf_path": str(pdf), "out_dir": str(out),
                            "boundary_page": 2,
                        })

    mod.build(p, tmp_path, index=1, method="X", keep_pdf=False)

    # Cache should be gone (default)
    assert not (tmp_path / "01_vaswani2017X(NeurIPS2017)" / ".pdf_cache").exists()


def test_main_reads_paper_json(tmp_path, monkeypatch, capsys):
    from scripts import build_paper_folder as mod

    paper_file = tmp_path / "paper.json"
    paper_file.write_text(json.dumps(_paper()))

    monkeypatch.setattr(mod, "_download_pdf",
                        lambda paper, cache: tmp_path / "pdf.pdf")
    (tmp_path / "pdf.pdf").write_bytes(b"%PDF-")
    monkeypatch.setattr(mod, "_extract",
                        lambda pdf, out: {
                            "pages": 3, "main_figures": 1, "appendix_figures": 0,
                            "figures": [{"fname": "fig1.png", "page": 1,
                                         "orig_num": 1, "caption": "c",
                                         "source": "image", "is_appx": False,
                                         "warn": None}],
                            "raw_md": str(out / "raw.md"),
                            "pdf_path": str(pdf), "out_dir": str(out),
                            "boundary_page": 4,
                        })

    rc = mod.main([
        "--paper", str(paper_file),
        "--out-dir", str(tmp_path / "out"),
        "--index", "2",
        "--method", "TEST",
    ])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["folder"].endswith("02_vaswani2017TEST(NeurIPS2017)")
    assert data["main_figures"] == 1
