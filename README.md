# paper-search

A Claude Code skill that analyses the current project, searches **arXiv**,
**OpenReview**, and **Google Scholar**, and writes a venue-organised
related-work directory with per-paper summaries and BibTeX.

Built for ML researchers who switch between topic-specific projects and
need a fast, reproducible way to build a related-work collection.

## What it does

Given a research project (current working directory or a text description),
the skill:

1. Analyses the project context (README, docs, source files).
2. Generates 2–4 English search queries.
3. Searches arXiv + OpenReview + Google Scholar in parallel.
4. Deduplicates results, preferring the conference-published version of
   each paper over its arXiv preprint.
5. Ranks and selects top-N per venue.
6. Writes `./papers/<venue>/` with per-paper Markdown, `index.md`, and
   `refs.bib` (English metadata + Korean summaries).

Target venues (configurable in `config/venues.yaml`): NeurIPS, ICLR, ICML,
COLM, ACL, EMNLP, NAACL, CVPR, ICCV, ECCV, AAAI, plus `arxiv_only` and
`workshop` buckets.

## Install

### Option A — as a Claude Code plugin (recommended)

From inside Claude Code:

```
/plugin marketplace add <owner>/paper-search
/plugin install paper-search@paper-search
```

Then install Python dependencies once (the plugin's scripts need them):

```bash
cd "${CLAUDE_PLUGIN_ROOT}"       # or wherever the plugin was cloned
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Option B — manual dev install

```bash
git clone https://github.com/<you>/paper-search.git
cd paper-search
./install.sh        # creates .venv, installs deps, symlinks skills/paper-search
```

`install.sh` links `skills/paper-search/` into `~/.claude/skills/paper-search`,
runs the full test suite (23 unit tests), and prints next steps.

## OpenReview credentials (optional)

OpenReview requires authentication. Export these env vars in the shell you
launch Claude Code from:

```bash
export OPENREVIEW_USERNAME="..."
export OPENREVIEW_PASSWORD="..."
```

Free registration at <https://openreview.net/signup>. If the vars are
missing, `search_openreview` exits with a clear message and the pipeline
continues with arXiv + Google Scholar only.

## Usage

Inside a Claude Code session, in your project directory:

```
/paper-search                          # default: top 10 per venue
/paper-search --top 15 --years 3       # restrict by recency
/paper-search "LLM agent planning"     # explicit topic override
```

Output lands in `./papers/<venue>/`.

## Development

```bash
source .venv/bin/activate
pytest                     # 23 unit tests, runs in ~2s
pytest -m integration      # opt-in, hits real arXiv
```

Layout:

```
.
├── SKILL.md                  # procedure Claude Code reads
├── scripts/                  # orchestration Python
│   ├── common.py             # Paper dataclass + helpers
│   ├── search_arxiv.py
│   ├── search_openreview.py
│   ├── search_gscholar.py
│   └── dedupe.py
├── tests/
├── config/venues.yaml
├── references/query_generation.md
└── docs/
    ├── specs/                # design spec
    └── plans/                # implementation plan
```

## License

MIT — see `LICENSE`.
