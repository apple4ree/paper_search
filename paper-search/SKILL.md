---
name: paper-search
description: Analyse the current project, search arXiv + OpenReview + Google Scholar for related papers, and write a venue-organised related-work directory. Use when the user runs /paper-search or asks to find papers related to the current project.
---

# paper-search

Given a research project in the current working directory (or a text
description from the user), build `./papers/` containing per-venue
Markdown indexes and per-paper summaries.

## Prerequisites

The skill bundles Python scripts that require `arxiv`, `openreview-py`,
`scholarly`, and `pyyaml`. If `python -c "import arxiv, openreview, scholarly, yaml"`
fails, tell the user to run:

    cd <skill-dir> && python -m venv .venv && source .venv/bin/activate \
        && pip install -r requirements.txt

and stop until they confirm.

## Arguments

Parse from the user's invocation:

| Arg | Default | Notes |
|-----|---------|-------|
| `--top N` | 10 | Max per category after ranking |
| `--years Y` | none | Restrict to last Y years |
| `--output <path>` | `./papers/` | Output root |
| `--venues <csv>` | all in `config/venues.yaml` | Restrict venues |
| `--force` | off | Overwrite without prompt |

Free-form topic override (no flag): `/paper-search "topic phrase"` — use
the phrase as the project description instead of reading the directory.

## Pipeline

### 1. Context gathering

Read the working directory: `README.md`, `docs/`, top-level source files,
any notes. If content is sparse (< ~200 words of signal), ask the user for
a 2–3 sentence project description.

### 2. Analysis & query generation

Analyse the context freely and produce 2–4 English queries per
`references/query_generation.md`. Write them to a temp file or keep them in
memory for step 3.

**Ambiguity gate:** if the context signals multiple unrelated topics (e.g.,
CV + NLP + systems all in one repo), show the user your draft analysis and
queries, and wait for confirmation before continuing.

### 3. Parallel search

Load `config/venues.yaml`. For each query Q, launch in parallel:

- `python scripts/search_arxiv.py --query "Q" --top <top*2>`
- For each venue V with `openreview_id`:
  `python scripts/search_openreview.py --query "Q" --top <top*2> --venue <openreview_id>`
- `python scripts/search_gscholar.py --query "Q" --top <top*2>`

Apply `--years` if specified. Concurrency caps: arXiv ≤ 3, OpenReview ≤ 2,
Google Scholar ≤ 1. Collect all stdouts; concatenate JSON arrays into one
combined array. Warn (do not abort) on per-source failures; abort only if
every source fails.

### 4. Dedupe & classify

Pipe the combined array into `dedupe.py`:

    echo "<combined.json>" | python scripts/dedupe.py

Receive `{category: [paper, ...]}` back. Categories that are not in
`venues.yaml` (i.e., venues learned only from arXiv/gscholar metadata that
don't match our list) should be folded into `arxiv_only`.

### 5. Relevance ranking

For each category, read titles + abstracts and pick the top N (default 10)
most relevant to the project context and original queries. Drop the rest.

### 6. Output

Root = `--output` (default `./papers/`). If it exists and `--force` is off,
ask the user before overwriting.

Create:

    papers/
      README.md               # project summary (Korean), queries (English),
                              # per-venue counts, run metadata
      <venue>/
        index.md              # Markdown table: # | Title | Year | Authors | 관련성
        refs.bib              # all BibTeX entries, concatenated
        YYYY-<firstauthor>-<slug>.md   # per paper, see template below

Categories with zero selected papers: no directory created; count 0 in
README table.

### Per-paper template

```markdown
# <Title>

**Authors:** <comma-separated>
**Venue:** <Venue Year>
**Links:** [OpenReview](...) · [arXiv](...) · [PDF](...)

## Abstract
<English abstract, verbatim>

## 한줄 요약
<Korean, 1 sentence>

## 왜 이 프로젝트와 관련 있는가
<Korean, 2–4 sentences referencing specific aspects of the project>

## BibTeX
​```bibtex
@inproceedings{...}
​```
```

Use the `title_slug` and `first_author_lastname` helpers from
`scripts/common.py` for filename generation if you shell out to Python; or
reproduce their logic directly (lowercase, punctuation stripped, hyphens,
≤ 60 chars).

## Failure reporting

End the run with a short status summary: which sources returned data,
which were blocked, per-venue counts. If Google Scholar was blocked,
say so plainly — the user needs to know that category may be under-covered.
