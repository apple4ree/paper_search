"""Tests for scripts.venue_from_pdf — PDF-based venue detection."""
from pathlib import Path

import fitz
import pytest


def _make_pdf(tmp_path: Path, header: str, body: str = "Abstract...") -> Path:
    """Build a 1-page PDF with a given header string at the top."""
    doc = fitz.open()
    page = doc.new_page()
    # Header at top of page
    page.insert_text((72, 50), header, fontsize=9, fontname="helv")
    page.insert_text((72, 120), "Paper Title Here", fontsize=16)
    page.insert_text((72, 160), body, fontsize=10)
    out = tmp_path / "sample.pdf"
    doc.save(out)
    doc.close()
    return out


def test_detects_iclr_from_header(tmp_path):
    from scripts.venue_from_pdf import detect_venue

    pdf = _make_pdf(tmp_path, "Published as a conference paper at ICLR 2024")
    assert detect_venue(pdf) == "ICLR"


def test_detects_neurips(tmp_path):
    from scripts.venue_from_pdf import detect_venue

    pdf = _make_pdf(
        tmp_path,
        "37th Conference on Neural Information Processing Systems (NeurIPS 2023)"
    )
    assert detect_venue(pdf) == "NeurIPS"


def test_detects_acl_from_proceedings_header(tmp_path):
    from scripts.venue_from_pdf import detect_venue

    pdf = _make_pdf(
        tmp_path,
        "Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics"
    )
    assert detect_venue(pdf) == "ACL"


def test_detects_emnlp_findings(tmp_path):
    from scripts.venue_from_pdf import detect_venue

    pdf = _make_pdf(
        tmp_path,
        "Findings of the Association for Computational Linguistics: EMNLP 2024"
    )
    # Both ACL and EMNLP Findings patterns could fire — EMNLP is the more
    # specific match and should win.
    assert detect_venue(pdf) == "EMNLP"


def test_detects_cvpr(tmp_path):
    from scripts.venue_from_pdf import detect_venue

    pdf = _make_pdf(
        tmp_path,
        "IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR) 2024"
    )
    assert detect_venue(pdf) == "CVPR"


def test_returns_none_on_preprint_without_venue(tmp_path):
    from scripts.venue_from_pdf import detect_venue

    pdf = _make_pdf(tmp_path, "arXiv preprint arXiv:2401.12345")
    assert detect_venue(pdf) is None


def test_returns_none_on_unreadable_pdf(tmp_path):
    from scripts.venue_from_pdf import detect_venue

    fake = tmp_path / "broken.pdf"
    fake.write_bytes(b"not a real pdf")
    assert detect_venue(fake) is None


def test_only_reads_first_page(tmp_path):
    """Venue indicator on page 2 must NOT be detected — we only read page 1."""
    from scripts.venue_from_pdf import detect_venue

    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 50), "Generic paper header with no venue info", fontsize=9)
    p2 = doc.new_page()
    p2.insert_text((72, 50), "Published as a conference paper at ICLR 2024", fontsize=9)
    out = tmp_path / "p2.pdf"
    doc.save(out)
    doc.close()

    assert detect_venue(out) is None


def test_loads_patterns_from_yaml(tmp_path, monkeypatch):
    """Sanity: detect_venue should actually use the patterns from venues.yaml,
    not a hardcoded list."""
    from scripts import venue_from_pdf as mod

    # Override yaml load to a single-venue config — detector should only match it
    monkeypatch.setattr(mod, "_load_patterns", lambda: {
        "TestVenue": [r"my-unique-venue-marker"]
    })
    pdf = _make_pdf(tmp_path, "Header containing my-unique-venue-marker 2024")
    assert mod.detect_venue(pdf) == "TestVenue"
