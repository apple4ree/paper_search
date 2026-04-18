# paper-search Skill — Design

**Date:** 2026-04-18
**Author:** dami.dgu@gmail.com
**Status:** Design (pre-implementation)

## 1. Purpose

A Claude Code skill that, when invoked from within a research project directory, autonomously:

1. Analyzes the project (reading files in the working directory and/or a user-supplied text description).
2. Generates targeted paper-search queries.
3. Searches arXiv, Google Scholar, and OpenReview in parallel.
4. Deduplicates results, preferring conference-published versions over preprints.
5. Organizes selected papers into a per-venue directory layout with summaries and BibTeX.

Primary user: master's-level ML researcher who regularly switches between topic-specific projects and needs a fast, reproducible way to build a venue-organized related-work collection.

## 2. Scope

**In scope:**
- arXiv, Google Scholar, OpenReview as paper sources.
- Fixed list of ML/AI top venues plus `arxiv_only` and `workshop` categories.
- Free-form Claude-driven project analysis (no rigid template).
- Per-venue Markdown index + per-paper Markdown summary + per-venue BibTeX.
- Bilingual output: English metadata, Korean summaries and relevance notes.

**Out of scope:**
- PDF download / full-text analysis.
- Citation graph traversal / forward-reverse citation expansion.
- Semantic Scholar, DBLP, ACL Anthology direct integration.
- Continuous watching / scheduled re-runs (skill is invoked on demand).

## 3. Invocation

**Skill location:** `~/.claude/skills/paper-search/` (global) or project-local `.claude/skills/paper-search/`.

**Trigger:** `/paper-search` slash command, or natural-language request (e.g., "이 프로젝트 관련 논문 찾아줘").

**Default behaviour:** treat current working directory as the project; read README, `docs/`, top-level source files, and notes to form an understanding. If the directory is empty or ambiguous, ask the user for a short text description.

**Optional arguments (natural-language or flag form):**

| Flag | Default | Meaning |
|------|---------|---------|
| `--top N` | `10` | Max papers per venue/category after ranking |
| `--years Y` | unrestricted | Only keep papers published within last Y years |
| `--output <path>` | `./papers/` | Output directory root |
| `--venues <list>` | all in `venues.yaml` | Restrict to a subset of venues |
| `--force` | off | Overwrite existing output directory without prompt |

**Examples:**
```
/paper-search
/paper-search --top 15 --years 3
/paper-search "LLM agent planning"      # topic override
```

## 4. Skill Package Layout

```
paper-search/
├── SKILL.md                    # Main procedure (Claude reads this)
├── scripts/
│   ├── search_arxiv.py         # arXiv API → JSON on stdout
│   ├── search_openreview.py    # openreview-py → JSON on stdout
│   ├── search_gscholar.py      # scholarly → JSON on stdout
│   └── dedupe.py               # Merge sources, apply venue-wins dedup
├── config/
│   └── venues.yaml             # Target venues + OpenReview venue IDs
├── requirements.txt            # arxiv, openreview-py, scholarly, pyyaml
├── requirements-dev.txt        # pytest, pytest-mock, responses
├── tests/
│   ├── test_arxiv.py
│   ├── test_openreview.py
│   ├── test_gscholar.py
│   └── test_dedupe.py
└── references/
    └── query_generation.md     # Guidance Claude reads when building queries
```

### 4.1 Script I/O contract

Every search script implements the same CLI and JSON schema so Claude can orchestrate them uniformly.

**Common CLI:**
```
<script> --query "<text>" --top N [--years Y] [--venue <name>]
```
`--venue` is only honored where the source supports venue filtering (i.e., `search_openreview.py`). For arXiv and Google Scholar, venue is assigned post-hoc by `dedupe.py` from metadata.

**Stdout (JSON array):**
```json
[
  {
    "title": "…",
    "authors": ["First Last", "…"],
    "year": 2024,
    "venue": "NeurIPS" | "arxiv" | "workshop" | null,
    "abstract": "…",
    "url": "https://…",
    "pdf_url": "https://…",
    "arxiv_id": "2401.12345" | null,
    "doi": "10.…" | null,
    "source": "arxiv" | "openreview" | "gscholar"
  }
]
```

**Errors:** logged to stderr; non-zero exit code.

### 4.2 `venues.yaml`

Initial list (extensible; user may add more before implementation):

```yaml
venues:
  - { name: NeurIPS,  openreview_id: NeurIPS.cc }
  - { name: ICLR,     openreview_id: ICLR.cc }
  - { name: ICML,     openreview_id: ICML.cc }
  - { name: ACL }
  - { name: EMNLP }
  - { name: NAACL }
  - { name: CVPR }
  - { name: ICCV }
  - { name: ECCV }
  - { name: AAAI }
  - { name: COLM,     openreview_id: colmweb.org }

special_categories:
  - arxiv_only    # Preprints without a matching venue publication
  - workshop      # Workshop papers (flagged by OpenReview venue metadata)
```

Venues without an `openreview_id` are reached only through arXiv/Google Scholar matches; `dedupe.py` assigns the venue name from paper metadata (journal/booktitle string pattern match).

## 5. Pipeline

Six stages, orchestrated by Claude per `SKILL.md`:

1. **Context gathering** — Read README, `docs/`, notable source files, notes in the working directory. If results are insufficient, prompt the user for a short project description.

2. **Analysis & query generation** — Claude freely analyses gathered context and produces **2–4 English search queries** tuned for academic search (see `references/query_generation.md`). Examples:
   - `"chain-of-thought reasoning distillation small language models"`
   - `"tool-augmented LLM agent planning benchmark"`

3. **Parallel search** — For each query, call each source in parallel:
   - `search_arxiv.py` — one call per query.
   - `search_openreview.py` — one call per (query × venue with `openreview_id`).
   - `search_gscholar.py` — one call per query.

   Aggregated results flow into stage 4.

4. **Deduplication & classification** (`dedupe.py`):
   - **Dedup key priority:** `doi` → `arxiv_id` → `normalize(title) + first_author_last_name`.
   - **Venue-wins rule:** if the same paper appears with a conference venue and as an arXiv preprint, keep the conference record (and record the arXiv URL in the merged entry).
   - **Classification:** each surviving record is assigned to exactly one of `{<venue>, arxiv_only, workshop}`. Venue assignment from either OpenReview metadata or pattern-matched `journal`/`booktitle` fields.

5. **Relevance ranking** — Claude reads each category's deduped list alongside the original queries and selects top-N per category (default N = 10, overridable). Ranking is qualitative; Claude judges relevance from title + abstract + original project context.

6. **Output generation** — Claude writes the directory tree described in §6. Categories with zero results do **not** get a directory.

## 6. Output Layout

Root path defaults to `./papers/` under the project.

```
papers/
├── README.md                   # Overall summary: project analysis, queries, per-venue counts, timestamp
├── NeurIPS/
│   ├── index.md
│   ├── refs.bib
│   ├── 2024-smith-chain-of-thought-distillation.md
│   └── …
├── ICLR/
│   └── …
├── arxiv_only/
│   └── …
└── workshop/
    └── …
```

### 6.1 Root `README.md`

- Project summary (Korean, Claude-written, based on stage 1 analysis).
- Search queries used (English, verbatim).
- Per-venue result count table.
- Run metadata: timestamp, skill version, argument values.

### 6.2 `<venue>/index.md`

Markdown table:

```markdown
# NeurIPS

| # | Title | Year | Authors | 관련성 |
|---|-------|------|---------|-------|
| 1 | [Chain-of-Thought Distillation…](2024-smith-…) | 2024 | Smith et al. | 본 프로젝트의 핵심 기법과 직접 관련 |
```

### 6.3 Per-paper `YYYY-firstauthor-slug.md`

```markdown
# <Title>

**Authors:** …
**Venue:** NeurIPS 2024
**Links:** [OpenReview](…) · [arXiv](…) · [PDF](…)

## Abstract
<English abstract, verbatim>

## 한줄 요약
<Korean, Claude-written>

## 왜 이 프로젝트와 관련 있는가
<Korean, Claude-written, 2–4 sentences tying paper to project context>

## BibTeX
​```bibtex
@inproceedings{…}
​```
```

### 6.4 `<venue>/refs.bib`

All BibTeX entries for that venue, concatenated, ready to paste into a writing project.

### 6.5 File naming

`YYYY-firstauthorlastname-titleslug.md`, all lowercase, hyphen-separated, slug truncated to ≲ 60 chars.

### 6.6 Idempotency

If `./papers/` already exists, confirm with user before overwriting; `--force` skips confirmation.

## 7. Error Handling

**Per-source failure modes:**
- **arXiv:** 3× retry with exponential backoff on network errors. Final failure → stderr warning, empty result for that query.
- **OpenReview:** Per-venue independent calls. A single venue failure only skips that venue. Wholesale OpenReview failure → warning + category skipped.
- **Google Scholar:** Treat HTTP 429/503/captcha pages as blocks. One retry only. Final failure → loud warning surfaced to user in the final report. Pipeline proceeds with remaining sources.

**Missing dependencies:** if `requirements.txt` packages are not importable, instruct user to `pip install -r requirements.txt` before proceeding.

**Zero results:**
- Globally empty → queries likely too narrow. Claude regenerates broader queries once; if still empty, report to user and exit without creating empty directories.
- Empty for a specific venue → that venue is omitted from the tree; README notes `0 results`.

**Ambiguous analysis:** If the working directory signal is weak or contradictory (multiple unrelated topics), Claude presents its draft analysis and proposed queries to the user for a single confirmation gate before running searches. This overrides the normal free-form analysis flow.

**Total network failure:** If every source fails, emit a clear error message and exit without creating any files.

**Rate limiting:** Each script enforces per-source delay internally. Claude's parallel orchestration caps concurrency per source: arXiv 3, OpenReview 2, Google Scholar 1.

## 8. Testing

**Unit tests** (each script, with mocks):
- `search_arxiv.py`: mock HTTP response → validate output JSON schema (all required fields present).
- `search_openreview.py`: stub `openreview-py` client → validate schema.
- `search_gscholar.py`: stub `scholarly` calls → validate schema + HTTP 429 path produces correct non-zero exit code.
- `dedupe.py`: fixture containing (a) same paper in arXiv + NeurIPS, (b) arXiv-only paper, (c) two papers with same title but different authors → verify venue-wins rule, dedup key priority, correct category assignment.

**Integration tests** (real network, one test only):
- Run `search_arxiv.py` with a generic query (e.g., "transformer attention") → assert ≥ 0 results and valid JSON. OpenReview and Google Scholar are excluded from automated integration tests due to flakiness; they are covered by the manual smoke test below.

**Manual smoke test:**
- Create a minimal fixture project (single README.md describing a topic) and invoke the skill. Verify that `papers/` is produced with at least one venue directory containing a valid `index.md`, a paper `.md`, and `refs.bib`.

**Frameworks:** `pytest`, `pytest-mock`, `responses` (for HTTP mocking) declared in `requirements-dev.txt`.

**Not unit-tested:** Claude-authored content (analysis, query generation, Markdown formatting, relevance ranking). Quality is governed by `SKILL.md` and `references/query_generation.md` rather than code tests.

## 9. Open Items Before Implementation

- Final venue list (user may want to add Robotics/Systems/IR venues depending on lab scope).
- Exact shape of `SKILL.md` procedure — to be drafted during implementation plan.
- Whether to pin Python versions or document a minimum (likely ≥ 3.10).
