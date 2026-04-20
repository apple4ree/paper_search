# paper-search

A Claude Code skill (packaged as a plugin) that analyses the current
project, searches **arXiv**, **OpenReview**, and **Google Scholar**, and
writes a venue-organised related-work directory with per-paper summaries,
BibTeX, and cross-paper synthesis.

Built for ML researchers who switch between topic-specific projects and
need a fast, reproducible way to build a related-work collection.

## What it does

Given a research project (current working directory) the skill:

1. **Analyses** the project context (README, `docs/`, dependency manifests,
   folder tree, recent commits) and extracts structured signals (domain,
   problem, method keywords, benchmarks, baselines, scale). Persisted as
   `papers/.project_analysis.json`.
2. **Generates** 2–4 English search queries from the signals.
3. **Infers venue subset** from the domain signal (NLP project → NLP
   venues + general ML; CV project → CV venues + general ML; unknown → all).
4. **Scope confirmation** — shows the draft summary, queries, and scope,
   waits for user approval.
5. **Searches** arXiv + OpenReview + Google Scholar in parallel.
6. **Deduplicates** with venue-wins merging (conference version beats
   arXiv preprint).
7. **Ranks and selects** top-N per venue.
8. **Writes** `./papers/<venue>/` with per-paper Markdown (English abstract
   + Korean TL;DR/Method/Result/Critical Reading/프로젝트 관련성), a venue
   `index.md`, and concatenated `refs.bib`. Root `README.md` includes
   cross-paper **Themes / Convergences / Disagreements / Gaps**.

Target venues (configurable in `skills/paper-search/config/venues.yaml`):

| Tag | Venues |
|---|---|
| `general` | NeurIPS, ICLR, ICML, AAAI |
| `nlp` | ACL, EMNLP, NAACL, COLM |
| `cv` | CVPR, ICCV, ECCV |

Plus `arxiv_only` and `workshop` buckets.

## Install

### Option A — as a Claude Code plugin (recommended)

From inside Claude Code:

```
/plugin marketplace add apple4ree/paper_search
/plugin install paper-search@paper-search
```

Then install Python dependencies once:

```bash
cd "${CLAUDE_PLUGIN_ROOT}"
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Option B — manual dev install

```bash
git clone https://github.com/apple4ree/paper_search.git
cd paper_search
./install.sh        # creates .venv, installs deps, symlinks skills/paper-search
```

`install.sh` links `skills/paper-search/` into
`~/.claude/skills/paper-search`, runs the full test suite (23 unit tests),
and prints next steps.

## OpenReview credentials (optional but recommended)

OpenReview requires authentication. Export these env vars in the shell you
launch Claude Code from:

```bash
export OPENREVIEW_USERNAME="..."
export OPENREVIEW_PASSWORD="..."
```

Free registration at <https://openreview.net/signup>. If the vars are
missing, `search_openreview` exits with a clear message and the pipeline
continues with arXiv + Google Scholar only — but venue classification
quality drops, since arXiv and Google Scholar venue strings are often
truncated.

## Usage

Inside a Claude Code session, in any project directory:

```
/paper-search                          # default: top 10 per venue
/paper-search --top 15 --years 3       # restrict by recency
/paper-search "LLM agent planning"     # explicit topic override
```

Output lands in `./papers/` with this structure:

```
papers/
├── README.md                   # project summary, queries, per-venue counts,
│                               # Themes / Convergences / Disagreements / Gaps
├── .project_analysis.json      # structured signals extracted from §1
├── <Venue>/
│   ├── index.md                # Markdown table of selected papers
│   ├── refs.bib                # all BibTeX entries
│   └── YYYY-firstauthor-slug.md    # per-paper notes (4 anchors + relevance)
├── arxiv_only/
└── workshop/
```

Per-paper file contents:

- **TL;DR** (Korean) — one sentence
- **Method** (Korean) — what the paper does
- **Result** (Korean) — key findings
- **Critical Reading** (Korean) — limitations, assumptions
- **왜 이 프로젝트와 관련 있는가** (Korean) — project-specific relevance
- **Confidence** — `high | medium | low` for venue classification / relevance
- **BibTeX** — ready to copy

## Development

```bash
source .venv/bin/activate
pytest                     # 23 unit tests, runs in ~2s
pytest -m integration      # opt-in, hits real arXiv
```

Layout:

```
.
├── .claude-plugin/
│   ├── plugin.json             # plugin manifest
│   └── marketplace.json        # lets GitHub serve as a marketplace
├── skills/
│   └── paper-search/
│       ├── SKILL.md            # procedure Claude Code follows
│       ├── scripts/
│       │   ├── common.py       # Paper dataclass + helpers
│       │   ├── search_arxiv.py
│       │   ├── search_openreview.py
│       │   ├── search_gscholar.py
│       │   └── dedupe.py
│       ├── config/venues.yaml  # venue list with domain tags
│       └── references/query_generation.md
├── tests/                      # unit + opt-in integration
├── requirements.txt
├── install.sh                  # dev install
└── docs/
    ├── specs/                  # design spec
    └── plans/                  # implementation plan
```

## License

MIT — see `LICENSE`.
