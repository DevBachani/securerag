"""FastAPI application factory: wires auth, chat, tickets, admin, CORS and health.

Run with:  uv run uvicorn securerag.api.main:app --reload
Docs at:   http://localhost:8000/docs
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlmodel import select

from ..config import get_settings
from ..db.models import User
from ..db.session import get_session, init_db
from ..ingestion.pipeline import get_qdrant_client
from . import auth, routes_admin, routes_chat, routes_tickets
from .limiter import limiter


def create_app() -> FastAPI:
    """Build the FastAPI app (tables ensured, routers and middleware attached)."""
    settings = get_settings()
    init_db()

    app = FastAPI(title="SecureRAG API", version="1.0.0")
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.ui_origin],  # only the UI origin
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router)
    app.include_router(routes_chat.router)
    app.include_router(routes_tickets.router)
    app.include_router(routes_admin.router)

    @app.get("/health", tags=["health"])
    def health() -> dict:
        db_ok = False
        qdrant_ok = False
        try:
            with get_session() as session:
                session.exec(select(User).limit(1)).first()
            db_ok = True
        except Exception:
            pass
        try:
            get_qdrant_client().get_collections()
            qdrant_ok = True
        except Exception:
            pass
        return {
            "status": "ok" if (db_ok and qdrant_ok) else "degraded",
            "db": db_ok,
            "qdrant": qdrant_ok,
            "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model,
        }

    return app


app = create_app()
