"""Per-user token usage, accumulated in SQLite (rolled up per user+model).

Incremented once per completed agent turn; queried for the sidebar readout.
"""
from __future__ import annotations

from ..db import db

_KINDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)


async def record_usage(username: str, model: str, usage: dict) -> None:
    await db().execute(
        """
        INSERT INTO usage (
            username, model,
            input_tokens, output_tokens,
            cache_read_input_tokens, cache_creation_input_tokens, turns
        ) VALUES (?, ?, ?, ?, ?, ?, 1)
        ON CONFLICT(username, model) DO UPDATE SET
            input_tokens                = input_tokens + excluded.input_tokens,
            output_tokens               = output_tokens + excluded.output_tokens,
            cache_read_input_tokens     = cache_read_input_tokens + excluded.cache_read_input_tokens,
            cache_creation_input_tokens = cache_creation_input_tokens + excluded.cache_creation_input_tokens,
            turns                       = turns + 1
        """,
        (
            username,
            model,
            int(usage.get("input_tokens", 0) or 0),
            int(usage.get("output_tokens", 0) or 0),
            int(usage.get("cache_read_input_tokens", 0) or 0),
            int(usage.get("cache_creation_input_tokens", 0) or 0),
        ),
    )
    await db().commit()


def _blank() -> dict:
    return {k: 0 for k in _KINDS}


def _shape(rows) -> dict:
    """Roll a set of usage rows into {totals..., turns, models: {model: kinds}}."""
    totals = _blank()
    turns = 0
    models: dict[str, dict] = {}
    for r in rows:
        slot = models.setdefault(r["model"], _blank())
        for k in _KINDS:
            slot[k] += r[k]
            totals[k] += r[k]
        turns += r["turns"]
    return {**totals, "turns": turns, "models": models}


async def usage_for_user(username: str) -> dict:
    cur = await db().execute(
        "SELECT model, input_tokens, output_tokens, cache_read_input_tokens, "
        "cache_creation_input_tokens, turns FROM usage WHERE username = ?",
        (username,),
    )
    return _shape(await cur.fetchall())


async def usage_all() -> dict:
    cur = await db().execute(
        "SELECT model, input_tokens, output_tokens, cache_read_input_tokens, "
        "cache_creation_input_tokens, turns FROM usage"
    )
    return _shape(await cur.fetchall())
