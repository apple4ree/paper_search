"""Approach A — figure extraction via PyMuPDF (pure Python, no Java).

Strategy:
  For each page, collect image blocks (with bboxes) and text blocks.
  Match each "Figure N:" caption line to the image block closest above it
  on the same page. Emit PNG + sidecar caption .txt per figure.

This is a heuristic — for higher-quality figure/caption grouping, use
approach B (pdffigures2).

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


def _nearest_image_above(caption_bbox, image_blocks: list[_Block]) -> Optional[_Block]:
    cx0, cy0, cx1, cy1 = caption_bbox
    candidates = [b for b in image_blocks if b.bbox[3] <= cy0 + 5]  # image bottom ≤ caption top
    if not candidates:
        return None
    # closest image by vertical gap
    return min(candidates, key=lambda b: cy0 - b.bbox[3])


def _extract_image_bytes(page, image_block: _Block) -> bytes:
    """Get raw image bytes from a text-dict image block.

    Some PyMuPDF versions put raw bytes in `payload['image']`; others only store
    a reference, in which case we fall back to scanning page.get_images() by bbox.
    """
    payload = image_block.payload
    if isinstance(payload, (bytes, bytearray)):
        return bytes(payload)
    if isinstance(payload, dict) and "image" in payload:
        data = payload["image"]
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
    # Fallback: rasterize the bbox area at 2x scale
    x0, y0, x1, y1 = image_block.bbox
    pix = page.get_pixmap(clip=fitz.Rect(x0, y0, x1, y1), dpi=200)
    return pix.tobytes("png")


def extract(pdf_path: Path, out_dir: Path) -> list[dict]:
    """Extract figures from `pdf_path` into `out_dir`.

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

            for tb in text_blocks:
                cap = _match_caption(tb.payload)
                if cap is None:
                    continue
                num, caption_text = cap
                img = _nearest_image_above(tb.bbox, image_blocks)
                if img is None:
                    continue

                img_bytes = _extract_image_bytes(page, img)
                ext = "png"  # normalize output format
                # If raw bytes are already PNG keep as-is; otherwise convert via Pixmap.
                if not img_bytes[:4] == b"\x89PNG":
                    try:
                        pix = fitz.Pixmap(img_bytes)
                        img_bytes = pix.tobytes("png")
                    except Exception:
                        pass

                out_file = out_dir / f"fig-{num:02d}.{ext}"
                out_file.write_bytes(img_bytes)
                out_file.with_suffix(".txt").write_text(caption_text)

                results.append({
                    "page": page_idx + 1,
                    "number": num,
                    "caption": caption_text,
                    "image_path": str(out_file),
                })
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
