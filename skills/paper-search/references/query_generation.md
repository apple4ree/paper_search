# Generating Paper Search Queries

## Goal

Produce **2–4 English queries** that collectively cover the project's central
topic. Each query is a phrase, not a question. They are sent verbatim to
arXiv / OpenReview / Google Scholar keyword search.

## Principles

1. **Be concrete.** "reasoning" is too broad; "chain-of-thought reasoning
   distillation small language models" is searchable.
2. **Cover multiple angles.** If the project has a method and a benchmark,
   make one query per angle.
3. **Prefer the terminology a paper author would use.** e.g.,
   "retrieval-augmented generation" > "RAG with extra knowledge".
4. **Drop stop words.** No "the", "a", "how to".
5. **Keep each query 3–10 content words.**

## Good examples

- `chain-of-thought reasoning distillation small language models`
- `tool-augmented LLM agent planning benchmark`
- `constrained decoding structured output LLM`
- `retrieval-augmented generation long context evaluation`

## Bad examples (and why)

- `LLM` — too broad, will flood with unrelated work.
- `how do I distill reasoning into smaller models` — natural-language,
  search engines down-weight filler words.
- `Chen et al 2024 method` — cites a specific author; use the concept.

## When to ask the user first

If the working-directory signal is weak or mixes unrelated topics, present
the draft analysis and query list for one-time confirmation before running
the search (see `SKILL.md` §Ambiguity Gate).
