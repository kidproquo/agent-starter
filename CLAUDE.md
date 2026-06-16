# CLAUDE.md

Guidance for working in this repo.

## What this is

**Agent Starter** — a full-stack template for streaming, litellm-based tool-use agents.
A React chat UI talks to a FastAPI agent over SSE; the agent runs a tool-use loop and
streams back typed render blocks. Includes multi-user auth, per-user token/cost
accounting, and admin-editable runtime LLM config. Swap the example tools in
`agent/app/tools/` for your own to build a real app.

Two parts:
- **Frontend** (repo root, `src/`) — React 18 + MUI 6 + Vite, TypeScript, zustand,
  react-query, react-plotly. A streaming chat UI.
- **Backend** (`agent/`) — FastAPI + **litellm** tool-use agent. Python 3.12.

## Commands

Frontend (repo root):
- `npm run dev` — Vite dev server on :5173, proxies `/api` → :8000.
- `npm run typecheck` — `tsc --noEmit`. Run before claiming a change builds.
- `npm run build` — typecheck + production build.
- `VITE_ENGINE=mock npm run dev` — explore the UI with a canned backend (no API key).

Backend (`agent/`, with `.venv` activated, `pip install -e .`):
- `uvicorn app.main:app --reload --port 8000` — run the API. Needs `ADMIN_USERNAME`,
  `ADMIN_PASSWORD`, and a provider key in the env (or `.env`).

## The streaming protocol (how front and back talk)

`POST /chat` returns `text/event-stream`. The backend yields SSE events; the frontend
`AgentAdapter` maps them to `AgentEvent`s, and `useConverse` reduces those into the
`conversationStore`. Event types (keep both sides in sync):

`start · thinking · narrative · tool_call · tool_result · data · block · metadata · done · error`

Key idea: **plain model text is scratchpad reasoning**, shown in the collapsible
`Scratchpad`. The user-visible answer is built only from emit-tool `block` events. Large
series are sent once as a `data` event keyed by a `ref`; `block`s of type `chart` carry
just the `dataRef`, resolved via the in-memory `dataRegistry`.

Render block types live in **two mirrored places** — keep them identical:
`src/types/blocks.ts` ↔ `agent/app/schemas.py`.

## Backend structure (`agent/app/`)

- `agent.py` — the litellm streaming tool-use loop + `SYSTEM_PROMPT`. Accumulates streamed
  `tool_calls` by index, runs handlers, loops. Sets `litellm.drop_params = True` so the same
  code runs across providers. Normalizes per-turn usage and attributes it to the operator.
- `config.py` — pydantic-settings. `MODEL` is a litellm string; provider keys come from the
  env. An admin can override model/effort/keys at runtime (stored in the DB).
- `config_store.py` / `admin_config.py` — runtime LLM config. `effective_config()` resolves
  DB override → env each turn; `apply_provider_keys()` pushes keys into `os.environ`.
- `db.py` — one aiosqlite connection: users, sessions, usage, config tables.
- `auth/` — cookie sessions, bootstrap admin, password hashing, usage rollups, route deps.
- `tools/` — each module exports `*_TOOLS` (OpenAI function schemas) and `*_HANDLERS`
  (`async (ctx, args) -> dict`), aggregated in `tools/__init__.py`:
  - `example.py` — `compute`, `sample_series`. **Replace these with your own tools.**
  - `users.py` — admin user-management tools (gated on `ctx.user.is_admin`).
  - `emit.py` — `make_markdown|metric|table|chart|timeline` (push `block`/`data` SSE).
- `tools/context.py` — `ToolContext` (the `emit` callback, `data_cache` for chart refs, `user`).
- `extract.py` — server-side text extraction for the optional `/chat/upload` route.

## Conventions

- Adding a tool: write the handler + schema in a `tools/*.py` module, register it in
  `tools/__init__.py`, and (if useful) add a one-line preview in
  `agent.py:_summarize_for_event` so the UI chip shows a meaningful summary.
- Tools return real data or a clear `{"error": ...}`; the agent is told not to invent facts.
  External calls must degrade gracefully.
- Frontend domain entity is **conversation**: `conversationStore`, `useConverse`,
  `ConversationList`, localStorage key `app.conversations.v1`. The transcript view component
  is `Transcript` (distinct from the `Conversation` data type).
- Auth env: `ADMIN_USERNAME` / `ADMIN_PASSWORD` bootstrap the first admin on startup.

## Gotchas

- Cookie sessions require credentialed CORS: `allow_credentials=True` with a non-wildcard
  `ALLOWED_ORIGINS` that includes your frontend origin.
- API keys are stored in SQLite in plaintext (same trust model as `.env`). The DB lives on a
  Docker named volume so saved overrides survive redeploys.
- Conversation memory (`_session_history` in `agent.py`) is in-memory only — a restart loses
  it; the persisted frontend store still shows past turns.
