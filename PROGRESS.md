# PROGRESS

## Current phase: 8 — Cross-encoder reranking
## Status: not started

## Environment
- OS / RAM / GPU: Windows 11 Home (10.0.27965) / ~8 GB RAM / no dedicated GPU
- LLM provider in use: groq (generator: openai/gpt-oss-120b, judge: qwen/qwen3.8-27b) — switched from
  Ollama in Phase 4 because 8 GB RAM can't run local 7-8B models at usable speed (llama3.1 >7 min/answer)
- Python version: 3.12.4 (project pinned to >=3.11); uv 0.13.4
- Docker: 29.1.3 + Compose v2.40.3 (Docker Desktop)

## Completed phases
| Phase | Date | Commit | Notes |
|---|---|---|---|
| 0 — Environment setup | 2026-10-26 | chore: project setup, qdrant, smoke test | Smoke test 3/3: LLM OK, embed 384, Qdrant up. Ollama/llama3.1. |
| 1 — Synthetic corpus and manifest | 2026-10-26 | feat(data): synthetic Acme corpus with ACL manifest | 26 docs (23 md + 3 pdf), manifest + FACTS.md, 55 manifest tests pass. Traps excluded. |
| 2 — Configuration and model providers | 2026-10-26 | feat(core): settings and pluggable model providers | Settings + factories (llm/judge/embed/reranker/langchain), tenacity backoff, diskcache embed cache. 63 tests, smoke 3/3. Reranker/gemini lazy. |
| 3 — Ingestion pipeline | 2026-10-26 | feat(ingestion): chunking, embeddings and qdrant upsert with ACL payload | 26 files -> 122 chunks -> 122 points, idempotent (UUID5 ids). Dense-only, payload indexes. 68 tests. |
| 4 — Baseline RAG with citations | 2026-10-26 | feat(rag): baseline dense RAG with citations | Dense retrieve + cited answers via Groq. Baseline: 7/8 answerable correct, 2/2 unanswerable refused, 1 miss (ERR-4021 fix chunk ranked #12). 74 tests. |
| 5 — Golden eval set + baseline | 2026-10-31 | feat(eval): golden set, ragas + custom metrics, baseline results | 40-question golden set; run_eval.py (4 Ragas + 3 custom). Custom baseline (15Q): hit_rate/citation/refusal = 1.0. Ragas sample (4Q): faithfulness 1.0, ctx_precision 0.83, ctx_recall 0.88. Full Ragas run deferred (Groq daily token cap). |
| 6 — ACLs + permission-filtered retrieval | 2026-10-31 | feat(security): group ACLs and permission-filtered retrieval with leakage tests | SQLModel users/groups + seed_users; build_filter inside the Qdrant query + defense-in-depth check; 20-question leakage set -> leakage_rate 0.0. 85 tests. |
| 7 — Hybrid search (BM25 + dense) | 2026-10-31 | feat(retrieval): hybrid BM25 + dense search with RRF | Named dense+sparse vectors, RRF fusion, permission filter on both branches. hit_rate@1 keyword: dense 0.75 -> hybrid 1.00. leakage still 0.0. 89 tests. |

## Key decisions (and why)
- LLM = Ollama / llama3.1:latest (local): no API key, no free-tier limits; machine already has it installed.
- Phase 2: reranker, Gemini, and LangChain-Groq backends are lazy-imported (clear error if called) so
  PyTorch and unused SDKs are not installed until the phase that needs them (reranker -> Phase 8).
- src/ layout: `pythonpath = ["src"]` in pytest config makes `securerag` importable without an install step.
- Phase 3: added a hatchling build-system so `uv` installs `securerag` editable -> scripts can import it.
- Phase 3 (rule #10): `pymupdf4llm==2.0` on PyPI is a broken/placeholder wheel (no module, no deps).
  Pinned the genuine `pymupdf4llm==0.0.27` (requires pymupdf>=1.26.3) instead.
- Phase 4 (rule #10): Groq retired all Llama chat models (2026-08-16). Using openai/gpt-oss-120b
  (generator, Llama-70B-class replacement) and qwen/qwen3.8-27b (judge). Model ids read from the
  live /models endpoint, not hard-coded.
- Phase 4: generator sees only top ANSWER_CONTEXT_CHUNKS (6) of RETRIEVAL_TOP_K (12); keeps prompts
  small. Citation parser accepts ASCII [1] and full-width 【1】 brackets (gpt-oss emits the latter).
- Phase 5 (rule #10): judge = Groq gpt-oss-20b (qwen failed Ragas structured output -> faithfulness 0.0).
  Groq free tier = 200k tokens/day per model; heavy Ragas runs exhaust it, so run_eval has --no-ragas
  (custom metrics only) and --ids (subset). Ragas 0.4.3 needs a vertexai import shim (langchain v1 dropped it).
- Phase 5: Google Gemini is UNUSABLE from this sandbox - generateContent inference times out via BOTH
  REST and the SDK, with free and premium keys (network egress block; metadata GETs work). Not an account
  issue. JUDGE_PROVIDER=gemini path is wired and would work on a normal machine.
- Phase 6 (rule #10): passlib 1.7.4 is unmaintained and crashes with bcrypt 5.x; use the bcrypt library
  directly for password hashing instead.
- Phase 6: permission filter is applied INSIDE the Qdrant query (pre-filtering), with an independent
  is_allowed() post-check for defense in depth. leakage_rate measured at retrieval -> quota-free.
- Embeddings = BAAI/bge-small-en-v1.5 via fastembed (384-dim), NOT Ollama's nomic-embed-text (768-dim):
  the whole retrieval design (Qdrant collection size, chunk payload, "prints 384" check) is built around 384.
- GitHub: local repo only for now; no remote pushed yet.

## Eval scores so far
| Phase | Config | Faithfulness | Answer relevancy | Context precision | Context recall | Leakage rate |
|---|---|---|---|---|---|---|
| 5 | baseline (Ragas n=4, judge gpt-oss-120b) | 1.00 | n/a* | 0.83 | 0.88 | n/a (Phase 6) |
| 6 | permission-filtered (leakage set, n=20) | - | - | - | - | **0.00** |

Phase 7 retrieval comparison (hit_rate@k, quota-free, all 44 golden questions):
- @12 and @3: dense == hybrid == 1.00 everywhere (dense saturated on this small corpus).
- **@1 keyword: dense 0.75 -> hybrid 1.00**; @1 overall: dense 0.95 -> hybrid 1.00.
- Example only hybrid gets at #1: "fix for ERR-6210" (dense returns the ERR-5002 doc; BM25 matches the exact code).
- leakage_rate stays **0.00** with hybrid (filter on both dense and sparse branches).

\* answer_relevancy came back n/a (Ragas question-generation step returned no output for these samples).
Custom metrics, baseline (n=15, all categories): hit_rate@k **1.00**, citation_accuracy **1.00**, refusal_accuracy **1.00**.
Full 40-question Ragas pass deferred: Groq free tier is 200k tokens/day **per model** and today's runs exhausted gpt-oss-20b; re-run after daily reset (or on gpt-oss-120b).

## Open issues / questions
- Machine has only ~8 GB RAM. llama3.1:8b (4.9 GB) runs but is tight once Qdrant + fastembed +
  (later) the cross-encoder reranker are loaded. Watch for OOM / slowness; fallback = gemma:2b or mistral:7b.
- SPEC.md saved from a truncated paste (cut mid–Section 8). Replace with the full spec when available.
