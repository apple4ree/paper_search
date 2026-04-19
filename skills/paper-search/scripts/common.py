"""Shared schema and helpers for paper-search scripts."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Optional


@dataclass(frozen=True)
class Paper:
    title: str
    authors: list[str]
    year: int
    venue: Optional[str]
    abstract: str
    url: str
    pdf_url: Optional[str]
    arxiv_id: Optional[str]
    doi: Optional[str]
    source: str  # "arxiv" | "openreview" | "gscholar"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Paper":
        return cls(
            title=d["title"],
            authors=list(d["authors"]),
            year=d["year"],
            venue=d.get("venue"),
            abstract=d.get("abstract", ""),
            url=d["url"],
            pdf_url=d.get("pdf_url"),
            arxiv_id=d.get("arxiv_id"),
            doi=d.get("doi"),
            source=d["source"],
        )


_PUNCT_RE = re.compile(r"[^\w\s-]")
_WS_RE = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation (except hyphens), collapse whitespace."""
    t = _PUNCT_RE.sub(" ", title.lower())
    t = t.replace("-", " ").replace("_", " ")
    t = _WS_RE.sub(" ", t).strip()
    return t


def title_slug(title: str, max_len: int = 60) -> str:
    """Produce a filesystem-safe slug, hyphen-separated, at most max_len chars."""
    t = _PUNCT_RE.sub("", title.lower())
    t = _WS_RE.sub("-", t).strip("-")
    if not t:
        return "untitled"
    if len(t) <= max_len:
        return t
    cut = t[:max_len].rsplit("-", 1)[0] or t[:max_len]
    return cut


def first_author_lastname(authors: list[str]) -> str:
    """Return the first author's last name, lowercased."""
    if not authors:
        return ""
    first = authors[0].strip()
    if "," in first:
        return first.split(",", 1)[0].strip().lower()
    parts = first.split()
    return (parts[-1] if parts else first).lower()


def dedup_key(paper: Paper) -> tuple:
    """Priority: doi > arxiv_id > (normalized title, first-author last name)."""
    if paper.doi:
        return ("doi", paper.doi.lower())
    if paper.arxiv_id:
        return ("arxiv", paper.arxiv_id.lower())
    return ("title", normalize_title(paper.title), first_author_lastname(paper.authors))
