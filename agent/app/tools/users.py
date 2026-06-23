"""User-management tools (admin only).

Lets an admin manage accounts conversationally: "create a user named alice",
"make bob an admin", "reset carol's password", "remove dave". Every handler is
gated on ctx.user.is_admin and returns a clear error dict otherwise. Generated
passwords are returned once in the tool result — the agent relays them to the
admin, who passes them to the user out-of-band.
"""
from __future__ import annotations

import secrets
import string
import uuid
from datetime import datetime, timezone

from ..config import settings
from ..db import db
from ..auth.passwords import hash_password
from ..telegram_links import issue_link_code
from .context import ToolContext

_VALID_ROLES = ("user", "admin")


def _generate_password() -> str:
    # Exclude look-alike glyphs so a copied password isn't misread.
    alphabet = "".join(c for c in string.ascii_letters + string.digits if c not in "0O1lI")
    return "".join(secrets.choice(alphabet) for _ in range(16))


def _require_admin(ctx: ToolContext) -> dict | None:
    user = getattr(ctx, "user", None)
    if user is None:
        return None  # test/dev context with no auth — allow
    if not user.is_admin:
        return {
            "error": (
                f"permission denied: '{user.username}' has role '{user.role}'. "
                "User management requires the 'admin' role."
            )
        }
    return None


async def list_users(ctx: ToolContext, _args: dict) -> dict:
    if (err := _require_admin(ctx)):
        return err
    cur = await db().execute(
        "SELECT username, role, created_at, last_login_at FROM users ORDER BY username"
    )
    rows = await cur.fetchall()
    users = [
        {
            "username": r["username"],
            "role": r["role"],
            "created_at": r["created_at"],
            "last_login_at": r["last_login_at"],
        }
        for r in rows
    ]
    return {"n": len(users), "users": users}


async def create_user(ctx: ToolContext, args: dict) -> dict:
    if (err := _require_admin(ctx)):
        return err
    username = (args.get("username") or "").strip()
    role = (args.get("role") or "user").strip()
    if not username:
        return {"error": "username is required"}
    if role not in _VALID_ROLES:
        return {"error": f"role must be one of {list(_VALID_ROLES)}; got '{role}'"}

    conn = db()
    cur = await conn.execute("SELECT 1 FROM users WHERE username = ?", (username,))
    if await cur.fetchone() is not None:
        return {"error": f"user '{username}' already exists (use reset_user_password instead)"}

    password = _generate_password()
    await conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), username, hash_password(password), role,
         datetime.now(timezone.utc).isoformat()),
    )
    await conn.commit()
    return {
        "username": username,
        "role": role,
        "password": password,
        "note": "Give this password to the user out-of-band. It is shown only once.",
    }


async def set_user_role(ctx: ToolContext, args: dict) -> dict:
    if (err := _require_admin(ctx)):
        return err
    username = (args.get("username") or "").strip()
    role = (args.get("role") or "").strip()
    if not username or role not in _VALID_ROLES:
        return {"error": f"username and role (one of {list(_VALID_ROLES)}) are required"}

    conn = db()
    cur = await conn.execute("SELECT id, role FROM users WHERE username = ?", (username,))
    row = await cur.fetchone()
    if row is None:
        return {"error": f"user '{username}' not found"}
    prior = row["role"]
    if prior == "admin" and role != "admin" and not await _other_admin_exists(row["id"]):
        return {"error": "cannot demote the last admin — create another admin first"}
    await conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, row["id"]))
    await conn.commit()
    return {
        "username": username,
        "prior_role": prior,
        "role": role,
        "note": "Active sessions keep their old role until logout or expiry.",
    }


async def reset_user_password(ctx: ToolContext, args: dict) -> dict:
    if (err := _require_admin(ctx)):
        return err
    username = (args.get("username") or "").strip()
    if not username:
        return {"error": "username is required"}
    conn = db()
    cur = await conn.execute("SELECT id FROM users WHERE username = ?", (username,))
    row = await cur.fetchone()
    if row is None:
        return {"error": f"user '{username}' not found"}
    password = _generate_password()
    await conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), row["id"])
    )
    await conn.commit()
    return {
        "username": username,
        "password": password,
        "note": "Shown once. Existing sessions are not revoked; only future logins use it.",
    }


async def delete_user(ctx: ToolContext, args: dict) -> dict:
    if (err := _require_admin(ctx)):
        return err
    username = (args.get("username") or "").strip()
    if not username:
        return {"error": "username is required"}
    actor = getattr(ctx, "user", None)
    if actor is not None and actor.username == username:
        return {"error": "cannot delete your own account — ask another admin"}

    conn = db()
    cur = await conn.execute("SELECT id, role FROM users WHERE username = ?", (username,))
    row = await cur.fetchone()
    if row is None:
        return {"error": f"user '{username}' not found"}
    if row["role"] == "admin" and not await _other_admin_exists(row["id"]):
        return {"error": "cannot delete the last admin"}
    await conn.execute("DELETE FROM users WHERE id = ?", (row["id"],))
    await conn.commit()
    return {"username": username, "deleted": True}


async def _other_admin_exists(exclude_id: str) -> bool:
    cur = await db().execute(
        "SELECT 1 FROM users WHERE role = 'admin' AND id != ? LIMIT 1", (exclude_id,)
    )
    return await cur.fetchone() is not None


async def link_telegram(ctx: ToolContext, _args: dict) -> dict:
    """Issue a one-time code to connect the current user's Telegram chat."""
    user = getattr(ctx, "user", None)
    if user is None:
        return {"error": "no user context"}
    if not settings.telegram_enabled:
        return {"error": "Telegram isn't configured on this server (no bot token set)."}
    res = await issue_link_code(user.id)
    return {
        **res,
        "instructions": f"Open the bot in Telegram and send: /link {res['code']} "
                        f"(valid for {res['expires_min']} minutes).",
    }


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


_ROLE_PROP = {"type": "string", "enum": list(_VALID_ROLES), "description": "Either 'user' or 'admin'."}

USER_TOOLS: list[dict] = [
    _tool("list_users", "List all accounts (username, role, timestamps). Admin only.", {}, []),
    _tool(
        "create_user",
        "Create a new account. Admin only. Server generates a password and returns it once.",
        {"username": {"type": "string"}, "role": _ROLE_PROP},
        ["username"],
    ),
    _tool(
        "set_user_role",
        "Change an account's role (user/admin). Admin only. The last admin cannot be demoted.",
        {"username": {"type": "string"}, "role": _ROLE_PROP},
        ["username", "role"],
    ),
    _tool(
        "reset_user_password",
        "Generate a fresh password for an account. Admin only. Returns it once.",
        {"username": {"type": "string"}},
        ["username"],
    ),
    _tool(
        "delete_user",
        "Delete an account. Admin only. Cannot delete yourself or the last admin.",
        {"username": {"type": "string"}},
        ["username"],
    ),
    _tool(
        "link_telegram",
        "Start linking the current user's Telegram to the assistant: returns a one-time code "
        "to send to the bot as '/link <code>'. Requires a bot token configured on the server.",
        {}, [],
    ),
]

USER_HANDLERS = {
    "list_users": list_users,
    "create_user": create_user,
    "set_user_role": set_user_role,
    "reset_user_password": reset_user_password,
    "delete_user": delete_user,
    "link_telegram": link_telegram,
}
