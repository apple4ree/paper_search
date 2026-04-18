# paper-search skill

Claude Code skill that analyses a research project and builds a venue-organised related-work directory from arXiv, OpenReview, and Google Scholar.

See `docs/superpowers/specs/2026-04-18-paper-search-skill-design.md` for design and `docs/superpowers/plans/2026-04-18-paper-search-skill.md` for the implementation plan.

## Install

    ln -s /home/dgu/skill_paper_search/paper-search ~/.claude/skills/paper-search
    cd paper-search && python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt

OpenReview requires authentication; export credentials before use:

    export OPENREVIEW_USERNAME="..."
    export OPENREVIEW_PASSWORD="..."

Free signup at https://openreview.net/signup.

## Usage

Inside Claude Code, in any project directory:

    /paper-search                        # default: top 10 per venue
    /paper-search --top 15 --years 3     # restrict by recency
    /paper-search "LLM agent planning"   # explicit topic override

Output lands in `./papers/<venue>/` with per-paper `.md`, `index.md`, and `refs.bib`.

## Development

    cd paper-search
    source .venv/bin/activate
    pytest                       # unit tests (23 tests, default)
    pytest -m integration        # opt-in, hits arXiv
