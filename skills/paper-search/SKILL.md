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
`scholarly`, `pyyaml`, and `requests`. **Every script invocation in this
skill must happen inside the plugin's venv**, which lives at
`${CLAUDE_PLUGIN_ROOT}/.venv`.

**Bootstrap check** (run this first, once per session):

    cd "${CLAUDE_PLUGIN_ROOT}"
    if [ ! -d .venv ]; then
        python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
    else
        source .venv/bin/activate
    fi
    python -c "import arxiv, openreview, scholarly, yaml, requests" \
        || { echo "deps missing — run: pip install -r requirements.txt"; exit 1; }

If the venv does not exist **and** the user cannot/should not install deps,
stop and ask them. Do not proceed with broken imports.

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
| `--no-figures` | off | Skip the figure-extraction step in §6 (faster runs) |
| `--figures-method` | `auto` | `auto` / `pymupdf` / `pdffigures2`. `auto` uses pdffigures2 if `PDFFIGURES2_JAR` is set, else pymupdf |
| `--no-resolve-venues` | off | Skip the PDF-based venue resolution step in §4.5 (faster but worse classification when OpenReview is unavailable) |

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

**Extract these structured signals**:

- **Domain** (e.g., "NLP / multi-step reasoning")
- **Problem statement** (1 sentence)
- **Method keywords** (3–8 technical terms the authors would use)
- **Benchmarks / datasets** mentioned (if any)
- **Baselines / prior work** named (if any)
- **Scale or regime** (model size, data size, constraint that matters)

If total collected signal is **< ~200 words** or the signals contradict
each other (e.g., CV + NLP + systems files all present), ask the user for
a 2–3 sentence project description before continuing.

**Persist the signals as an artifact.** Immediately after extraction,
write them to `<output>/.project_analysis.json` (default
`./papers/.project_analysis.json`). This makes runs reproducible and
lets the user re-run with the same analysis but different scope.
Schema:

```json
{
  "domain": "...",
  "problem": "...",
  "method_keywords": ["...", "..."],
  "benchmarks": ["..."],
  "baselines": ["..."],
  "scale": "...",
  "inferred_domain_tags": ["general", "nlp"],
  "source_files_read": ["README.md", "docs/..."],
  "generated_at": "<ISO timestamp>"
}
```

`inferred_domain_tags` drives venue filtering in §2 below — see the domain
→ tag mapping there.

### 2. Analysis & query generation

Draft 2–4 English queries per `references/query_generation.md`, using the
structured signals from §1. Each query should map to one of:
(a) core method, (b) problem framing, (c) key benchmark/dataset,
(d) important baseline/alternative approach.

#### Venue subset inference (from domain signal)

Before scope confirmation, infer which venues in `config/venues.yaml` are
relevant by mapping the **Domain** signal to these tags:

| Domain signal contains | Include venues tagged |
|---|---|
| any project (always) | `general` |
| "NLP", "language", "text", "dialogue", "translation", "LLM" | + `nlp` |
| "CV", "vision", "image", "detection", "segmentation", "video" | + `cv` |
| unclear / multi-domain | + all (no domain filter) |

The resulting subset becomes the default `--venues` set in scope
confirmation. Always include the `arxiv_only` and `workshop` buckets
regardless. User can override with `--venues <csv>`.

Example: signal `Domain: NLP / multi-step reasoning` →
`inferred_domain_tags: [general, nlp]` → venues:
NeurIPS, ICLR, ICML, AAAI, COLM, ACL, EMNLP, NAACL (drop CVPR/ICCV/ECCV).

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
- inferred domain: <general | general+nlp | general+cv | all>
- venues: <comma-separated venue names from the inferred subset>
- output: <path>

Approve, tweak, or say "abort".
```

One pass only — do NOT re-prompt after approval. If the user requests
changes, apply them and re-show; proceed only after they say OK.

**Ambiguity gate (merged into this step):** If §1 surfaced contradictory
topics, the confirmation is the place to surface that — present the
conflict plainly and let the user pick the direction.

### 3. Parallel search

**Required CWD + venv** for every script call in this section:

    cd "${CLAUDE_PLUGIN_ROOT}/skills/paper-search"
    source "${CLAUDE_PLUGIN_ROOT}/.venv/bin/activate"

Without this, `python -m scripts.X` fails with `ModuleNotFoundError`. Keep
all script calls inside a single bash snippet that sets both, or re-emit the
prefix each call.

Load `config/venues.yaml` from `${CLAUDE_PLUGIN_ROOT}/skills/paper-search/config/`.

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

Pipe the combined array into `dedupe.py` (same CWD/venv as §3):

    cat combined.json | python -m scripts.dedupe

Receive `{category: [paper, ...]}` back. Categories may include truncated
gscholar strings (e.g. `"Proceedings of the …"`) — §4.5 handles these.

### 4.5. Resolve ambiguous venues via PDF (default-on)

When OpenReview is unavailable, gscholar venue strings are often
truncated, and many arXiv papers are actually published at conferences.
Pipe the dedupe output through `resolve_venues.py` to re-classify these
by reading each ambiguous paper's first-page PDF header:

    cat deduped.json | python -m scripts.resolve_venues > resolved.json

`resolve_venues.py`:
  - Skips papers already in a canonical venue bucket (NeurIPS, ICLR, …).
  - For papers in `arxiv_only` or in any non-canonical bucket name
    (truncated gscholar strings), downloads the PDF and matches its header
    text against `pdf_patterns` in `venues.yaml`.
  - Confirmed papers are moved to the correct bucket with
    `"venue_resolution": "pdf"` annotation.
  - Unresolvable papers (no PDF, paywall, or no matching pattern) stay in
    `arxiv_only`.

Best-effort — failures are silent. Use `--no-resolve-venues` to skip this
step entirely (faster).

### 5. Relevance ranking

For each category, read titles + abstracts and pick the top N (default 10)
most relevant to the project context and original queries. Drop the rest.

### 6. Output

Root = `--output` (default `./papers/`). If it exists and `--force` is off,
ask the user before overwriting.

Create:

    papers/
      README.md                        # project summary, queries, counts, Themes/Gaps
      .project_analysis.json           # §1 signals
      <venue>/
        index.md                       # Markdown table
        refs.bib                       # all BibTeX entries concatenated
        YYYY-<firstauthor>-<slug>.md   # per-paper notes (4 anchors + relevance)
        YYYY-<firstauthor>-<slug>/     # per-paper asset directory (same slug)
          figures/
            fig-01.png
            fig-01.txt                 # caption sidecar
            fig-02.png
            fig-02.txt

Categories with zero selected papers: no directory created; count 0 in
README table. **The per-paper asset directory uses the same slug as the
`.md` file** so they stay paired in listings.

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

Four structured anchors (TL;DR, Method, Result, Critical Reading) come
before the project-specific relevance note. These four match the standard
pattern for literature-review note-taking — fill each one even if short.

```markdown
# <Title>

**Authors:** <comma-separated>
**Venue:** <Venue Year>
**Confidence:** <high | medium | low>     <!-- venue match / relevance certainty -->
**Links:** [OpenReview](...) · [arXiv](...) · [PDF](...)

## Abstract
<English abstract, verbatim>

## TL;DR
<Korean, 1 sentence — what this paper is about in one breath>

## Method
<Korean, 1–2 sentences — what the paper proposes or does, the core mechanism>

## Result
<Korean, 1–2 sentences — key findings or numbers. If no numbers available
from abstract, say what improvement claim is made and over what baseline>

## Critical Reading
<Korean, 2–3 bullets — limitations, unstated assumptions, what's missing.
If the abstract alone is not enough to critique, say so and flag what you'd
want to verify in the full paper>

## 왜 이 프로젝트와 관련 있는가
<Korean, 2–4 sentences referencing specific aspects of the project>

## Figures
<!-- Filled in by the figure-extraction step. Omit the section entirely if
     no figures were extracted for this paper (paywall, parse failure). -->
![Figure 1](<slug>/figures/fig-01.png)
> Figure 1: …

![Figure 2](<slug>/figures/fig-02.png)
> Figure 2: …

## BibTeX
​```bibtex
@inproceedings{...}
​```
```

Use the `title_slug` and `first_author_lastname` helpers from
`scripts/common.py` for filename generation if you shell out to Python; or
reproduce their logic directly (lowercase, punctuation stripped, hyphens,
≤ 60 chars).

#### Figure extraction (default-on, skip with `--no-figures`)

After writing each per-paper `.md`, download the paper's PDF and extract
figures into the sibling asset directory:

    echo '<selected_paper.json>' | python -m scripts.get_figures \
        --out-dir "papers/<venue>/<slug>/" \
        --method "<auto|pymupdf|pdffigures2>"

This creates `papers/<venue>/<slug>/figures/fig-NN.png` + `fig-NN.txt`.
The orchestrator (`get_figures.py`) handles download + extraction +
cleanup of the PDF cache by default.

Method selection:
- **pdffigures2** (best) — Allen AI's Scala tool, gold-standard
  figure/caption mapping. Requires Java + pre-built jar referenced by
  `PDFFIGURES2_JAR`. `--method auto` prefers it when set.
- **pymupdf** (fallback) — pure-Python, heuristic caption mapping.

**After extraction**, append a `## Figures` section to the per-paper
`<slug>.md` using **relative paths** that work when viewing from
`<venue>/index.md`:

```markdown
## Figures

![Figure 1](2024-smith-paper/figures/fig-01.png)
> Figure 1: Architecture of the proposed model.

![Figure 2](2024-smith-paper/figures/fig-02.png)
> Figure 2: Main results on benchmark X.
```

Failure handling: figure extraction is **best-effort**. Paywalled PDFs
(common for gscholar landing pages), network errors, or parse failures
yield an empty figures list — append an empty `## Figures` section
header (or omit entirely) and CONTINUE. Never abort the rest of the run.
Surface per-paper figure counts in the final status summary.

## Failure reporting

End the run with a short status summary: which sources returned data,
which were blocked, per-venue counts, and (if `--with-figures` was set)
per-paper figure counts. If Google Scholar was blocked, say so plainly —
the user needs to know that category may be under-covered.
