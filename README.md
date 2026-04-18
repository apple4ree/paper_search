# paper-search skill

Claude Code skill that analyses a research project and builds a venue-organised related-work directory from arXiv, OpenReview, and Google Scholar.

See `docs/superpowers/specs/2026-04-18-paper-search-skill-design.md` for design and `docs/superpowers/plans/2026-04-18-paper-search-skill.md` for the implementation plan.

## Install (after implementation)

    ln -s /home/dgu/skill_paper_search/paper-search ~/.claude/skills/paper-search
    cd paper-search && python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
