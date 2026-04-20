"""Tests for scripts.download_pdf — URL resolution + fetching."""
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _paper(**kw) -> dict:
    base = dict(
        title="T", authors=["A B"], year=2024, venue=None,
        abstract="", url="", pdf_url=None, arxiv_id=None, doi=None, source="arxiv",
    )
    base.update(kw)
    return base


def test_resolve_pdf_url_prefers_arxiv_id():
    from scripts.download_pdf import resolve_pdf_url
    p = _paper(arxiv_id="2401.12345", url="http://other", pdf_url="http://old")
    assert resolve_pdf_url(p) == "https://arxiv.org/pdf/2401.12345.pdf"


def test_resolve_pdf_url_strips_arxiv_version_suffix():
    from scripts.download_pdf import resolve_pdf_url
    p = _paper(arxiv_id="2401.12345v3")
    assert resolve_pdf_url(p) == "https://arxiv.org/pdf/2401.12345.pdf"


def test_resolve_pdf_url_openreview_forum_to_pdf():
    from scripts.download_pdf import resolve_pdf_url
    p = _paper(url="https://openreview.net/forum?id=abcXYZ", source="openreview")
    assert resolve_pdf_url(p) == "https://openreview.net/pdf?id=abcXYZ"


def test_resolve_pdf_url_direct_pdf_url_passthrough():
    from scripts.download_pdf import resolve_pdf_url
    p = _paper(pdf_url="https://example.org/paper.pdf")
    assert resolve_pdf_url(p) == "https://example.org/paper.pdf"


def test_resolve_pdf_url_returns_none_when_unresolvable():
    from scripts.download_pdf import resolve_pdf_url
    p = _paper()  # no arxiv_id, no pdf_url, no openreview url
    assert resolve_pdf_url(p) is None


def test_download_pdf_writes_file(tmp_path, monkeypatch):
    from scripts import download_pdf

    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.content = b"%PDF-1.7\n<fake pdf bytes>\n"
    fake_response.headers = {"Content-Type": "application/pdf"}
    fake_response.raise_for_status.return_value = None
    monkeypatch.setattr(download_pdf.requests, "get", lambda *a, **kw: fake_response)

    p = _paper(arxiv_id="2401.1", title="Hello World")
    out = download_pdf.download_pdf(p, tmp_path)

    assert out is not None
    assert out.exists()
    assert out.read_bytes().startswith(b"%PDF")
    # Filename should be deterministic (arxiv_id-based slug)
    assert "2401.1" in out.name or "hello" in out.name.lower()


def test_download_pdf_returns_none_on_unresolvable(tmp_path, monkeypatch):
    from scripts import download_pdf
    p = _paper()
    out = download_pdf.download_pdf(p, tmp_path)
    assert out is None


def test_download_pdf_fast_fails_on_4xx(tmp_path, monkeypatch):
    """4xx responses (403/404) mean auth/gone — never retry."""
    from scripts import download_pdf

    calls = {"n": 0}

    def fake_get(*a, **kw):
        calls["n"] += 1
        resp = MagicMock()
        resp.status_code = 403
        err = download_pdf.requests.HTTPError("403 Forbidden")
        err.response = MagicMock(status_code=403)
        resp.raise_for_status.side_effect = err
        return resp

    monkeypatch.setattr(download_pdf.requests, "get", fake_get)
    monkeypatch.setattr(download_pdf.time, "sleep", lambda s: None)

    p = _paper(arxiv_id="2401.1")
    out = download_pdf.download_pdf(p, tmp_path)
    assert out is None
    assert calls["n"] == 1  # no retries on 4xx


def test_download_pdf_retries_on_5xx(tmp_path, monkeypatch):
    from scripts import download_pdf

    calls = {"n": 0}

    def fake_get(*a, **kw):
        calls["n"] += 1
        resp = MagicMock()
        resp.status_code = 503
        err = download_pdf.requests.HTTPError("503 unavailable")
        err.response = MagicMock(status_code=503)
        resp.raise_for_status.side_effect = err
        return resp

    monkeypatch.setattr(download_pdf.requests, "get", fake_get)
    monkeypatch.setattr(download_pdf.time, "sleep", lambda s: None)

    p = _paper(arxiv_id="2401.1")
    out = download_pdf.download_pdf(p, tmp_path)
    assert out is None
    assert calls["n"] == 3  # exhaust retries on 5xx


def test_download_pdf_skips_paywalled_domain(tmp_path, monkeypatch):
    """SSRN / Elsevier etc. always return 403 — skip without even trying."""
    from scripts import download_pdf

    calls = {"n": 0}
    monkeypatch.setattr(download_pdf.requests, "get",
                        lambda *a, **kw: (calls.__setitem__("n", calls["n"] + 1) or MagicMock()))

    p = _paper(pdf_url="https://papers.ssrn.com/sol3/Delivery.cfm?abstractid=5277657")
    out = download_pdf.download_pdf(p, tmp_path)
    assert out is None
    assert calls["n"] == 0  # never called requests.get


def test_download_pdf_rejects_non_pdf_content_type(tmp_path, monkeypatch):
    """Some publisher URLs return HTML landing pages instead of PDFs."""
    from scripts import download_pdf

    fake = MagicMock()
    fake.status_code = 200
    fake.headers = {"Content-Type": "text/html"}
    fake.content = b"<html>paywall</html>"
    fake.raise_for_status.return_value = None
    monkeypatch.setattr(download_pdf.requests, "get", lambda *a, **kw: fake)

    p = _paper(pdf_url="https://example.org/some.pdf")
    out = download_pdf.download_pdf(p, tmp_path)
    assert out is None
