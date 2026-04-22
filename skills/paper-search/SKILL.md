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
`scholarly`, `pyyaml`, `requests`, and `pymupdf` (for PDF reading).
**Every script invocation in this skill must happen inside the plugin's
venv**, which lives at `${CLAUDE_PLUGIN_ROOT}/.venv`.

**Bootstrap check** (run this first, once per session — safe to re-run):

    cd "${CLAUDE_PLUGIN_ROOT}"
    if [ ! -d .venv ]; then
        python -m venv .venv
    fi
    source .venv/bin/activate
    # If the plugin was updated, requirements.txt may have new deps —
    # `pip install -r requirements.txt` is idempotent and fast when
    # everything is already there.
    python -c "import arxiv, openreview, scholarly, yaml, requests, fitz" 2>/dev/null \
        || pip install -r requirements.txt

After a `/plugin marketplace update paper-search`, re-run this bootstrap
once — new dependencies (e.g. `pymupdf`) won't be auto-installed by the
plugin system.

If the user cannot install deps, stop and report — do not proceed with
broken imports.

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
| `--no-extract` | off | Skip §6 (no per-paper folder; index-only output) |
| `--no-figures` | off | Run §6 but without figure crops (raw.md text only) |
| `--no-summary` | off | Run §6 but skip §7 LLM summary writing (raw.md + figures + paper_meta only) |
| `--no-resolve-venues` | off | Skip §4.5 PDF-based venue resolution |

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

Draft **3–5 English queries**, each **2–5 content words, one concept only**,
per `references/query_generation.md`, using the structured signals from §1.

**Anti-pattern**: stuffing multiple concepts into one long query (e.g.
`order flow imbalance limit order book short-term price prediction` —
three concepts, few matches). Split into separate queries instead.

Each query should map to one of:
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

### 6. Per-paper folder build (Python, §6 = `build_paper_folder.py`)

Root = `--output` (default `./papers/`). If it exists and `--force` is off,
ask the user before overwriting.

For each selected paper (§5 output), run:

    echo '<paper.json>' | python -m scripts.build_paper_folder \
        --out-dir "papers/<Venue>/" \
        --index <N> \
        --method <TRANSFORMER|DPO|...>  # optional, skip if unclear

This downloads the PDF, extracts structured content, and writes:

    papers/<Venue>/<NN_firstauthoryearMETHOD(venueYear)>/
      raw.md                          # page-by-page text + figure index + embeds
      paper_meta.json                 # paper dict + extraction summary
      figures/
        fig1.png, fig2.png, ...       # main content figures (sequentially renumbered)
        figA1.png, figA2.png, ...     # appendix figures
        _pages/
          p-01.png, p-02.png, ...     # 200dpi full-page renders (manual re-crop fallback)

**METHOD token**: extract a short acronym from title/abstract (e.g., `DPO`,
`LoRA`, `TRANSFORMER`). If no obvious acronym, omit `--method` — folder
becomes `01_vaswani2017(NeurIPS2017)`.

**PDF-unavailable papers** (paywalled, gscholar landing pages): the script
returns `{"status": "failed"}` — do NOT create the folder, but DO write a
minimal stub at `papers/<Venue>/<NN_...>_NO_PDF.md` containing just the
metadata and abstract from the search result, so the paper is still listed.

**Root output files** (regardless of per-paper success):

    papers/
      README.md                       # §8 synthesis (Themes/Convergences/Gaps)
      .project_analysis.json          # §1 signals
      <Venue>/
        index.md                      # folder list with one-line relevance per paper
        refs.bib                      # all BibTeX entries concatenated

Categories with zero selected papers: no directory created.

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

### 7. LLM summary writing (Claude, §7)

For each per-paper folder that §6 produced successfully, read
`references/writing_rules.md`, `templates/summary.md`, `templates/abstract.md`,
and the folder's `raw.md` + `paper_meta.json`. Write two files in-place:

- `summary.md` — full structured summary (메타 + TL;DR + 기여 + Glossary +
  Section별 상세 + Figure embed + 인용 선행연구 + **§ 왜 이 프로젝트와 관련 있는가**)
- `abstract.md` — 경량 검색용 파일 (메타 + 원문 abstract + **한글 번역 (필수)**
  + 관련성 한 줄)

**Required**:
- Abstract 한글 번역은 **필수** — `abstract.md` 에도, `summary.md` 의 Abstract
  섹션에도 포함. 의역 OK, 수치/모델명/약어/기호는 원문 보존.
- 두 파일 간 메타·원문·번역은 **동일 문구**.
- `§ 왜 이 프로젝트와 관련 있는가` 는 `.project_analysis.json` 의 signal 기반
  2–4 문장. summary.md 만이 이 섹션을 가짐.

**Skip with `--no-summary`** — raw.md / figures / paper_meta.json 만 남기고
Claude 가 summary/abstract 를 쓰지 않음.

### 8. Cross-paper synthesis (Claude, §8)

Read the selected papers together (abstracts + key methods) and write
`papers/README.md`. **Never skip this step** — it converts the output from a
reading list into a literature-review starter.

## Failure reporting

End the run with a short status summary: which sources returned data,
which were blocked, per-venue counts, and (if `--with-figures` was set)
per-paper figure counts. If Google Scholar was blocked, say so plainly —
the user needs to know that category may be under-covered.
