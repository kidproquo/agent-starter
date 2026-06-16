"""Auth HTTP routes: login / logout / me / me/usage.

User management (create/list/delete/...) is done via admin-gated agent tools
(see app/tools/users.py), not HTTP, so there are no user-CRUD routes here.
"""
from __future__ import annotations

import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from ..config import settings
from ..db import db
from .deps import SESSION_COOKIE, UserContext, get_current_user
from .passwords import verify_password
from .sessions import create_session, revoke_session
from .usage import usage_all, usage_for_user

router = APIRouter(prefix="/auth", tags=["auth"])


# --- tiny in-process login throttle (per username + per IP) ---
_failures: dict[str, list[float]] = defaultdict(list)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _locked(key: str) -> bool:
    window = settings.login_window_seconds
    now = time.monotonic()
    recent = [t for t in _failures[key] if now - t < window]
    _failures[key] = recent
    return len(recent) >= settings.login_max_failures


def _record_failure(key: str) -> None:
    _failures[key].append(time.monotonic())


def _clear(key: str) -> None:
    _failures.pop(key, None)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    id: str
    username: str
    role: str


class UsageKinds(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


class UsageOut(UsageKinds):
    turns: int = 0
    models: dict[str, UsageKinds] = {}
    # Present only for admins: aggregate across all users.
    all_users: Optional["UsageOut"] = None


UsageOut.model_rebuild()


@router.post("/login", response_model=UserOut)
async def login(body: LoginRequest, request: Request, response: Response) -> UserOut:
    user_key = f"user:{body.username.strip().lower()}"
    ip_key = f"ip:{_client_ip(request)}"
    if _locked(user_key) or _locked(ip_key):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "too many failed login attempts; try again later",
        )

    cur = await db().execute(
        "SELECT id, username, role, password_hash FROM users WHERE username = ?",
        (body.username,),
    )
    row = await cur.fetchone()
    if row is None or not verify_password(body.password, row["password_hash"]):
        # Spend a hash even when the user is unknown to flatten timing.
        if row is None:
            verify_password(body.password, "$2b$12$" + "x" * 53)
        _record_failure(user_key)
        _record_failure(ip_key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")

    _clear(user_key)
    sid = await create_session(row["id"])
    await db().execute(
        "UPDATE users SET last_login_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), row["id"]),
    )
    await db().commit()

    response.set_cookie(
        key=SESSION_COOKIE,
        value=sid,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=30 * 24 * 3600,
        path="/",
    )
    return UserOut(id=row["id"], username=row["username"], role=row["role"])


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    vs_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> None:
    if vs_session:
        await revoke_session(vs_session)
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=UserOut)
async def me(user: UserContext = Depends(get_current_user)) -> UserOut:
    return UserOut(id=user.id, username=user.username, role=user.role)


@router.get("/me/usage", response_model=UsageOut)
async def me_usage(user: UserContext = Depends(get_current_user)) -> UsageOut:
    mine = await usage_for_user(user.username)
    out = UsageOut(**mine)
    if user.is_admin:
        out.all_users = UsageOut(**(await usage_all()))
    return out
