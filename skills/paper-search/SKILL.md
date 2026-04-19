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
`scholarly`, `pyyaml`, and `requests`. If `python -c "import arxiv, openreview, scholarly, yaml, requests"`
fails, tell the user to run (from the plugin repo root):

    python -m venv .venv && source .venv/bin/activate \
        && pip install -r requirements.txt

and stop until they confirm. When installed as a plugin, the repo root is
`${CLAUDE_PLUGIN_ROOT}`.

### OpenReview credentials

OpenReview requires authentication for all API calls. Before running the
skill, the user must set:

    export OPENREVIEW_USERNAME="..."
    export OPENREVIEW_PASSWORD="..."

Free signup at https://openreview.net/signup. If these env vars are missing,
`search_openreview.py` exits 1 with a clear message and the pipeline
continues with arxiv + gscholar only.

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

Collect evidence about the project in this **order** (broad → narrow), stop
reading as soon as the signal is clear:

1. **`README.md`** — the single most informative file; read fully.
2. **`docs/`** — design notes, specs, plans (read the 2–3 most recent).
3. **Dependency manifests** — `requirements*.txt`, `pyproject.toml`,
   `package.json`, `environment.yml`. Names of libraries reveal the
   domain (e.g., `transformers`, `torch` → deep learning; `scikit-learn` →
   classical ML; `ray` → distributed systems).
4. **Top-level folder tree** — `ls -la`, `find . -maxdepth 2 -type d`.
   Module names and directory layout signal the structure of the work.
5. **Recent commits** — `git log --oneline -20` shows what's being
   actively worked on vs. stale.
6. **Source files — selective**: if signals are still unclear, open the
   main entry point (e.g., `main.py`, `src/index.ts`) and 1–2 core modules.
   Do NOT scan the whole codebase.

**Extract these structured signals** (keep in memory or a temp note):

- **Domain** (e.g., "NLP / multi-step reasoning")
- **Problem statement** (1 sentence)
- **Method keywords** (3–8 technical terms the authors would use)
- **Benchmarks / datasets** mentioned (if any)
- **Baselines / prior work** named (if any)
- **Scale or regime** (model size, data size, constraint that matters)

If total collected signal is **< ~200 words** or the signals contradict
each other (e.g., CV + NLP + systems files all present), ask the user for
a 2–3 sentence project description before continuing.

### 2. Analysis & query generation

Draft 2–4 English queries per `references/query_generation.md`, using the
structured signals from §1. Each query should map to one of:
(a) core method, (b) problem framing, (c) key benchmark/dataset,
(d) important baseline/alternative approach.

#### Scope confirmation (mandatory)

**Before running any search**, show the user a compact summary and wait
for explicit approval. Use this format:

```
**Project summary (draft):** <1–2 sentences of domain + problem>

**Queries (English):**
1. `<query 1>`
2. `<query 2>`
3. `<query 3>`
4. `<query 4>`

**Scope:**
- top per venue: <N>
- years: <unrestricted | last Y>
- venues: <all | csv list>
- output: <path>

Approve, tweak, or say "abort".
```

One pass only — do NOT re-prompt after approval. If the user requests
changes, apply them and re-show; proceed only after they say OK.

**Ambiguity gate (merged into this step):** If §1 surfaced contradictory
topics, the confirmation is the place to surface that — present the
conflict plainly and let the user pick the direction.

### 3. Parallel search

Load `config/venues.yaml` from this skill directory. All script invocations
below run from the **skill's own directory** (Claude Code sets this as CWD
when the skill is active). If needed, `cd ${CLAUDE_PLUGIN_ROOT}/skills/paper-search`
first.

For each query Q, launch in parallel:

- `python -m scripts.search_arxiv --query "Q" --top <top*2>`
- For each venue V with `openreview_id`:
  `python -m scripts.search_openreview --query "Q" --top <top*2> --venue <openreview_id>`
- `python -m scripts.search_gscholar --query "Q" --top <top*2>`

Apply `--years` if specified. Concurrency caps: arXiv ≤ 3, OpenReview ≤ 2,
Google Scholar ≤ 1. Collect all stdouts; concatenate JSON arrays into one
combined array. Warn (do not abort) on per-source failures; abort only if
every source fails.

### 4. Dedupe & classify

Pipe the combined array into `dedupe.py`:

    cat combined.json | python -m scripts.dedupe

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
                              # per-venue counts, cross-paper themes, run metadata
      <venue>/
        index.md              # Markdown table: # | Title | Year | Authors | 관련성
        refs.bib              # all BibTeX entries, concatenated
        YYYY-<firstauthor>-<slug>.md   # per paper, see template below

Categories with zero selected papers: no directory created; count 0 in
README table.

#### Root `papers/README.md` template

```markdown
# paper-search 결과

**프로젝트 요약** (Korean, 2–3 문장 based on §1 signals)

## 사용된 검색 쿼리 (English)
- `<query 1>`
- `<query 2>`
- ...

## 학회별 결과 수
| Category | Count |
|----------|-------|
| ... | ... |

## Themes across papers

Read the selected papers' titles + abstracts together and write **3–6
themes** that recur across at least 2 papers. Each theme is 2–3 sentences
and references the papers by key (e.g., `[shridhar2023]`).

## Convergences
Where do the selected papers **agree** on a claim, method, or finding?
2–4 bullet points, each citing ≥ 2 papers.

## Disagreements / open questions
Where do the selected papers **disagree** or leave things unsettled?
2–4 bullet points. Cite the papers on each side.

## Gaps
What does this set of papers **not** cover that matters for the current
project? 2–3 bullet points — these are candidates for contribution.

## 실행 메타데이터
- 생성 일시: `<ISO timestamp>`
- 사용된 소스: arXiv / OpenReview / Google Scholar (which worked)
- 파라미터: `--top N --years Y ...`
- 총 선정 논문 수: `<sum>`
```

The `Themes / Convergences / Disagreements / Gaps` sections are what turn
this from a reading list into a literature-review starter — do not skip
them even if results are small (3+ papers is enough).

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
