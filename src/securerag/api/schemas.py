"""Pydantic request/response models for the API."""

from __future__ import annotations

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """Login credentials."""

    email: str
    password: str


class TokenResponse(BaseModel):
    """A signed JWT and its type."""

    access_token: str
    token_type: str = "bearer"


class ChatRequest(BaseModel):
    """A chat turn; thread_id continues an existing conversation."""

    message: str
    thread_id: str | None = None


class ApproveRequest(BaseModel):
    """A human approval decision for a pending ticket."""

    approve: bool
    edited_title: str | None = None
