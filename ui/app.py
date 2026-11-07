"""SecureRAG Streamlit UI.

A thin demo client over the FastAPI backend: pick a demo user, chat with cited and
sensitivity-badged answers, approve tickets, compare what two users can see side by
side, and (as admin) view the audit log and trigger re-ingestion.

Run:  uv run streamlit run ui/app.py   (API must be running on API_BASE_URL)
"""

from __future__ import annotations

import uuid

import api_client as api
import streamlit as st

from securerag.config import get_settings

BASE = get_settings().api_base_url

# (email, label) for the login dropdown — demo users seeded by scripts/seed_users.py.
DEMO_USERS = [
    ("vikram.shah@acme.example", "Vikram Shah — CEO (sees everything)"),
    ("priya.mehta@acme.example", "Priya Mehta — HR Manager"),
    ("meera.joshi@acme.example", "Meera Joshi — HR Executive"),
    ("anita.desai@acme.example", "Anita Desai — Finance Analyst"),
    ("arjun.patel@acme.example", "Arjun Patel — Engineering Manager"),
    ("rahul.verma@acme.example", "Rahul Verma — Software Engineer"),
    ("sneha.rao@acme.example", "Sneha Rao — Intern (public only)"),
    ("admin@acme.example", "Admin — Platform Admin"),
]
_SENSITIVITY_BADGE = {
    "public": "🟢 public",
    "internal": "🔵 internal",
    "confidential": "🟠 confidential",
    "restricted": "🔴 restricted",
}


def _badge(sensitivity: str) -> str:
    return _SENSITIVITY_BADGE.get(sensitivity, sensitivity or "")


def _render_citations(citations: list[dict]) -> None:
    if not citations:
        return
    st.caption("Sources")
    for c in citations:
        where = c.get("section") or (f"Page {c['page']}" if c.get("page") else "")
        st.markdown(
            f"- **[{c['n']}] {c['title']}**{f' — {where}' if where else ''} "
            f"&nbsp; {_badge(c.get('sensitivity', ''))} &nbsp; `{c['doc_id']}`"
        )


def _ask(token: str, message: str, thread_id: str | None) -> dict:
    """Stream an answer into the page; return the final 'done' metadata."""
    placeholder = st.empty()
    text = ""
    final: dict = {}
    for event, data in api.chat_stream(BASE, token, message, thread_id):
        if event == "token":
            text += data + " "
            placeholder.markdown(text)
        elif event == "done":
            final = api.parse_done(data)
    if not text.strip() and final.get("answer"):
        placeholder.markdown(final["answer"])
    return final


# --------------------------------------------------------------------------- #
# Login
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="SecureRAG", page_icon="🔒", layout="wide")
st.title("🔒 SecureRAG — permission-aware knowledge agent")

if "token" not in st.session_state:
    st.subheader("Sign in as a demo user")
    email = st.selectbox("User", DEMO_USERS, format_func=lambda u: u[1])[0]
    password = st.text_input("Password", value="demo1234", type="password")
    if st.button("Sign in"):
        token = api.login(BASE, email, password)
        if token:
            st.session_state.token = token
            st.session_state.email = email
            st.session_state.is_admin = email.startswith("admin@")
            st.session_state.thread_id = uuid.uuid4().hex
            st.rerun()
        else:
            st.error("Login failed.")
    st.stop()

token = st.session_state.token
st.sidebar.write(f"Signed in as **{st.session_state.email}**")
if st.sidebar.button("Sign out"):
    st.session_state.clear()
    st.rerun()

tabs = ["Chat", "Compare access"] + (["Admin"] if st.session_state.get("is_admin") else [])
chat_tab, compare_tab, *admin_tab = st.tabs(tabs)

# --------------------------------------------------------------------------- #
# Chat
# --------------------------------------------------------------------------- #
with chat_tab:
    st.subheader("Ask a question (or request a ticket)")
    question = st.text_input("Your message", key="chat_msg")
    if st.button("Send", key="chat_send") and question:
        result = _ask(token, question, st.session_state.thread_id)
        if result.get("refused"):
            st.warning("The agent refused — no permitted document supports an answer.")
        _render_citations(result.get("citations") or [])
        if result.get("interrupted") and result.get("pending_ticket"):
            st.session_state.pending = result["pending_ticket"]
            st.session_state.pending_thread = result["thread_id"]

    pending = st.session_state.get("pending")
    if pending:
        st.divider()
        st.subheader("🎫 Ticket awaiting your approval")
        title = st.text_input("Title", value=pending["title"], key="tk_title")
        st.write(f"**Department:** {pending['department']}  |  **Priority:** {pending['priority']}")
        st.write(pending["description"])
        col_a, col_r = st.columns(2)
        if col_a.button("✅ Approve"):
            edited = title if title != pending["title"] else None
            out = api.approve(BASE, token, st.session_state.pending_thread, True, edited)
            st.success(out.get("answer", "Created."))
            st.session_state.pop("pending", None)
        if col_r.button("❌ Reject"):
            out = api.approve(BASE, token, st.session_state.pending_thread, False, None)
            st.info(out.get("answer", "Cancelled."))
            st.session_state.pop("pending", None)

# --------------------------------------------------------------------------- #
# Compare access — the headline demo
# --------------------------------------------------------------------------- #
with compare_tab:
    st.subheader("Same question, two users — see permissions in action")
    q = st.text_input("Question to compare", value="What are the salary bands for each level?")
    c1, c2 = st.columns(2)
    left = c1.selectbox("User A", DEMO_USERS, index=0, format_func=lambda u: u[1], key="cmpA")[0]
    right = c2.selectbox("User B", DEMO_USERS, index=6, format_func=lambda u: u[1], key="cmpB")[0]
    if st.button("Compare") and q:
        for col, email in ((c1, left), (c2, right)):
            with col:
                tok = api.login(BASE, email, "demo1234")
                if not tok:
                    st.error("login failed")
                    continue
                res = _ask(tok, q, uuid.uuid4().hex)
                if res.get("refused"):
                    st.warning("Refused (no permitted source).")
                _render_citations(res.get("citations") or [])

# --------------------------------------------------------------------------- #
# Admin
# --------------------------------------------------------------------------- #
if admin_tab:
    with admin_tab[0]:
        st.subheader("Admin")
        if st.button("Trigger re-ingest"):
            st.json(api.reingest(BASE, token))
        st.caption("Recent audit log")
        rows = api.get_audit(BASE, token, limit=50)
        st.dataframe(
            [
                {
                    "user": r["user_id"],
                    "question": r["question"][:60],
                    "route": r["route"],
                    "refused": r["refused"],
                    "latency_ms": r["latency_ms"],
                }
                for r in rows
            ],
            use_container_width=True,
        )
