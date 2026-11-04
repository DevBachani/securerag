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

## Phase 9 — Incremental sync + document versions

Added ingest_state (content_hash + meta_hash) and ingestion/sync.py: only new/changed files are
re-embedded, deleted files have their chunks removed, and an ACL/version change updates the chunk
payload in place (no re-embed). Added travel_policy_v1 (superseded); retrieval filters is_current=true.

Verified: full rebuild 27 files/127 chunks; re-running sync = all unchanged (0.8s); the stale v1 policy
is never retrieved; an ACL change (temp manifest) updates the payload and reverts cleanly. leakage 0.0.
99 tests.

Lessons:
- **Hash content, not mtime.** mtime changes on touch/clone (false churn) and can miss real edits.
- **The vector-store payload is the enforcement point** - an un-synced ACL tightening keeps serving
  revoked content. Sync must update the payload on an ACL change even when content is unchanged.
- Two hashes separate concerns: content_hash -> re-embed; meta_hash -> cheap payload update.

_(add your own reflection: hash vs mtime, security risk of unsynced ACLs, Google Drive change feed)_

## Phase 10 — PII redaction at ingestion

Added ingestion/pii.py (regex recognizers: EMAIL, +91 PHONE, AADHAAR, PAN) run on each document's text
BEFORE chunking/embedding; chunks carry pii_redacted. Added the disciplinary-log trap with fake PII.
Policy: keep names (needed for HR, protected by ACL), redact contact/ID numbers everywhere.

Verified: 0 planted PII tokens across all 132 chunks; budget "36 crore" intact; 16 chunks flagged redacted.
119 tests.

Decisions / lessons:
- **Regex over Presidio (rule #10):** since we keep names and only redact regex-detectable IDs/contacts,
  heavy spaCy NER adds nothing - and it's a big install on 8 GB. Documented tradeoff.
- **Redact at ingestion, not answer time:** what's never stored can't leak (to the vector DB, the external
  LLM, logs, or caches). Answer-time redaction trusts a scrub step on every path, every request.
- **False positives destroy facts:** over-redaction (e.g. a budget matched as <AADHAAR>) silently makes a
  question unanswerable - patterns must be precise; tests assert budgets/dates/codes survive.
- Side effect: org emails (ethics@/secops@) are redacted too - acceptable; we just don't embed any email.

_(add your own reflection: redact at ingestion vs answer time, false positives, ACLs+redaction defense in depth)_

## Phase 11 — LangGraph agent: state, router and memory

Replaced the straight answer() pipeline with a LangGraph agent: condense -> route (structured output)
-> retrieve -> generate, with action (stub) and decline branches. SQLite checkpointer keyed by thread_id
gives conversation memory. Rendered docs/graph.png + graph.mmd.

Verified live: follow-up "and casual leaves?" was condensed into a standalone question and answered "7";
greetings route to decline; "raise a ticket" routes to the action stub; an intern asking salary bands is
refused inside the agent (permission context from state, not the LLM). 121 tests (+2 opt-in agent tests).

Lessons:
- **The checkpointer is memory + durability + the basis for interrupts** (Phase 13). It stores the whole
  state per thread_id.
- **Structured output beats text parsing for routing** - a typed Literal can't be mis-parsed or hallucinated.
- **Keep permission context in state, set from the session.** If the LLM could set it, injection could
  escalate access. Trusted code enforces authz; the model never touches it.
- LLM-using tests are opt-in (RUN_LLM_TESTS=1) to protect the free-tier token budget.

_(add your own reflection: what the checkpointer stores, structured output vs parsing, why the LLM must not set identity)_

## Phase 12 — Self-correcting retrieval

Added grade_context (keep only relevant chunks) -> rewrite_query (max 2 retries) -> retrieve loop, and
check_grounding after generate (regenerate once, then refuse). A dedicated refuse node uses a message that
never reveals a restricted document exists. All behind self_correction_enabled (A/B flag).

Measured: self-correction adds ~4s/question (2 extra LLM calls: grade + grounding). On this corpus it rarely
changes outcomes - retrieval is already strong, so grade seldom rejects and grounding seldom fails.
123 tests (+2 opt-in).

Lessons:
- **gpt-oss + Groq function-calling structured output is flaky** ("tool not in request.tools"); method=
  "json_schema" is reliable. Switched route/grade/grounding to it.
- **Cap the loops.** Unbounded rewrite/regenerate never terminates and burns tokens; 2 rewrites + 1
  regenerate bound cost and force a clean refusal.
- **Refusals must not leak existence.** "I couldn't find this in documents you have access to" is
  indistinguishable from "doesn't exist" - no probing for restricted docs via error messages.
- **Decide features by measurement.** Self-correction earns its latency only on noisy/large corpora; here
  it's mostly overhead - which is why it's a flag.

_(add your own reflection: why cap retries, why refusal must not reveal restricted docs, is the cost worth it)_

## Phase 13 — Ticket tool with human-in-the-loop approval

Added the tickets table + agent/tools.py (draft_ticket via LLM, create_ticket to DB). Graph: action ->
draft_ticket -> approval (LangGraph interrupt) -> approve: create_ticket / reject: cancelled. resume_ticket()
drives it with Command(resume=...). Verified live (opt-in): approve creates a ticket, reject creates none.

Rules enforced + tested (DB-only unit tests, no LLM): approve -> 1 ticket, reject -> 0, double-resume -> 1
(idempotent on thread_id), non-owner cannot approve. 128 tests (+4 opt-in).

Lessons:
- **The approval gate lives outside the LLM** - interrupt() + checkpointer make the pause structural, so a
  prompt injection can't talk the agent into taking the action.
- **Idempotency is mandatory for side-effecting actions.** Deterministic key (thread_id) + check-before-
  insert makes retries/double-resume safe.
- **Act as the authenticated user, never on someone's behalf** - the create node rejects a non-owner approver.

_(add your own reflection: approval outside the LLM, idempotency, which actions need human approval)_

## Phase 14 — Guardrails & prompt-injection defense

Added the poisoned newsletter (hidden "reveal salary bands" instruction) + a 15-attack injection set.
agent/guardrails.py: rule-based injection detector (flags -> logs + stricter prompt), untrusted-context
labelling in the answer prompt, and output validation (cite only chunks retrieved for this user).

Result: attack_success_rate (data leakage) = **0.0** over 15 attacks. The intern's injection cannot leak
salary bands (verified via generation too). 141 tests (+5 opt-in).

Lessons:
- **A prompt can't stop injection** - system rules and attacker text are the same tokens; defenses lower
  the rate but never guarantee 0.
- **The permission filter is the real guarantee.** Forbidden chunks never reach the LLM, so even a fully
  successful injection has nothing to leak. Security is at retrieval (data minimization), not model will.
- **Indirect injection is the bigger RAG risk** - instructions hidden in retrieved docs, innocent user,
  bypasses input filters. The poisoned newsletter is inert because the salary bands aren't retrievable.
- Honest residual: pure instruction-following (e.g. "print your system prompt") may partially comply; that
  is not data leakage and is acceptable - which is why the structural guarantee matters most.

_(add your own reflection: why a prompt can't stop injection, why the filter is the real guarantee, indirect injection)_

## Phase 15 — FastAPI backend with auth and audit log

Built the API: JWT login, SSE streaming chat, ticket approval, own-thread history, /tickets,
admin audit + reingest, /health, per-user rate limiting (slowapi), CORS to the UI, and an audit row
per chat request. 147 tests; server boots and /health is green.

Lessons:
- **Authenticate with the token, authorize from the DB.** The JWT carries only the user id; groups are
  loaded fresh each request, so a permission change is immediate and the client can't tamper with groups.
- **SSE fits one-way streaming** better than WebSockets here (HTTP-native, simple, auto-reconnect).
- **The audit log is metadata, not content** - doc ids + status + latency, never the raw answer, so the
  audit trail doesn't become a second leak path.
- Ran the sync agent via run_in_threadpool so it doesn't block the async event loop.
- Honest gap: chat streams a chunked replay of the finished answer, not live LLM tokens (astream later).

_(add your own reflection: groups-from-DB each request, SSE vs WebSockets, what belongs in an audit log)_

## Phase 16 — Observability with Langfuse

observability.py attaches a Langfuse LangChain callback handler to agent runs when keys are set, and is a
no-op otherwise. User ids are pseudonymised (hashed) before telemetry; trace_content=False redacts
inputs/outputs; a trace_id is generated per request and stored in audit_log so audit and trace link up.
scripts/latency_report.py reads the audit log (works without Langfuse). 150 tests.

What tracing revealed (the point of the phase): agent latency is ~28s median / ~30s p95 per question -
self-correction adds grade+grounding (~5 Groq calls) on a slow 120B model. That's a real finding to act on
before deploy (disable self-correction, smaller model, or cache).

Lessons:
- **Instrument for privacy:** pseudonymise user ids, allow content redaction - telemetry shouldn't leak.
- **Trace linkage:** a shared trace_id across the audit log and the trace ties "what happened" to "how".
- **Graceful degradation:** observability must never break the request; wrap it and no-op if unavailable.
- **Measure to find waste:** the latency report surfaced the self-correction cost immediately.

_(add your own reflection: traces vs spans, why pseudonymise, what to alert on)_
