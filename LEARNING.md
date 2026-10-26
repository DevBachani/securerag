# LEARNING

Your own notes, one short entry per phase: what you built, why, and one thing
that surprised you. Write it in your own words after the deep dive.

## Phase 0 — Environment setup
_(write your notes here)_

## Phase 1 — Synthetic corpus and manifest
_(write your notes here: why checkable facts matter, where real ACLs come from, synthetic-data biases)_

## Phase 2 — Configuration and model providers
_(write your notes here: the factory pattern, what backoff protects against, why cache embeddings not answers)_

## Phase 3 — Ingestion pipeline
_(write your notes here: chunk-size trade-offs, heading-first splitting, payload indexes, idempotency)_

## Phase 4 — Baseline RAG with citations

Baseline run (Groq openai/gpt-oss-120b, dense-only retrieval, top-6 chunks to generator):
- 8 answerable questions: **7 correct with the right citation**, 1 miss.
- 2 unanswerable questions: **both correctly refused**.

What failed, honestly:
- **ERR-4021 postmortem question** ("what caused it and how was it fixed?") was **refused**.
  Not a pure retrieval miss: the postmortem ranked #1 and #5 (both sent to the generator), but
  heading-chunking split it and the "Resolution / fix" chunk ranked **#12** (not sent). The model
  had the cause but not the fix, so it refused rather than answer partially. Motivates reranking
  (Phase 8), context grading + rewrite (Phase 12), and shows a chunking side-effect.

Surprises / fixes during the phase:
- **Model cited with full-width brackets** 【1】 (gpt-oss), not ASCII [1]; the parser now accepts
  both. Lesson: never assume the model follows the exact citation syntax you asked for.
- **8 GB RAM can't run local 7-8B models** for RAG (llama3.1 >7 min/answer) -> switched to Groq.
- Groq retired all Llama chat models (2026-08-16); using openai/gpt-oss-120b (generator) and
  qwen/qwen3.8-27b (judge, different family -> less self-preference bias).

_(add your own reflection: why number context chunks, what causes hallucinated citations, cost of larger top-k)_
