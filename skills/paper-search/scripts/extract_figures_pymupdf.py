"""Approach A — figure extraction via PyMuPDF (pure Python, no Java).

Strategy (hybrid):
  1. Find every "Figure N:" caption block on each page.
  2. Prefer an embedded raster image block immediately above the caption
     (produces the original high-quality bitmap when available).
  3. Fall back to rasterising the page region above the caption at 150 DPI
     — this catches vector-drawn figures (TikZ, Illustrator) that PyMuPDF's
     block detection misses.

For higher-quality figure/caption grouping, use approach B (pdffigures2).

Library usage:
    figures = extract(pdf_path, out_dir)

CLI usage:
    python -m scripts.extract_figures_pymupdf --pdf paper.pdf --out-dir figs/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

# Silence MuPDF diagnostics — they can leak to stdout when processing some
# PDFs (e.g. malformed ICC profiles) and corrupt downstream JSON consumers.
try:
    fitz.TOOLS.mupdf_display_errors(False)
    fitz.TOOLS.mupdf_display_warnings(False)
except (AttributeError, Exception):
    pass


_FIG_CAPTION_RE = re.compile(r"^\s*(?:figure|fig\.?)\s*(\d+)\b[\.:]?\s*(.*)$",
                             re.IGNORECASE)


@dataclass
class _Block:
    bbox: tuple  # x0, y0, x1, y1
    kind: str    # "image" | "text"
    payload: object  # bytes for image, str for text


def _page_blocks(page) -> list[_Block]:
    """Return image and text blocks in a single flat list."""
    out: list[_Block] = []
    # `page.get_text("dict")` yields blocks with type: 0=text, 1=image.
    for b in page.get_text("dict")["blocks"]:
        bbox = tuple(b["bbox"])
        if b["type"] == 1:
            out.append(_Block(bbox=bbox, kind="image", payload=b.get("image", b)))
        else:
            lines = []
            for line in b.get("lines", []):
                lines.append("".join(span["text"] for span in line.get("spans", [])))
            text = "\n".join(lines).strip()
            if text:
                out.append(_Block(bbox=bbox, kind="text", payload=text))
    return out


def _match_caption(text: str) -> Optional[tuple[int, str]]:
    for line in text.splitlines():
        m = _FIG_CAPTION_RE.match(line)
        if m:
            num = int(m.group(1))
            rest = m.group(2).strip()
            return (num, line.strip() if rest else f"Figure {num}")
    return None


_MIN_RASTER_BYTES = 2000  # below this, embedded "image" is likely a thumbnail/icon


def _nearest_image_above(caption_bbox, image_blocks: list[_Block]) -> Optional[_Block]:
    cx0, cy0, cx1, cy1 = caption_bbox
    candidates = [b for b in image_blocks if b.bbox[3] <= cy0 + 5]
    if not candidates:
        return None
    return min(candidates, key=lambda b: cy0 - b.bbox[3])


def _image_block_bytes(image_block: _Block) -> Optional[bytes]:
    payload = image_block.payload
    if isinstance(payload, (bytes, bytearray)):
        return bytes(payload)
    if isinstance(payload, dict) and "image" in payload:
        data = payload["image"]
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
    return None


def _rasterize_region(page, bbox, dpi: int = 150) -> bytes:
    """Render a bbox of the page to PNG at the given DPI."""
    pix = page.get_pixmap(clip=fitz.Rect(*bbox), dpi=dpi)
    return pix.tobytes("png")


def _figure_region_for_caption(
    page,
    caption_bbox,
    prev_caption_bottom_on_page: Optional[float],
) -> tuple[float, float, float, float]:
    """Compute a bbox for the figure area above a caption.

    Horizontal extent = page width minus a small margin.
    Top   = page top OR previous caption bottom on same page.
    Bottom = caption top - small gap.
    """
    pw, ph = page.rect.width, page.rect.height
    x0 = 0
    x1 = pw
    y_top = prev_caption_bottom_on_page + 6 if prev_caption_bottom_on_page else 0
    y_bot = max(y_top + 20, caption_bbox[1] - 4)
    return (x0, y_top, x1, y_bot)


def extract(pdf_path: Path, out_dir: Path) -> list[dict]:
    """Extract figures from `pdf_path` into `out_dir`.

    Hybrid: prefer embedded raster images; fall back to rasterising the
    page region above each caption.

    Returns a list of dicts: {page, number, caption, image_path}.
    """
    pdf_path = Path(pdf_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    doc = fitz.open(pdf_path)
    try:
        for page_idx, page in enumerate(doc):
            blocks = _page_blocks(page)
            image_blocks = [b for b in blocks if b.kind == "image"]
            text_blocks = [b for b in blocks if b.kind == "text"]

            # Captions sorted top-to-bottom on this page
            page_captions = []
            for tb in text_blocks:
                cap = _match_caption(tb.payload)
                if cap is not None:
                    page_captions.append((tb, cap))
            page_captions.sort(key=lambda pair: pair[0].bbox[1])

            prev_caption_bottom: Optional[float] = None
            for tb, (num, caption_text) in page_captions:
                img_bytes: Optional[bytes] = None

                # Strategy 1: embedded raster image above caption.
                img_block = _nearest_image_above(tb.bbox, image_blocks)
                if img_block is not None:
                    raw = _image_block_bytes(img_block)
                    if raw and len(raw) >= _MIN_RASTER_BYTES:
                        img_bytes = raw if raw[:4] == b"\x89PNG" else None
                        if img_bytes is None:
                            try:
                                img_bytes = fitz.Pixmap(raw).tobytes("png")
                            except Exception:
                                img_bytes = None

                # Strategy 2: rasterise region above caption (vector fallback).
                if img_bytes is None:
                    region = _figure_region_for_caption(
                        page, tb.bbox, prev_caption_bottom
                    )
                    # Skip if region has no meaningful area
                    if region[3] - region[1] >= 30 and region[2] - region[0] >= 30:
                        img_bytes = _rasterize_region(page, region, dpi=150)

                if img_bytes is None:
                    continue

                out_file = out_dir / f"fig-{num:02d}.png"
                out_file.write_bytes(img_bytes)
                out_file.with_suffix(".txt").write_text(caption_text)

                results.append({
                    "page": page_idx + 1,
                    "number": num,
                    "caption": caption_text,
                    "image_path": str(out_file),
                })
                prev_caption_bottom = tb.bbox[3]
    finally:
        doc.close()

    results.sort(key=lambda r: r["number"])
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract figures from a PDF (PyMuPDF).")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)

    figures = extract(Path(args.pdf), Path(args.out_dir))
    json.dump(figures, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
