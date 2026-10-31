"""Database engine, password hashing, and loading a user's permission context.

`load_principal` is the trust boundary: it turns a user id into the exact groups
that user belongs to, read from the database, which the retrieval filter then uses.
The LLM never influences this.
"""

from __future__ import annotations

from functools import lru_cache

import bcrypt
from sqlmodel import Session, SQLModel, create_engine, select

from ..config import get_settings
from ..retrieval.permissions import Principal
from .models import Group, User, UserGroup


@lru_cache
def get_engine():
    """Return a cached SQLModel engine for the configured database."""
    url = get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, echo=False, connect_args=connect_args)


def init_db() -> None:
    """Create all tables if they do not exist."""
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Session:
    """Open a new database session (caller manages its lifetime)."""
    return Session(get_engine())


def hash_password(password: str) -> str:
    """Hash a password with bcrypt and return it as a utf-8 string."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def load_principal(user_id: str) -> Principal:
    """Build a Principal (id + group names) for a user from the database."""
    with get_session() as session:
        user = session.get(User, user_id)
        if user is None:
            raise ValueError(f"Unknown user_id: {user_id!r}. Did you run scripts/seed_users.py?")
        group_ids = session.exec(
            select(UserGroup.group_id).where(UserGroup.user_id == user_id)
        ).all()
        if not group_ids:
            return Principal(id=user.id, groups=[])
        names = session.exec(select(Group.name).where(Group.id.in_(group_ids))).all()
        return Principal(id=user.id, groups=list(names))
