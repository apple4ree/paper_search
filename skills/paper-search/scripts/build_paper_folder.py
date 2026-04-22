"""Build a per-paper folder: PDF download → figure/raw extraction → meta JSON.

Called once per selected paper (§6 of SKILL.md). The produced folder is the
workspace from which §7 Claude writes `summary.md` + `abstract.md`.

Folder layout:
    papers/<Venue>/<NN_firstauthoryearMETHOD(venueYear)>/
        raw.md
        paper_meta.json               # paper dict + extraction summary
        figures/
            fig1.png, figA1.png, ...
            _pages/p-NN.png

CLI:
    python -m scripts.build_paper_folder \
        --paper paper.json \
        --out-dir papers/NeurIPS/ \
        --index 1 \
        --method TRANSFORMER
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Optional

from scripts.common import first_author_lastname
from scripts.download_pdf import download_pdf as _download_pdf
from scripts.extract_paper_content import extract as _extract


def folder_name(paper: dict, *, index: int, method: Optional[str]) -> str:
    """Format: `<NN>_<firstauthor><year>[<METHOD>](<venue><year>)`.

    Examples:
        01_vaswani2017TRANSFORMER(NeurIPS2017)
        03_vaswani2017(NeurIPS2017)         # method omitted
        05_vaswani2017LoRA(preprint2017)    # no venue
    """
    author = first_author_lastname(paper.get("authors", [])) or "anon"
    year = paper.get("year", "NA")
    venue = paper.get("venue") or "preprint"
    method_part = method if method else ""
    return f"{index:02d}_{author}{year}{method_part}({venue}{year})"


def build(
    paper: dict,
    parent_dir: Path,
    *,
    index: int,
    method: Optional[str],
    keep_pdf: bool = False,
) -> dict:
    """Materialise one paper's folder under parent_dir. Returns summary dict.

    On failure (no downloadable PDF), returns {"status": "failed", "reason": ...}
    without creating a folder — callers can still keep a stub `.md` summary if
    they want.
    """
    parent_dir = Path(parent_dir)
    parent_dir.mkdir(parents=True, exist_ok=True)

    name = folder_name(paper, index=index, method=method)
    folder = parent_dir / name
    folder.mkdir(parents=True, exist_ok=True)
    pdf_cache = folder / ".pdf_cache"

    pdf_path = _download_pdf(paper, pdf_cache)
    if pdf_path is None:
        print(f"build_paper_folder: no PDF for {paper.get('title', '?')!r}",
              file=sys.stderr)
        shutil.rmtree(pdf_cache, ignore_errors=True)
        return {"status": "failed", "reason": "pdf_unresolvable",
                "folder": str(folder), "title": paper.get("title")}

    try:
        ext = _extract(pdf_path, folder)
    except Exception as e:
        print(f"build_paper_folder: extraction failed: {e}", file=sys.stderr)
        if not keep_pdf:
            shutil.rmtree(pdf_cache, ignore_errors=True)
        return {"status": "failed", "reason": f"extract_error: {e}",
                "folder": str(folder), "title": paper.get("title")}

    meta = {
        **paper,
        "folder": name,
        "index": index,
        "method": method,
        "pages": ext["pages"],
        "main_figures": ext["main_figures"],
        "appendix_figures": ext["appendix_figures"],
        "boundary_page": ext["boundary_page"],
    }
    (folder / "paper_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2)
    )

    if not keep_pdf:
        shutil.rmtree(pdf_cache, ignore_errors=True)

    return {
        "status": "ok",
        "folder": str(folder),
        "index": index,
        "method": method,
        "pages": ext["pages"],
        "main_figures": ext["main_figures"],
        "appendix_figures": ext["appendix_figures"],
        "figures": ext["figures"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build one paper's folder.")
    parser.add_argument("--paper", help="Path to single paper JSON")
    parser.add_argument("--out-dir", required=True,
                        help="Parent dir (e.g. papers/NeurIPS/)")
    parser.add_argument("--index", type=int, required=True,
                        help="Ordering index across the whole paper set")
    parser.add_argument("--method", default=None,
                        help="Short method name, e.g. TRANSFORMER, DPO")
    parser.add_argument("--keep-pdf", action="store_true",
                        help="Keep .pdf_cache/ inside the folder")
    args = parser.parse_args(argv)

    if args.paper:
        paper = json.loads(Path(args.paper).read_text())
    else:
        paper = json.load(sys.stdin)

    result = build(paper, Path(args.out_dir),
                   index=args.index, method=args.method, keep_pdf=args.keep_pdf)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
