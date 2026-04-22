#!/usr/bin/env python3
"""
PDF → raw.md + figures/ + figures/_pages/ extractor.

This module is adapted from wj926/paper-summary (Phase B extract.py),
MIT-licensed. See ATTRIBUTION below. Changes from upstream:
  - All diagnostic prints redirected to stderr (keep stdout JSON-clean).
  - MuPDF C-level diagnostics silenced at import time.
  - `extract()` now returns a result dict so orchestrators can inspect
    counts/warnings without re-reading raw.md.

ATTRIBUTION
-----------
Original: https://github.com/wj926/paper-summary/blob/main/scripts/extract.py
Copyright (c) 2026 wj926
License: MIT (same as this project)

Full mode outputs under <out_dir>:
    raw.md                         full text per page + figure embeds
    figures/figN.png               main figures (renumbered 1..)
    figures/figAN.png              appendix figures (renumbered A1..)
    figures/_pages/p-NN.png        full-page renders (200dpi), kept as
                                   source for manual re-cropping

--metadata-only prints key=value lines to stdout so the caller can decide
the final folder name before any extraction work.

CLI:
    python -m scripts.extract_paper_content <pdf> <out_dir>
    python -m scripts.extract_paper_content --metadata-only <pdf>
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

# Silence C-level MuPDF diagnostics — they otherwise leak to stdout/stderr
# and corrupt JSON pipelines consuming our output.
try:
    fitz.TOOLS.mupdf_display_errors(False)
    fitz.TOOLS.mupdf_display_warnings(False)
except (AttributeError, Exception):
    pass


CAPTION_RE = re.compile(r"^\s*(?:Figure|Fig\.?)\s*(\d+)\s*[:.\-]", re.IGNORECASE)
REFERENCES_RE = re.compile(r"^\s*references\s*$", re.IGNORECASE)
APPENDIX_RE = re.compile(
    r"^\s*(appendix(\s*[A-Z0-9]{1,3})?|supplementary\s+material)\s*[:.]?\s*$",
    re.IGNORECASE,
)


def _log(msg: str) -> None:
    """Diagnostic output → stderr so stdout stays clean for JSON pipelines."""
    print(msg, file=sys.stderr)


def dump_pages(doc: fitz.Document, pages_dir: Path, dpi: int = 200) -> None:
    pages_dir.mkdir(parents=True, exist_ok=True)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    for idx, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=mat)
        pix.save(str(pages_dir / f"p-{idx:02d}.png"))


def find_boundary_page(doc: fitz.Document) -> int:
    """Return 0-based page index where references/appendix starts (== main end)."""
    for i, page in enumerate(doc):
        for line in page.get_text("text").splitlines():
            if REFERENCES_RE.match(line) or APPENDIX_RE.match(line):
                return i
    return doc.page_count


def caption_blocks(page: fitz.Page):
    """Yield (fig_num, caption_bbox, caption_text) for each figure caption on page."""
    for b in page.get_text("blocks"):
        text = (b[4] or "").strip()
        if not text:
            continue
        first_line = text.splitlines()[0]
        m = CAPTION_RE.match(first_line)
        if not m:
            continue
        fig_num = int(m.group(1))
        bbox = fitz.Rect(b[0], b[1], b[2], b[3])
        yield fig_num, bbox, " ".join(text.splitlines())


def image_bboxes_on_page(page: fitz.Page):
    """Return list of Rects covering embedded raster images on the page."""
    rects = []
    for img in page.get_images(full=True):
        xref = img[0]
        try:
            for r in page.get_image_rects(xref):
                rects.append(r)
        except Exception:
            continue
    return rects


def drawing_bboxes_on_page(page: fitz.Page):
    """Return Rects for vector drawings. Filters degenerate rects (lines, tiny
    marks) and near-page-spanning rects (likely crop boxes / margin rules)."""
    page_rect = page.rect
    rects = []
    for d in page.get_drawings():
        r = d.get("rect")
        if r is None:
            continue
        if r.width < 5 or r.height < 5:
            continue
        if r.width > page_rect.width * 0.95 and r.height > page_rect.height * 0.9:
            continue
        rects.append(fitz.Rect(r))
    return rects


def _text_block_bottom_above(page: fitz.Page, caption_bbox: fitz.Rect) -> float:
    """Bottom y of the lowest text block above caption that overlaps its
    x-range. Becomes the hard upper bound on the crop so we never bleed into
    title/body text above the figure."""
    best_y = page.rect.y0 + 18
    cx0, cx1 = caption_bbox.x0, caption_bbox.x1
    caption_w = max(1.0, cx1 - cx0)
    for b in page.get_text("blocks"):
        x0, y0, x1, y1 = b[0], b[1], b[2], b[3]
        text = (b[4] or "").strip()
        if not text:
            continue
        if y1 > caption_bbox.y0 - 1:
            continue
        if x1 < cx0 or x0 > cx1:
            continue
        # filter short text (likely figure-internal labels)
        if len(text.replace("\n", " ")) < 40:
            continue
        # filter narrow blocks (also figure-internal)
        if (x1 - x0) < caption_w * 0.4:
            continue
        if y1 > best_y:
            best_y = y1
    return best_y


def figure_region_above_caption(
    page: fitz.Page, caption_bbox: fitz.Rect, image_rects, drawing_rects
):
    """Return (rect, source_tag). Tag ∈ {image, drawing, mixed, text-bound, page-top, none}."""
    page_rect = page.rect
    text_floor = _text_block_bottom_above(page, caption_bbox) + 2
    if caption_bbox.y0 - text_floor < 60:
        # Text floor suspiciously close to caption → figure likely an
        # undetected vector. Prefer over-crop to missing it.
        text_floor = page_rect.y0 + 36

    cx0, cx1 = caption_bbox.x0, caption_bbox.x1

    def _above_and_overlapping(rects):
        out = []
        for r in rects:
            if r.y1 > caption_bbox.y0 + 2:
                continue
            if r.y1 < caption_bbox.y0 - 600:
                continue
            if r.x1 < cx0 - 10 or r.x0 > cx1 + 10:
                continue
            out.append(r)
        return out

    img_cands = _above_and_overlapping(image_rects)
    drw_cands = _above_and_overlapping(drawing_rects)

    if img_cands or drw_cands:
        all_cands = img_cands + drw_cands
        rect = fitz.Rect(all_cands[0])
        for r in all_cands[1:]:
            rect |= r
        rect.x0 = min(rect.x0, caption_bbox.x0) - 4
        rect.x1 = max(rect.x1, caption_bbox.x1) + 4
        rect.y0 = max(rect.y0, text_floor)
        rect.y1 = caption_bbox.y0 - 2
        rect &= page_rect
        if rect.height >= 40 and rect.width >= 40:
            if img_cands and drw_cands:
                tag = "mixed"
            elif img_cands:
                tag = "image"
            else:
                tag = "drawing"
            return rect, tag

    slab = fitz.Rect(
        max(page_rect.x0, caption_bbox.x0 - 6),
        text_floor,
        min(page_rect.x1, caption_bbox.x1 + 6),
        caption_bbox.y0 - 2,
    )
    tag = "text-bound" if text_floor > page_rect.y0 + 40 else "page-top"
    if slab.height >= 40 and slab.width >= 40:
        return slab, tag
    return None, "none"


def render_crop(page: fitz.Page, rect: fitz.Rect, dpi: int = 200) -> fitz.Pixmap:
    zoom = dpi / 72.0
    return page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect)


def extract(pdf_path: Path, out_dir: Path) -> dict:
    """Materialise raw.md + figures/ + figures/_pages/ under out_dir.

    Returns a dict summarising what was written:
        {
          "pdf_path": str, "out_dir": str,
          "pages": int, "boundary_page": int,
          "main_figures": int, "appendix_figures": int,
          "figures": list[dict],   # page/number/fname/caption/source/warn
          "raw_md": str,
        }
    """
    pdf_path = Path(pdf_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_dir = out_dir / "figures"
    pages_dir = fig_dir / "_pages"
    fig_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    try:
        _log(f"[info] pages: {doc.page_count}")
        dump_pages(doc, pages_dir)

        boundary = find_boundary_page(doc)
        _log(f"[info] main/appendix boundary page: {boundary + 1}")

        main_n = 0
        appx_n = 0
        figures: list[dict] = []

        for i, page in enumerate(doc):
            is_appx = i >= boundary
            img_rects = image_bboxes_on_page(page)
            drw_rects = drawing_bboxes_on_page(page)
            for fig_num, cap_bbox, cap_text in caption_blocks(page):
                rect, source = figure_region_above_caption(
                    page, cap_bbox, img_rects, drw_rects
                )
                if rect is None:
                    _log(f"[warn] could not crop Fig {fig_num} on p{i+1}")
                    continue
                if is_appx:
                    appx_n += 1
                    fname = f"figA{appx_n}.png"
                else:
                    main_n += 1
                    fname = f"fig{main_n}.png"
                render_crop(page, rect).save(str(fig_dir / fname))
                warn: Optional[str] = None
                if rect.height < 80 or rect.width < 80:
                    warn = f"small crop ({int(rect.width)}x{int(rect.height)}pt)"
                elif source in ("text-bound", "page-top"):
                    warn = f"no graphic rects detected (source={source})"
                if warn:
                    _log(f"[warn] Fig {fig_num} p{i+1} ({fname}): {warn} "
                         f"-> check _pages/p-{i+1:02d}.png")
                figures.append({
                    "page": i + 1,
                    "is_appx": is_appx,
                    "fname": fname,
                    "orig_num": fig_num,
                    "caption": cap_text,
                    "source": source,
                    "warn": warn,
                })

        raw_md = out_dir / "raw.md"
        with raw_md.open("w", encoding="utf-8") as f:
            f.write(f"# raw: {pdf_path.name}\n\n")
            meta = doc.metadata or {}
            if meta.get("title"):
                f.write(f"- title: {meta['title']}\n")
            if meta.get("author"):
                f.write(f"- author: {meta['author']}\n")
            f.write(f"- pages: {doc.page_count}\n")
            f.write(f"- main/appendix boundary page: {boundary + 1}\n")
            f.write(f"- figures: {main_n} main + {appx_n} appendix\n\n")

            f.write("## Figure index\n\n")
            for rec in figures:
                tag = "A" if rec["is_appx"] else "M"
                warn_str = f"  ⚠ {rec['warn']}" if rec.get("warn") else ""
                f.write(
                    f"- [{tag}] p.{rec['page']} orig Fig {rec['orig_num']} -> "
                    f"`figures/{rec['fname']}` (src: {rec['source']}){warn_str}\n"
                )
                f.write(f"  > {rec['caption'][:240]}\n")
            f.write("\n> Note: for figures flagged with ⚠, re-crop manually "
                    "from `figures/_pages/p-NN.png`.\n\n---\n\n")

            figs_by_page: dict[int, list] = {}
            for rec in figures:
                figs_by_page.setdefault(rec["page"], []).append(rec)

            for i, page in enumerate(doc):
                f.write(f"\n## p. {i+1}\n\n")
                f.write(page.get_text("text").strip() + "\n\n")
                for rec in figs_by_page.get(i + 1, []):
                    f.write(f"![{rec['fname']}](figures/{rec['fname']})\n\n")
                    f.write(f"_caption_: {rec['caption']}\n\n")

        _log(f"[done] raw.md -> {raw_md}")
        _log(f"[done] figures -> {fig_dir} ({main_n} main, {appx_n} appendix)")

        return {
            "pdf_path": str(pdf_path),
            "out_dir": str(out_dir),
            "pages": doc.page_count,
            "boundary_page": boundary + 1,
            "main_figures": main_n,
            "appendix_figures": appx_n,
            "figures": figures,
            "raw_md": str(raw_md),
        }
    finally:
        doc.close()


def print_metadata(pdf_path: Path) -> None:
    """Print enough info for upstream naming: title/author/arxiv/first-page head."""
    doc = fitz.open(str(pdf_path))
    try:
        meta = doc.metadata or {}
        print(f"title={(meta.get('title') or '').strip()}")
        print(f"author={(meta.get('author') or '').strip()}")
        print(f"pages={doc.page_count}")
        first_text = doc[0].get_text("text") if doc.page_count else ""
        m = re.search(r"arXiv:\s*(\d{4}\.\d{4,5}(?:v\d+)?)", first_text)
        if m:
            print(f"arxiv={m.group(1)}")
        head = " ".join(first_text.split())[:400]
        print(f"first_page_head={head}")
    finally:
        doc.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("out_dir", nargs="?", default=None,
                    help="output directory (required unless --metadata-only)")
    ap.add_argument("--metadata-only", action="store_true",
                    help="print title/author/arxiv/first-page head and exit")
    args = ap.parse_args(argv)
    if args.metadata_only:
        print_metadata(Path(args.pdf))
        return 0
    if args.out_dir is None:
        ap.error("out_dir is required unless --metadata-only is given")
    extract(Path(args.pdf), Path(args.out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
