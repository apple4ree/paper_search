"""Approach B — figure extraction via pdffigures2 (Allen AI, Scala).

pdffigures2 is the highest-quality open figure-caption extractor — used by
Semantic Scholar. It requires Java + a pre-built jar.

Setup (one-time, by the user):
    git clone https://github.com/allenai/pdffigures2
    cd pdffigures2 && sbt assembly
    # Point the env var at the produced jar:
    export PDFFIGURES2_JAR=/path/to/pdffigures2/target/scala-2.12/pdffigures2-assembly-0.1.0.jar

If PDFFIGURES2_JAR is unset or missing, `extract()` raises
PdfFiguresNotAvailable — the orchestrator (`get_figures.py`) falls back to
the PyMuPDF approach.

Library usage:
    figures = extract(pdf_path, out_dir)

CLI usage:
    python -m scripts.extract_figures_pdffigures --pdf paper.pdf --out-dir figs/
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


class PdfFiguresNotAvailable(RuntimeError):
    """Raised when PDFFIGURES2_JAR is unset or points at a missing file."""


def _jar_path() -> Optional[Path]:
    jar = os.environ.get("PDFFIGURES2_JAR")
    if not jar:
        return None
    p = Path(jar)
    return p if p.exists() else None


def is_available() -> bool:
    return _jar_path() is not None


def extract(pdf_path: Path, out_dir: Path) -> list[dict]:
    """Run pdffigures2 on `pdf_path`, materialise results in `out_dir`.

    Returns a list of dicts: {page, number, caption, image_path}.
    """
    jar = _jar_path()
    if jar is None:
        raise PdfFiguresNotAvailable(
            "PDFFIGURES2_JAR env var not set or points to missing file. "
            "See scripts/extract_figures_pdffigures.py docstring for setup."
        )

    pdf_path = Path(pdf_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "pdffigures2.json"
    # pdffigures2 CLI:
    #   -m <prefix>  — prefix for extracted figure image files
    #   -f <path>    — path to write the JSON index
    #   <pdf>        — input file(s)
    cmd = [
        "java", "-jar", str(jar),
        "-m", str(out_dir / "fig-"),
        "-f", str(json_path),
        str(pdf_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, cwd=str(out_dir))
    if proc.returncode != 0:
        msg = proc.stderr.decode("utf-8", errors="replace") if proc.stderr else "(no stderr)"
        raise RuntimeError(f"pdffigures2 failed (rc={proc.returncode}): {msg}")

    if not json_path.exists():
        raise RuntimeError(f"pdffigures2 produced no output at {json_path}")

    raw = json.loads(json_path.read_text())
    figures: list[dict] = []
    for entry in raw:
        # entry["name"] looks like "Figure 1" or "Table 3" — filter to figures
        name = entry.get("name", "")
        if not name.lower().startswith("figure"):
            continue
        try:
            num = int(name.split()[1].rstrip(".:"))
        except (IndexError, ValueError):
            continue

        render_url = entry.get("renderURL") or entry.get("imagePath")
        if not render_url:
            continue
        image_path = Path(render_url)
        if not image_path.is_absolute():
            image_path = (out_dir / image_path).resolve()

        figures.append({
            "page": (entry.get("page", 0) + 1),  # pdffigures2 is 0-indexed
            "number": num,
            "caption": entry.get("caption", "").strip(),
            "image_path": str(image_path),
        })

    figures.sort(key=lambda f: f["number"])
    return figures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract figures via pdffigures2.")
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)

    try:
        figures = extract(Path(args.pdf), Path(args.out_dir))
    except PdfFiguresNotAvailable as e:
        print(str(e), file=sys.stderr)
        return 2
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1

    json.dump(figures, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
