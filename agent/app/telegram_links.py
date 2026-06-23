"""Telegram chat <-> account binding (the /link flow) + lookups.

Light (only `db`) so both the link tool and the bot loop can import it without
pulling in the agent — keeps the import graph acyclic. A chat binds to a user.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from .config import settings
from .db import db

# Unambiguous code alphabet (no 0/O/1/I/L) — codes are read aloud / retyped.
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def issue_link_code(user_id: str) -> dict:
    """Create a one-time code the user sends to the bot as '/link <code>'."""
    code = "".join(secrets.choice(_ALPHABET) for _ in range(6))
    expires = _now() + timedelta(minutes=settings.telegram_link_code_ttl_min)
    conn = db()
    await conn.execute("DELETE FROM telegram_link_codes WHERE user_id = ?", (user_id,))
    await conn.execute(
        "INSERT INTO telegram_link_codes (code, user_id, expires_at) VALUES (?, ?, ?)",
        (code, user_id, expires.isoformat()),
    )
    await conn.commit()
    return {"code": code, "expires_min": settings.telegram_link_code_ttl_min}


async def redeem_code(code: str, chat_id: str, title: str | None) -> str | None:
    """Bind `chat_id` to the code's user. Returns user_id, or None if unknown/expired."""
    code = (code or "").strip().upper()
    if not code:
        return None
    conn = db()
    cur = await conn.execute("SELECT user_id, expires_at FROM telegram_link_codes WHERE code = ?", (code,))
    row = await cur.fetchone()
    if row is None or row["expires_at"] < _now().isoformat():
        return None
    user_id = row["user_id"]
    await conn.execute(
        "INSERT INTO telegram_chats (chat_id, user_id, title, linked_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET user_id = excluded.user_id, title = excluded.title",
        (str(chat_id), user_id, title, _now().isoformat()),
    )
    await conn.execute("DELETE FROM telegram_link_codes WHERE code = ?", (code,))
    await conn.commit()
    return user_id


async def user_for_chat(chat_id: str) -> dict | None:
    """The login bound to a chat (id/username/role/is_admin), or None if unlinked."""
    cur = await db().execute(
        "SELECT u.id, u.username, u.role FROM telegram_chats tc "
        "JOIN users u ON u.id = tc.user_id WHERE tc.chat_id = ?",
        (str(chat_id),),
    )
    r = await cur.fetchone()
    if r is None:
        return None
    return {"id": r["id"], "username": r["username"], "role": r["role"], "is_admin": r["role"] == "admin"}


async def unlink_chat(chat_id: str) -> bool:
    conn = db()
    cur = await conn.execute("SELECT 1 FROM telegram_chats WHERE chat_id = ?", (str(chat_id),))
    if await cur.fetchone() is None:
        return False
    await conn.execute("DELETE FROM telegram_chats WHERE chat_id = ?", (str(chat_id),))
    await conn.commit()
    return True
