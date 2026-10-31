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

## Phase 5 — Golden eval set + baseline

Built a 40-question golden set (20 factual, 6 table, 6 multi_hop, 4 keyword, 4 unanswerable) and
run_eval.py computing 4 Ragas metrics + 3 custom (hit_rate@k, citation_accuracy, refusal_accuracy).

Real results (not invented):
- Custom metrics, n=15 across all categories: hit_rate 1.0, citation_accuracy 1.0, refusal_accuracy 1.0.
- Ragas sample, n=4 (judge gpt-oss-120b): faithfulness 1.0, context_precision 0.83, context_recall 0.88.

Surprises / lessons:
- **Judge choice matters a lot.** qwen3.8-27b scored a clearly-faithful answer 0.0 because it didn't emit
  Ragas's structured verdict; gpt-oss models did it right. Always calibrate the judge on a known
  faithful/unfaithful pair before trusting it.
- **Free-tier token budgets are a real engineering constraint.** Groq gives 200k tokens/day PER MODEL;
  Ragas makes ~10 judge calls/question (context-precision is 1 call per context chunk), so a full 40-Q
  run blows the daily cap. Levers: --no-ragas (custom only), --ids subset, switch judge model, cache.
- **Gemini was a dead end here** — inference times out via REST and SDK, free and premium keys: a sandbox
  network egress block, not an account problem. Confirmed by testing the raw REST endpoint directly.
- Ragas 0.4.3 vs langchain v1 needed a small import shim (langchain-community dropped chat_models.vertexai).

_(add your own reflection: low context-recall vs low faithfulness, why the judge can be wrong, why unanswerable Qs)_

## Phase 6 — ACLs + permission-filtered retrieval

Built SQLModel users/groups (8 demo users seeded), build_filter(user) applied INSIDE the Qdrant query,
plus an independent is_allowed() post-check (defense in depth). 20-question leakage set.

Result: **leakage_rate = 0.0** over 20 questions. Demo: same question, intern retrieves only public
docs; CEO retrieves the restructuring plan. Permission-aware retrieval proven. 85 tests pass.

Lessons:
- **Pre-filter, never post-filter.** Post-filtering pulls forbidden chunks into the app (leak risk) and
  wastes top-k slots (quality loss). Filtering in the vector query means forbidden data is never a candidate.
- The leakage guarantee is testable WITHOUT the LLM - it's a property of retrieval - so it's cheap, fast,
  deterministic, and quota-free. Good for the CI gate (Phase 19).
- passlib is dead (breaks with bcrypt 5); used bcrypt directly.

_(add your own reflection: post-filter danger, top-k with forbidden chunks, Google Drive ACL sync)_

## Phase 7 — Hybrid search (BM25 + dense)

Recreated the collection with named dense + sparse (BM25) vectors; retrieval/hybrid.py queries both
(each permission-filtered) and fuses with Reciprocal Rank Fusion. Behind HYBRID_ENABLED.

Result (hit_rate@k over all 44 golden questions, quota-free):
- @12 and @3: dense == hybrid == 1.00 (dense already saturated on a 26-doc corpus).
- **@1 keyword: dense 0.75 -> hybrid 1.00**. Concrete win: "fix for ERR-6210?" - dense's #1 is the
  ERR-5002 postmortem (near-duplicate); hybrid's BM25 branch matches the exact code and returns the right doc.
- leakage_rate stays 0.00 with hybrid (filter applied on BOTH branches).

Lessons:
- **Embeddings blur rare exact tokens** (ERR-4021/5002/6210 cluster together); BM25's literal match
  disambiguates. This is the core reason to run hybrid.
- **RRF fuses by rank, not score** - sidesteps that cosine and BM25 scores aren't comparable.
- **Metrics can saturate.** hit_rate@12 showed nothing; only hit_rate@1 exposed the difference. Pick a
  k (and a corpus) where the metric has headroom, or you'll "prove" nothing.

_(add your own reflection: why embeddings miss exact codes, how RRF works, why hybrid may not help a category)_

## Phase 8 — Cross-encoder reranking

Added retrieval/rerank.py using bge-reranker-base via fastembed's ONNX cross-encoder (NO PyTorch - big
win on 8 GB RAM). Pipeline: hybrid retrieve wide (top_k) -> permission check -> rerank -> top_n. Behind
RERANK_ENABLED.

Measured (44 questions, CPU):
- hybrid @4 no-rerank: hit_rate 1.00, median 744ms.
- +rerank pool8->4: 1.00, 2021ms.  pool12->4: 1.00, 2499ms.  pool20->4: 0.975, 3506ms.

One-sentence verdict: on this saturated corpus reranking adds ~1.3-2.8s median latency for no recall gain,
and pool 20 even drops hit_rate - its value is precision/ordering, not recall.

Lessons:
- **Cross-encoders are O(N) per query** - only affordable on a small candidate set from a cheap first stage.
- **Rerank can't fix recall** (it only reorders what retrieval returned); it improves context precision.
- **Know when to skip it.** If first-stage metrics are already saturated, reranking is pure latency cost.
- fastembed ONNX avoided the torch install the spec implied.

_(add your own reflection: why not cross-encode the whole corpus, precision vs recall, when to skip rerank)_
