"""FastAPI auth dependencies: resolve the current user from a session cookie.

Two roles, totally ordered: user < admin. `require_role("admin")` guards
admin-only endpoints; `get_current_user` is the baseline gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status

from ..db import db
from .sessions import get_session_user_id

SESSION_COOKIE = "vs_session"
ROLE_ORDER = {"user": 0, "admin": 1}


@dataclass(frozen=True)
class UserContext:
    id: str
    username: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def role_at_least(self, min_role: str) -> bool:
        return ROLE_ORDER.get(self.role, -1) >= ROLE_ORDER.get(min_role, 99)


async def get_current_user(
    vs_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> UserContext:
    if not vs_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not signed in")
    user_id = await get_session_user_id(vs_session)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "session expired")
    cur = await db().execute("SELECT id, username, role FROM users WHERE id = ?", (user_id,))
    row = await cur.fetchone()
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user no longer exists")
    return UserContext(id=row["id"], username=row["username"], role=row["role"])


def require_role(min_role: str):
    if min_role not in ROLE_ORDER:
        raise ValueError(f"unknown role: {min_role}")

    async def _guard(user: UserContext = Depends(get_current_user)) -> UserContext:
        if not user.role_at_least(min_role):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"requires role >= {min_role}; you have {user.role}",
            )
        return user

    return _guard
