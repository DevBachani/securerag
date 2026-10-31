"""SQLModel tables for identity: users, groups, and the membership link.

Only the tables Phase 6 needs exist here; tickets and audit_log arrive in later
phases. Group membership is the sole source of a user's permissions -- the agent
never derives access from anything the user types.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class UserGroup(SQLModel, table=True):
    """Link table: which users belong to which groups (many-to-many)."""

    __tablename__ = "user_groups"

    user_id: str = Field(foreign_key="users.id", primary_key=True)
    group_id: int = Field(foreign_key="groups.id", primary_key=True)


class Group(SQLModel, table=True):
    """A permission group, e.g. 'hr', 'engineering', 'all'."""

    __tablename__ = "groups"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)


class User(SQLModel, table=True):
    """An employee who can ask questions; access comes from group membership."""

    __tablename__ = "users"

    id: str = Field(primary_key=True)
    name: str
    email: str = Field(unique=True)
    role: str
    password_hash: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
