# Generating Paper Search Queries

## Goal

Produce **3–5 English queries**, each covering **one concept only**. Each
query is a phrase of **2–5 content words**, not a compound stuffing of
multiple concepts. They are sent verbatim to arXiv / OpenReview / Google
Scholar keyword search.

## Core rule: one concept per query ★

Keyword search treats terms as conjunctive — more words = narrower result
set = lower recall. If you have three concepts to cover, emit **three
queries**, not one query with all three concepts concatenated.

Rather than one 8-word query, prefer 3–5 queries of 2–5 words each.

## Principles

1. **One concept per query.** If the project touches "order-flow imbalance",
   "limit order book", and "mid-price prediction", that is THREE queries,
   not one.
2. **Be concrete on the core concept.** `reasoning` alone is too broad;
   `chain-of-thought distillation` pins it down in 3 words.
3. **Prefer the terminology a paper author would use.** e.g.,
   `retrieval-augmented generation` > `RAG with extra knowledge`.
4. **Drop stop words and hedging.** No `the`, `a`, `how to`, `short-term`,
   `via`, `towards`.
5. **Keep each query 2–5 content words.** If you find yourself writing
   more than 5 words, split into multiple queries.

## Good examples

Project: "LLM-generated trading code at tick-level LOB"
- ✅ `order flow imbalance prediction`
- ✅ `limit order book deep learning`
- ✅ `microprice high-frequency trading`
- ✅ `LLM code generation trading`
- ✅ `specification fidelity backtest`

Project: "CoT distillation for sub-3B LMs"
- ✅ `chain-of-thought distillation small language models`   (4 words — OK, one concept)
- ✅ `rationale-based knowledge distillation`
- ✅ `multi-step reasoning benchmark`
- ✅ `teacher student LLM reasoning`

## Bad examples (and why)

- ❌ `LLM` — too broad, 100k+ results.
- ❌ `how do I distill reasoning into smaller models` — natural-language,
  filler words tank ranking.
- ❌ `Chen et al 2024 method` — cites a specific author; use the concept.
- ❌ `order flow imbalance limit order book short-term price prediction`
  — **concept-stuffing**. Three concepts in one query. Likely returns
  fewer than 10 results because few papers mention ALL three. Split:
  `order flow imbalance prediction` + `limit order book price movement`
  + `microprice mid-price direction`.
- ❌ `deep learning limit order book price movement prediction` —
  redundant ("deep learning" + "prediction" + "price movement" are
  near-synonyms in this context). Trim to `limit order book deep learning`.

## When in doubt, split

If you can insert "AND" between any two adjacent words in your draft query
without changing meaning, you have two concepts — split them:

- `order flow imbalance [AND] limit order book` → split
- `LLM [AND] trading strategy [AND] code generation` → split to 2–3 queries
- `chain-of-thought distillation` — no natural AND boundary, keep whole

## When to ask the user first

If the working-directory signal is weak or mixes unrelated topics, present
the draft analysis and query list for one-time confirmation before running
the search (see `SKILL.md` §2 Scope confirmation). Shorter queries make
this review easier — the user can spot missing concepts at a glance.
