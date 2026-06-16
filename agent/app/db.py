"""SQLite data layer (aiosqlite).

One process-wide connection (aiosqlite serializes operations on its own worker
thread, so sharing it across coroutines is safe). Holds users, sessions,
per-user token usage, and runtime LLM config. The file lives on a Docker volume
so it survives redeploys.
"""
from __future__ import annotations

from pathlib import Path

import aiosqlite

from .config import settings

_conn: aiosqlite.Connection | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id            TEXT PRIMARY KEY,
  username      TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'user',
  created_at    TEXT NOT NULL,
  last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
  id         TEXT PRIMARY KEY,
  user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

-- Cumulative token usage, rolled up per (user, model). Incremented once per
-- completed agent turn.
CREATE TABLE IF NOT EXISTS usage (
  username                     TEXT NOT NULL,
  model                        TEXT NOT NULL,
  input_tokens                 INTEGER NOT NULL DEFAULT 0,
  output_tokens                INTEGER NOT NULL DEFAULT 0,
  cache_read_input_tokens      INTEGER NOT NULL DEFAULT 0,
  cache_creation_input_tokens  INTEGER NOT NULL DEFAULT 0,
  turns                        INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (username, model)
);

-- Runtime LLM config overrides (model / effort / max_tokens / provider keys).
-- A missing key falls back to env/Settings — see config_store.effective().
CREATE TABLE IF NOT EXISTS config (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


async def init_db() -> None:
    global _conn
    path = Path(settings.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _conn = await aiosqlite.connect(str(path))
    _conn.row_factory = aiosqlite.Row
    await _conn.execute("PRAGMA journal_mode=WAL")
    await _conn.execute("PRAGMA foreign_keys=ON")
    await _conn.executescript(_SCHEMA)
    await _conn.commit()


def db() -> aiosqlite.Connection:
    if _conn is None:
        raise RuntimeError("db not initialized — call init_db() on startup")
    return _conn


async def close_db() -> None:
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None
