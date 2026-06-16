"""Server-side sessions. Cookie value is an opaque uuid → a row in `sessions`.

Server-side (not JWT) so revocation is a row delete and rolling expiry needs no
token rotation. One DB roundtrip per authenticated request, fine at this scale.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from ..db import db

SESSION_TTL = timedelta(days=30)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_session(user_id: str) -> str:
    sid = str(uuid.uuid4())
    now = _now()
    await db().execute(
        "INSERT INTO sessions (id, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (sid, user_id, (now + SESSION_TTL).isoformat(), now.isoformat()),
    )
    await db().commit()
    return sid


async def get_session_user_id(sid: str) -> str | None:
    """Return the session's user_id if still valid, else None. Bumps expiry on
    a hit (rolling TTL); lazily GCs the row on a miss."""
    cur = await db().execute("SELECT user_id, expires_at FROM sessions WHERE id = ?", (sid,))
    row = await cur.fetchone()
    if row is None:
        return None
    try:
        expires = datetime.fromisoformat(row["expires_at"])
    except ValueError:
        expires = _now()
    if expires <= _now():
        await db().execute("DELETE FROM sessions WHERE id = ?", (sid,))
        await db().commit()
        return None
    await db().execute(
        "UPDATE sessions SET expires_at = ? WHERE id = ?",
        ((_now() + SESSION_TTL).isoformat(), sid),
    )
    await db().commit()
    return row["user_id"]


async def revoke_session(sid: str) -> None:
    await db().execute("DELETE FROM sessions WHERE id = ?", (sid,))
    await db().commit()
