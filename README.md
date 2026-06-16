# Agent Starter

A full-stack starter for building **streaming, tool-use AI agents** with a chat UI,
multi-user auth, and runtime LLM configuration. Provider-agnostic via
[litellm](https://github.com/BerriAI/litellm) — point it at Anthropic, OpenAI, Gemini,
or anything litellm supports.

Strip the example tools, drop in your own, and you have a deployable app.

## What you get

**Frontend** (`src/`) — React 18 + MUI 6 + Vite + TypeScript, zustand, react-query, react-plotly.
- Streaming chat with a collapsible **scratchpad** (model reasoning) separated from the
  user-visible answer, which is assembled from typed **render blocks**: markdown, metric
  cards, tables, charts (Plotly), and timelines.
- Multi-turn **conversation** history persisted to localStorage.
- **Login gate**, admin **LLM settings modal** (model/effort/keys, write-only + validated),
  per-conversation **export to HTML/PDF** (select turns), dark/light mode, live token/cost readout.

**Backend** (`agent/`) — FastAPI + litellm, Python 3.12.
- Streaming tool-use loop (`app/agent.py`) over SSE; tools live in `app/tools/`.
- **Auth**: cookie sessions, bootstrap admin, login throttle, bcrypt (`app/auth/`).
- **Per-user usage** accounting (tokens + cache, priced per model) in SQLite (`app/db.py`).
- **Runtime LLM config**: admins change model/keys via the UI; resolved per turn, no restart
  (`app/admin_config.py`, `app/config_store.py`).
- Optional document **upload + server-side text extraction** (`app/extract.py`).

## Quick start

### Docker (both halves)
```bash
cp .env.example .env     # set a provider key + ADMIN_PASSWORD
docker compose up --build
# open http://localhost:8300  (log in with ADMIN_USERNAME / ADMIN_PASSWORD)
```

### Local dev
```bash
# backend
cd agent && python -m venv .venv && . .venv/bin/activate && pip install -e .
ADMIN_USERNAME=admin ADMIN_PASSWORD=dev DB_PATH=./app.db uvicorn app.main:app --reload --port 8000
# frontend (separate shell)
npm install && npm run dev      # http://localhost:5173, proxies /api → :8000
```

Explore the UI with **no backend** by building the mock engine: `VITE_ENGINE=mock npm run dev`.

## Make it yours

1. **Add tools.** Copy `agent/app/tools/example.py` → your module, export `*_TOOLS`
   (OpenAI function schemas) + `*_HANDLERS` (`async (ctx, args) -> dict`), and register them
   in `agent/app/tools/__init__.py`. Delete `example.py` when done.
2. **Set the persona.** Edit `SYSTEM_PROMPT` in `agent/app/agent.py`.
3. **Tune render blocks.** Block types are mirrored in `src/types/blocks.ts` ↔
   `agent/app/schemas.py` — keep them in sync.
4. **Rebrand.** App name appears in `index.html`, `src/components/LoginPage.tsx`,
   `src/components/Sidebar/ConversationList.tsx`, and `package.json`.

See `CLAUDE.md` for architecture notes and conventions.
