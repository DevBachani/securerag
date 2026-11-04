# FastAPI Backend — Practical Interview Q&A (SecureRAG)

The Phase 15 API layer explained for study/interviews: what we used and why, an
honest list of what we did **not** use, and a question bank. Code lives in
[src/securerag/api/](../src/securerag/api).

---

## Part 1 — Say it simply

**Elevator:**
> "I built a FastAPI backend for the agent: JWT login, a streaming chat endpoint over
> Server-Sent Events, a ticket-approval endpoint, an admin audit log, and a health
> check. Auth proves *who you are* with a token; *what you can do* is loaded from the
> database on every request, so permission changes take effect immediately."

**Mental model:** FastAPI = the front door. Each request shows a token (who), the server
re-checks permissions against the DB (what), runs the agent, streams the answer, and
records an audit row.

---

## Part 2 — What we used & why

| Tool | Why |
|---|---|
| **FastAPI** | Async, typed web framework with auto OpenAPI `/docs` |
| **Uvicorn** | ASGI server that runs the app |
| **Pydantic** (via FastAPI) | Validates request/response bodies ([schemas.py](../src/securerag/api/schemas.py)) |
| **PyJWT** | Create/verify the stateless login token |
| **bcrypt** | Verify the password hash at login |
| **`Depends` (DI)** | `get_current_user` / `require_admin` run per route |
| **`HTTPBearer`** | Extract `Bearer <token>` from the header |
| **sse-starlette** | Stream the answer over SSE (`EventSourceResponse`) |
| **slowapi** | Per-user rate limit on `/chat` |
| **CORSMiddleware** | Restrict browser access to the UI origin |
| **`run_in_threadpool`** | Run the sync agent without blocking the async loop |
| **SQLModel** | `audit_log` / `users` / `tickets` tables |
| **httpx `TestClient`** | API tests without a live server |

**Key decision:** the JWT carries only the user id; `get_current_user` loads **groups from
the DB each request** — immediate permission changes, no client tampering.

---

## Part 3 — Endpoints

| Route | Purpose | Auth |
|---|---|---|
| `POST /auth/login` | email+password → JWT | public |
| `POST /chat` | run agent, stream answer (SSE) + final event | user |
| `POST /chat/{id}/approve` | resume a paused ticket (owner only) | user |
| `GET /chat/{id}` | thread history (own threads only) | user |
| `GET /tickets` | your tickets | user |
| `GET /admin/audit` | audit rows | admin group |
| `POST /admin/reingest` | trigger corpus sync | admin group |
| `GET /health` | DB + Qdrant + LLM config | public |

---

## Part 4 — Question bank

**Q: Why load groups from the DB each request instead of trusting the token?**
The token is valid for its lifetime (60 min). If groups lived in the token, a revoked user
would keep access until expiry, and a tampered token could claim extra groups. Loading
groups fresh means permission changes are immediate; the token only needs the user id.

**Q: Why SSE instead of WebSockets?**
Chat streaming is one-directional (server → client). SSE is HTTP-native, auto-reconnects,
and is trivial to proxy/secure. WebSockets are bidirectional and heavier — overkill unless
the client must push messages mid-stream.

**Q: What belongs in an audit log (and what doesn't)?**
Yes: who, when, the question, route, retrieved/cited **doc ids**, refused flag,
latency/tokens, trace id. No: the raw answer or chunk text (confidential — it would make
the audit log a second leak path), secrets, full PII. Store references + status, not the
sensitive payload.

**Q: How does streaming actually work in your API?**
The agent runs to completion first (so a grounding refusal can't be streamed as if it were
an answer), then I stream the final text as SSE `token` events, followed by a `done` event
carrying citations and any pending ticket.

**Q: How do you keep the async server responsive while the agent is synchronous?**
I call the agent via `run_in_threadpool`, which offloads the blocking work to a thread so
the event loop stays free.

**Q: How do you enforce that a user only reads their own conversations?**
The checkpointer stores each thread's state, including `user_id`. `GET /chat/{id}` reads that
state and 403s if `user_id` doesn't match the caller — ownership comes from saved state, not
the client.

**Q: How is admin access scoped?**
A `require_admin` dependency checks the `admin` group. Note the admin can read the audit log
and trigger re-ingestion but is in **no document's ACL**, so admin endpoints never expose
confidential content — separating "manages the system" from "reads the data."

---

## Part 5 — What we did NOT use (be honest)

| Not used | Instead / why |
|---|---|
| **True LLM token streaming** (`astream`) | Chunked replay of the finished answer (avoids streaming text a grounding check may refuse) |
| **WebSockets** | SSE (one-way is enough) |
| **OAuth2 flow / refresh tokens / revocation list** | One short-lived JWT |
| **Async DB** (asyncpg) | Sync SQLite via `run_in_threadpool` |
| **Background queue** (Celery/RQ) for reingest | Inline sync call |
| **API versioning `/v1`, rich pagination, scopes** | Flat routes, a `limit`, single admin check |
| **HTTPS/TLS, secrets manager** | Deployment concerns (Phase 20) |
| **DB-session `Depends`** | `get_session()` context managers directly |

Framing:
> "I used FastAPI with JWT auth, dependency injection for per-route authorization, SSE for
> streaming, slowapi for rate limiting, and an audit log that stores metadata not content.
> I deliberately kept it demo-appropriate — no OAuth refresh flow, async DB, or task queue
> yet — and I know exactly where each of those would slot in for production."
