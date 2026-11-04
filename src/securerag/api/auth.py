"""JWT login and the per-request authentication dependencies.

get_current_user decodes the token but then loads the user's groups FROM THE DB on
every request, rather than trusting whatever was in the token. So a permission change
takes effect immediately and a stale/forged group claim in a token is ignored.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import select

from ..config import get_settings
from ..db.models import User
from ..db.session import get_session, verify_password
from ..retrieval.permissions import Principal
from .schemas import LoginRequest, TokenResponse

router = APIRouter(tags=["auth"])
_bearer = HTTPBearer(auto_error=False)
_ALGORITHM = "HS256"


def create_access_token(user_id: str) -> str:
    """Create a signed JWT carrying the user id and an expiry."""
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": user_id, "exp": expire}, settings.jwt_secret, algorithm=_ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    """Resolve the bearer token to a Principal, loading groups from the DB each call."""
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = jwt.decode(
            credentials.credentials, get_settings().jwt_secret, algorithms=[_ALGORITHM]
        )
        user_id = payload["sub"]
    except (jwt.PyJWTError, KeyError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from exc

    from ..db.session import load_principal

    try:
        return load_principal(user_id)  # groups read fresh from the DB
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user") from exc


def require_admin(user: Principal = Depends(get_current_user)) -> Principal:
    """Allow only members of the 'admin' group (admins manage; they don't read docs)."""
    if "admin" not in user.groups:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    """Verify email + password and return a JWT."""
    with get_session() as session:
        user = session.exec(select(User).where(User.email == body.email)).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return TokenResponse(access_token=create_access_token(user.id))
