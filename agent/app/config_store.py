"""Runtime LLM config, stored in SQLite, overriding env/Settings.

Unlike drift (which rewrites .env and restarts the container), we read the
effective config from the DB on every agent turn — so an admin's change via the
settings modal takes effect on the next conversation with no restart.

Provider API keys default to whatever is in the process env (from .env /
compose); a DB value overrides it. Keys are write-only at the API layer — see
admin_config.py — but stored in plaintext here (same trust model as .env).
"""
from __future__ import annotations

import os

from .config import settings
from .db import db

# Config keys we persist. model/effort/max_tokens + one key per provider.
PROVIDER_ENV = {
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "openai_api_key": "OPENAI_API_KEY",
    "gemini_api_key": "GEMINI_API_KEY",
}


async def get_overrides() -> dict[str, str]:
    cur = await db().execute("SELECT key, value FROM config")
    return {r["key"]: r["value"] for r in await cur.fetchall()}


async def set_overrides(updates: dict[str, str]) -> None:
    conn = db()
    for key, value in updates.items():
        await conn.execute(
            "INSERT INTO config (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
    await conn.commit()


async def effective_config() -> dict:
    """Resolve the LLM config the agent should use: DB override, else env/Settings."""
    o = await get_overrides()

    def key(name: str) -> str:
        return o.get(name) or os.environ.get(PROVIDER_ENV[name], "")

    try:
        max_tokens = int(o.get("max_tokens") or settings.max_tokens)
    except (TypeError, ValueError):
        max_tokens = settings.max_tokens

    return {
        "model": o.get("model") or settings.model,
        "effort": o.get("effort") or settings.reasoning_effort,
        "max_tokens": max_tokens,
        "anthropic_api_key": key("anthropic_api_key"),
        "openai_api_key": key("openai_api_key"),
        "gemini_api_key": key("gemini_api_key"),
    }


def apply_provider_keys(cfg: dict) -> None:
    """Push resolved provider keys into os.environ so litellm picks them up."""
    for field, env_name in PROVIDER_ENV.items():
        val = cfg.get(field)
        if val:
            os.environ[env_name] = val
