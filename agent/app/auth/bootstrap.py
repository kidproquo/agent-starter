"""Ensure an admin exists on startup.

Idempotent: creates the env-configured admin if missing, or reconciles its role
+ password if they drifted. Guarantees a login path after a fresh deploy.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from ..config import settings
from ..db import db
from .passwords import hash_password, verify_password

log = logging.getLogger(__name__)


async def ensure_bootstrap_admin() -> None:
    username = settings.admin_username
    password = settings.admin_password
    conn = db()

    cur = await conn.execute("SELECT id, username FROM users WHERE role = 'admin' LIMIT 1")
    existing_admin = await cur.fetchone()

    if not username or not password:
        if existing_admin is None:
            log.warning(
                "No admin user and VS_ADMIN_USERNAME/VS_ADMIN_PASSWORD unset — "
                "there is no way to log in. Set them and restart."
            )
        return

    cur = await conn.execute(
        "SELECT id, role, password_hash FROM users WHERE username = ?", (username,)
    )
    target = await cur.fetchone()
    now = datetime.now(timezone.utc).isoformat()

    if target is None:
        log.info("bootstrap: creating admin user '%s'", username)
        await conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at) "
            "VALUES (?, ?, ?, 'admin', ?)",
            (str(uuid.uuid4()), username, hash_password(password), now),
        )
        await conn.commit()
        return

    new_hash = target["password_hash"]
    changed = target["role"] != "admin"
    if not verify_password(password, target["password_hash"]):
        new_hash = hash_password(password)
        changed = True
    if changed:
        log.info("bootstrap: reconciling admin '%s'", username)
        await conn.execute(
            "UPDATE users SET role = 'admin', password_hash = ? WHERE id = ?",
            (new_hash, target["id"]),
        )
        await conn.commit()
