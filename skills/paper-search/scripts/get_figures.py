"""Orchestrator — download a paper's PDF and extract figures.

Picks between approach A (PyMuPDF) and approach B (pdffigures2) based on
the `--method` flag (default `auto` = B if PDFFIGURES2_JAR is set, else A).

Library usage:
    figures = get_figures(paper_dict, out_dir, method="auto")

CLI usage:
    python -m scripts.get_figures --paper paper.json --out-dir papers/NeurIPS/<slug>/
    python -m scripts.get_figures --paper paper.json --out-dir dir --method pdffigures2
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Optional

from scripts.download_pdf import download_pdf
from scripts.extract_figures_pymupdf import extract as _extract_pymupdf
from scripts.extract_figures_pdffigures import (
    extract as _extract_pdffigures,
    is_available as _pdffigures_available,
)


def _pick_method(requested: str) -> str:
    if requested == "auto":
        return "pdffigures2" if _pdffigures_available() else "pymupdf"
    if requested not in {"pymupdf", "pdffigures2"}:
        raise ValueError(f"unknown method: {requested!r}")
    return requested


def get_figures(
    paper: dict,
    out_dir: Path,
    *,
    method: str = "auto",
    keep_pdf: bool = False,
) -> list[dict]:
    """Download + extract figures for one paper.

    Writes figures under `out_dir/figures/` and returns a JSON-serialisable
    list of figure records. Returns [] if the PDF can't be fetched.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = out_dir / "figures"
    figures_dir.mkdir(exist_ok=True)

    pdf_cache = out_dir / ".pdf_cache"
    pdf_path = download_pdf(paper, pdf_cache)
    if pdf_path is None:
        print(f"get_figures: no PDF for {paper.get('title', '?')!r}",
              file=sys.stderr)
        return []

    chosen = _pick_method(method)
    try:
        if chosen == "pdffigures2":
            figures = _extract_pdffigures(pdf_path, figures_dir)
        else:
            figures = _extract_pymupdf(pdf_path, figures_dir)
    except Exception as e:
        print(f"get_figures: {chosen} extraction failed: {e}", file=sys.stderr)
        figures = []

    if not keep_pdf:
        shutil.rmtree(pdf_cache, ignore_errors=True)

    return figures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download a paper PDF and extract figures.")
    parser.add_argument("--paper", help="Path to a single paper JSON file")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--method", choices=["auto", "pymupdf", "pdffigures2"],
                        default="auto")
    parser.add_argument("--keep-pdf", action="store_true",
                        help="Keep the downloaded PDF in <out>/.pdf_cache/")
    args = parser.parse_args(argv)

    if args.paper:
        paper = json.loads(Path(args.paper).read_text())
    else:
        paper = json.load(sys.stdin)

    figures = get_figures(paper, Path(args.out_dir),
                          method=args.method, keep_pdf=args.keep_pdf)
    json.dump(figures, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if figures else 1


if __name__ == "__main__":
    raise SystemExit(main())
