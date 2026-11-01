# Agent Layer Study Guide (LangChain + LangGraph)

A study reference for the SecureRAG agent (Phases 11–14), grounded in this repo's
actual code rather than generic documentation. See the rendered graph in
[graph.png](graph.png) / [graph.mmd](graph.mmd).

---

## 1. LangChain vs LangGraph — two different things

| | **LangChain** | **LangGraph** |
|---|---|---|
| Role here | The **model wrapper** layer | The **orchestration** layer |
| Used for | `ChatGroq` chat model, `.invoke()`, `.with_structured_output()`, message types (`HumanMessage`/`AIMessage`) | The stateful graph: nodes, edges, loops, checkpointer, interrupt/resume |
| File | [providers.py](../src/securerag/providers.py) (`get_langchain_llm`) | [graph.py](../src/securerag/agent/graph.py), [nodes.py](../src/securerag/agent/nodes.py), [state.py](../src/securerag/agent/state.py) |

**One-liner:** *LangChain gives a uniform interface to the LLM (invoke, structured
output, messages); LangGraph gives a stateful graph to orchestrate multi-step
reasoning with branches, loops, memory, and human-in-the-loop.*

**Why a graph, not a plain chain?** A chain is linear (A→B→C). The agent needs to
**branch** (route to knowledge/action/out-of-scope), **loop** (retrieve → grade →
rewrite → retrieve again), and **pause for a human** (ticket approval). A plain chain
can't express those cleanly; a graph can.

---

## 2. The State — the object that flows through everything

[state.py](../src/securerag/agent/state.py) defines `AgentState` (a `TypedDict`). Each
node receives the state and returns a **partial update** that LangGraph merges in.

Key fields:
- `messages` — chat history, with the **reducer** `add_messages`
  (`Annotated[list, add_messages]`). A reducer defines how updates combine: returning
  `{"messages": [AIMessage(...)]}` **appends** instead of replacing — that is what gives
  conversation memory.
- `question`, `standalone_question` — raw vs condensed question.
- `user_id`, `user_groups` — **the permission context, set by the caller, never by the
  LLM** (the security linchpin).
- `route`, `retrieved`, `rewrites`, `generations`, `grounded`, `injection_flagged`,
  `pending_ticket`, `approval_decision`, `ticket_id`, `refused`, `citations`, `answer`.

`total=False` lets a node return only the keys it changes.

---

## 3. The Nodes — each a function `(state) -> partial update`

All in [nodes.py](../src/securerag/agent/nodes.py):

| Node | What it does | LLM? |
|---|---|---|
| `condense` | Rewrites a follow-up into a standalone question using history; runs the injection detector | yes (if history) |
| `route` | Structured output → `knowledge` / `action` / `out_of_scope` | yes |
| `retrieve_node` | Calls the permission-filtered retriever (uses `search_query` if rewritten) | no (local) |
| `grade_context` | Keeps only chunks the LLM judges relevant; empty → rewrite/refuse | yes |
| `rewrite_query` | Expands the query (keywords/synonyms); bumps `rewrites` | yes |
| `generate` | Writes the cited answer; applies guardrails (stricter prompt, citation validation) | yes |
| `check_grounding` | Verifies claims are supported; else regenerate/refuse | yes |
| `refuse` / `decline` | Safe refusal / out-of-scope message | no |
| `draft_ticket_node` → `approval_node` → `create_ticket_node` / `cancelled_node` | Ticket action with the human pause | draft: yes |

---

## 4. The Graph — edges, branches, and loops

`build_graph()` in [graph.py](../src/securerag/agent/graph.py):

```
START → condense → route ─┬─(knowledge)→ retrieve → grade_context ─┬─(relevant)→ generate → check_grounding ─┬─(grounded)→ END
                          │                                        ├─(none,<2 rewrites)→ rewrite → retrieve   ├─(not grounded,<2 gens)→ generate
                          │                                        └─(none,exhausted)→ refuse → END           └─(exhausted)→ refuse → END
                          ├─(action)→ draft_ticket → approval ─(interrupt)─┬─(approve)→ create_ticket → END
                          │                                                └─(reject)→ cancelled → END
                          └─(out_of_scope)→ decline → END
```

- **Static edge:** `add_edge("A","B")` — always A→B.
- **Conditional edge:** `add_conditional_edges("route", fn, {...})` — `fn(state)` returns
  a key that selects the next node. The router functions `_after_grade`,
  `_after_grounding`, `_after_approval` are pure and unit-tested with no LLM
  ([test_agent.py](../tests/unit/test_agent.py)).
- **Loops:** `rewrite → retrieve` and `check_grounding → generate` are cycles,
  **bounded** by `max_rewrites` / `max_generations`. Unbounded loops would never
  terminate — always cap them.

---

## 5. LangChain mechanics used

`get_langchain_llm()` ([providers.py](../src/securerag/providers.py)) returns a `ChatGroq`:
- **`.invoke(prompt_or_messages)`** → returns a message; read `.content`.
- **`.with_structured_output(Model, method="json_schema")`** → forces a typed object.
  We use `method="json_schema"` because gpt-oss on Groq throws a tool-validation error
  with the default `function_calling` method.
- **Messages:** `HumanMessage` / `AIMessage`; `add_messages` appends them to history.

**Structured-output models** ([state.py](../src/securerag/agent/state.py),
[tools.py](../src/securerag/agent/tools.py)): `RouteDecision` (a `Literal` of 3 routes),
`ContextGrade` (`relevant_indices`), `GroundingCheck` (`grounded: bool`), `TicketDraft`.
Structured output = no brittle string parsing, no hallucinated/invalid values.

---

## 6. Memory & durability — the checkpointer

`get_compiled_graph()` compiles with `SqliteSaver` (a **checkpointer**). Each `invoke`
passes `config={"configurable": {"thread_id": ...}}`. The checkpointer **saves the full
state per thread_id to SQLite** after every step, giving:
- **Memory** — next turn on the same `thread_id` restores prior `messages`, so `condense`
  can resolve follow-ups.
- **Durability** — conversations survive a restart.
- **The basis for interrupts** (below).

---

## 7. Human-in-the-loop — `interrupt()` and `Command(resume=...)`

The ticket flow:
1. `approval_node` calls `interrupt({...})` → the graph **pauses** and saves state;
   `run_agent` returns `interrupted=True` with the `pending_ticket`.
2. The human decides; `resume_ticket(thread_id, approve=..., acting_user_id=...)` calls
   `graph.invoke(Command(resume=decision), config=...)`.
3. Inside `approval_node`, `interrupt()` **returns the resume payload** and the graph
   continues to `create_ticket` or `cancelled`.

The pause is **structural** (enforced by the graph + checkpointer, outside the LLM), so
a prompt injection can't talk the agent past it. `create_ticket`
([tools.py](../src/securerag/agent/tools.py)) is idempotent on `thread_id` so a
double-resume creates exactly one ticket.

---

## 8. Security woven into the agent

- **Identity is in state, set from the session** (`run_agent` sets `user_id`/`user_groups`
  from the `Principal`), never from the LLM → injection can't escalate privileges.
- **Permission filter in `retrieve_node`** → forbidden chunks never enter the model's
  context (the real guarantee).
- **Guardrails** ([guardrails.py](../src/securerag/agent/guardrails.py)):
  `detect_injection` (flag → stricter prompt), untrusted-context labelling in
  [prompts.py](../src/securerag/agent/prompts.py), and `validate_citations` (an answer may
  only cite chunks retrieved for this user).

---

## 9. End-to-end trace (a knowledge follow-up)

`run_agent("and casual leaves?", principal, thread_id)`:
`condense` (restores history, rewrites to "how many casual leaves per year?", checks
injection) → `route` (→ knowledge) → `retrieve` (hybrid + permission filter + rerank) →
`grade_context` (keep relevant) → `generate` (cited answer + guardrails) →
`check_grounding` (supported?) → END. Returns
`{answer, citations, retrieved, refused, route, ...}`.

---

## 10. File map

| File | Contents |
|---|---|
| [state.py](../src/securerag/agent/state.py) | `AgentState`, `RouteDecision`, `ContextGrade`, `GroundingCheck` |
| [nodes.py](../src/securerag/agent/nodes.py) | all node functions |
| [graph.py](../src/securerag/agent/graph.py) | `build_graph`, conditional routers, `get_compiled_graph`, `run_agent`, `resume_ticket` |
| [prompts.py](../src/securerag/agent/prompts.py) | all prompts (condense/route/grade/rewrite/grounding/answer) |
| [tools.py](../src/securerag/agent/tools.py) | `TicketDraft`, `draft_ticket`, `create_ticket` (idempotent) |
| [guardrails.py](../src/securerag/agent/guardrails.py) | `detect_injection`, `validate_citations`, untrusted-context note |
| [providers.py](../src/securerag/providers.py) | `get_langchain_llm` (ChatGroq) |

---

## 11. Interview cheat-sheet

- **LangChain vs LangGraph:** model wrapper vs stateful orchestration.
- **Why a graph:** branches, retry loops, human pause — a chain can't.
- **State + reducers:** partial updates merge; `add_messages` appends for memory.
- **Structured output:** typed, validated routing/grading (no string parsing).
- **Checkpointer:** per-thread state in SQLite → memory, durability, interrupts.
- **Human-in-the-loop:** `interrupt()`/`Command(resume=...)`; the gate is outside the LLM.
- **Self-correcting RAG:** grade → rewrite (capped) → retrieve; grounding → regenerate → refuse.
- **Security:** identity in state from the session; permission filter before the LLM;
  guardrails as defense-in-depth. The filter — not the prompt — is the real guarantee.
