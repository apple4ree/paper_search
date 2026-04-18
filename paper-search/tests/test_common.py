import pytest
from scripts.common import (
    Paper,
    normalize_title,
    title_slug,
    first_author_lastname,
    dedup_key,
)


def test_paper_round_trip_dict():
    p = Paper(
        title="Chain-of-Thought Distillation",
        authors=["Jane Smith", "Bob Lee"],
        year=2024,
        venue="NeurIPS",
        abstract="We distill reasoning...",
        url="https://openreview.net/forum?id=abc",
        pdf_url=None,
        arxiv_id="2401.12345",
        doi=None,
        source="openreview",
    )
    d = p.to_dict()
    assert d["title"] == "Chain-of-Thought Distillation"
    assert d["authors"] == ["Jane Smith", "Bob Lee"]
    assert Paper.from_dict(d) == p


def test_normalize_title_strips_punct_and_lowercases():
    assert normalize_title("Chain-of-Thought: Reasoning!") == "chain of thought reasoning"
    assert normalize_title("  Multi  Spaces  ") == "multi spaces"


def test_title_slug_truncates_and_hyphenates():
    s = title_slug("Chain-of-Thought Distillation for Small Language Models")
    assert s == "chain-of-thought-distillation-for-small-language-models"
    long_title = "A " * 60
    assert len(title_slug(long_title)) <= 60


def test_first_author_lastname_handles_comma_and_space_forms():
    assert first_author_lastname(["Jane Smith", "Bob Lee"]) == "smith"
    assert first_author_lastname(["Smith, Jane", "Lee, Bob"]) == "smith"
    assert first_author_lastname(["Plato"]) == "plato"
    assert first_author_lastname([]) == ""


def test_dedup_key_prefers_doi_then_arxiv_then_title_author():
    p_doi = Paper(
        title="T", authors=["A B"], year=2024, venue="X",
        abstract="", url="", pdf_url=None,
        arxiv_id="2401.1", doi="10.1/abc", source="arxiv",
    )
    p_arxiv = Paper(
        title="T", authors=["A B"], year=2024, venue="X",
        abstract="", url="", pdf_url=None,
        arxiv_id="2401.1", doi=None, source="arxiv",
    )
    p_title = Paper(
        title="Cool Paper!", authors=["Alice Zed"], year=2024, venue="X",
        abstract="", url="", pdf_url=None,
        arxiv_id=None, doi=None, source="arxiv",
    )
    assert dedup_key(p_doi) == ("doi", "10.1/abc")
    assert dedup_key(p_arxiv) == ("arxiv", "2401.1")
    assert dedup_key(p_title) == ("title", "cool paper", "zed")
