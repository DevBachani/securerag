# PROGRESS

## Current phase: 17 — Streamlit UI
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
| 8 — Cross-encoder reranking | 2026-10-31 | feat(retrieval): cross-encoder reranking with latency measurement | bge-reranker-base via fastembed ONNX (no PyTorch). Retrieve wide -> rerank -> top_n. hit_rate stays 1.0 (saturated); rerank adds ~1.3-2.8s median CPU latency. Best pool=8. 91 tests. |
| 9 — Incremental sync + versioning | 2026-10-31 | feat(ingestion): incremental sync, deletions, versioning and ACL updates | ingest_state (SHA-256 content_hash + meta_hash); sync only re-embeds changed files, deletes removed, updates payload on ACL change. travel v1 trap, is_current filter. ingest.py default=sync. 99 tests. |
| 10 — PII redaction at ingestion | 2026-10-31 | feat(governance): PII redaction with Indian ID recognizers | Regex redactor (EMAIL/+91 PHONE/AADHAAR/PAN) runs before embedding; pii_redacted flag. disciplinary-log trap. 0 planted PII across 132 chunks; budgets intact. 119 tests. |
| 11 — LangGraph agent (router + memory) | 2026-11-01 | feat(agent): langgraph agent with router, memory and checkpointer | State graph: condense -> route (structured) -> retrieve -> generate / action-stub / decline. SQLite checkpointer (thread_id memory). Follow-up condensing + routing + permission refusal verified. docs/graph.png. 121 tests (+2 opt-in). |
| 12 — Self-correcting retrieval | 2026-11-01 | feat(agent): context grading, query rewriting and grounding check | grade_context -> rewrite (max 2) -> retrieve loop; check_grounding -> regenerate once -> refuse. Refusal never reveals a restricted doc. ~4s/question overhead (grade+grounding). 123 tests (+2 opt-in). |
| 13 — Ticket tool + human approval | 2026-11-01 | feat(agent): ticket tool with human-in-the-loop approval | tickets table; draft_ticket (LLM) -> interrupt -> approve: create_ticket / reject: cancel. Idempotent per thread_id; tickets created as self; non-owner can't approve. 128 tests (+4 opt-in). |
| 14 — Guardrails + injection defense | 2026-11-01 | feat(safety): injection tests, guardrails and validated outputs | Poisoned newsletter trap; 15-attack injection set -> attack_success_rate 0.0. guardrails: injection detector, untrusted-context prompt, cite-only-retrieved validation. 141 tests (+5 opt-in). |
| 15 — FastAPI backend | 2026-11-04 | feat(api): fastapi with jwt auth, streaming chat, approvals and audit log | JWT login + per-request group load; SSE chat; ticket approve; own-thread history; /tickets; admin audit/reingest; /health; slowapi per-user limit; CORS to UI; audit row per chat (doc ids, not answers). 147 tests. |
| 16 — Observability (Langfuse) | 2026-11-04 | feat(obs): langfuse tracing, cost and latency reporting | observability.py: graceful Langfuse callback handler (no-op without keys), pseudonymised user ids, trace_content redaction, trace_id linked into audit_log. latency_report.py from the audit log. 150 tests. |

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
- Phase 8 (rule #10): used fastembed's ONNX cross-encoder (TextCrossEncoder) for bge-reranker-base
  instead of the torch-based SentenceTransformerRerank -> no ~1-2 GB PyTorch install on an 8 GB machine.
- Phase 9: `scripts/ingest.py` default is now incremental SYNC; `--reset` does a full rebuild.
  Change detection uses content_hash (file bytes) for re-embed and meta_hash (ACL/version fields) for
  in-place payload updates. Retrieval filters is_current=true so superseded versions are never served.
- Phase 10 (rule #10): used a regex redactor instead of Microsoft Presidio. The policy keeps names and
  redacts only contact/ID PII (all regex-detectable), so Presidio's heavy spaCy NER adds nothing on 8 GB.
  Side effect: org emails (ethics@, secops@) are also redacted to <EMAIL> - acceptable (don't embed emails).
- Phase 11: permission context (user_id, user_groups) lives in agent STATE, set from the session, never
  by the LLM. Routing uses structured output (Pydantic Literal). SQLite checkpointer persists per thread_id.
  Agent integration tests are opt-in (RUN_LLM_TESTS=1) so routine test runs don't spend Groq tokens.
- Phase 12 (rule #10): gpt-oss on Groq throws a tool-call-validation error with the default
  function_calling structured output; use with_structured_output(..., method="json_schema") instead.
  Self-correction is a config flag (self_correction_enabled); measured ~+4s/question for grade+grounding.
  Honest: on this strong-retrieval corpus it rarely changes outcomes (its value is noisy/large corpora).
- Phase 13: human approval is a LangGraph interrupt() (enforced by the graph + checkpointer, outside the
  LLM). Tickets are created as the requesting user; create_ticket is idempotent per thread_id (unique), so
  double-resume creates one ticket. A non-owner cannot approve another user's pending ticket.
- Phase 15: JWT carries only the user id; groups are loaded from the DB on every request (immediate
  permission changes, no tampering). Chat streams over SSE as chunked replay of the completed answer (true
  LLM token streaming via astream is deferred). Audit log stores doc ids + status, never the raw answer.
  slowapi rate-limits per user; CORS restricted to the UI origin; /admin/* requires the admin group.
- Embeddings = BAAI/bge-small-en-v1.5 via fastembed (384-dim), NOT Ollama's nomic-embed-text (768-dim):
  the whole retrieval design (Qdrant collection size, chunk payload, "prints 384" check) is built around 384.
- GitHub: local repo only for now; no remote pushed yet.

## Eval scores so far
| Phase | Config | Faithfulness | Answer relevancy | Context precision | Context recall | Leakage rate |
|---|---|---|---|---|---|---|
| 5 | baseline (Ragas n=4, judge gpt-oss-120b) | 1.00 | n/a* | 0.83 | 0.88 | n/a (Phase 6) |
| 6 | permission-filtered (leakage set, n=20) | - | - | - | - | **0.00** |
| 14 | injection set (n=15) | - | - | - | - | attack_success_rate **0.00** |

Phase 7 retrieval comparison (hit_rate@k, quota-free, all 44 golden questions):
- @12 and @3: dense == hybrid == 1.00 everywhere (dense saturated on this small corpus).
- **@1 keyword: dense 0.75 -> hybrid 1.00**; @1 overall: dense 0.95 -> hybrid 1.00.
- Example only hybrid gets at #1: "fix for ERR-6210" (dense returns the ERR-5002 doc; BM25 matches the exact code).
- leakage_rate stays **0.00** with hybrid (filter on both dense and sparse branches).

Phase 8 reranking (hit_rate@final-k + latency, all 44 questions; eval/results/20261031_rerank_latency.json):
- hybrid @4 no-rerank: hit_rate 1.00, median 744ms, p95 825ms.
- hybrid+rerank pool8->4: 1.00, 2021ms / 2934ms.  pool12->4: 1.00, 2499ms / 3698ms.  pool20->4: 0.975, 3506ms / 5950ms.
- One-liner: reranking left hit_rate unchanged (already saturated at k=4) and added ~1.3-2.8s median
  CPU latency; its real benefit is context precision (needs Ragas / a bigger corpus). Best pool = 8.

\* answer_relevancy came back n/a (Ragas question-generation step returned no output for these samples).
Custom metrics, baseline (n=15, all categories): hit_rate@k **1.00**, citation_accuracy **1.00**, refusal_accuracy **1.00**.
Full 40-question Ragas pass deferred: Groq free tier is 200k tokens/day **per model** and today's runs exhausted gpt-oss-20b; re-run after daily reset (or on gpt-oss-120b).

## Open issues / questions
- Phase 16 observed agent latency ~28s median / ~30s p95 per question (self-correction =
  grade+grounding ≈ 5 Groq calls on gpt-oss-120b). Levers for a snappy UI: disable
  SELF_CORRECTION_ENABLED, use a smaller Groq model, or cache. Decide before Phase 20 deploy.
- Live Langfuse traces need the user's Langfuse Cloud keys + network reachability (sandbox may
  block it like Gemini); the integration is graceful no-op without keys. latency_report works locally.
- Machine has only ~8 GB RAM. llama3.1:8b (4.9 GB) runs but is tight once Qdrant + fastembed +
  (later) the cross-encoder reranker are loaded. Watch for OOM / slowness; fallback = gemma:2b or mistral:7b.
- SPEC.md saved from a truncated paste (cut mid–Section 8). Replace with the full spec when available.
