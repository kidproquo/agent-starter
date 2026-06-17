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

## Deploy behind a reverse proxy

`docker compose up` publishes the frontend (nginx) on `:8300`; it serves the SPA and
proxies `/api/` to the agent on the internal network. Put a TLS-terminating reverse proxy
in front of `:8300` to expose it on a domain.

The frontend image is built with Vite `base: './'` and derives its API URL from
`document.baseURI` (`src/lib/apiBase.ts`), so **the same image works at a root domain or
under a subpath with no rebuild** — as long as the proxy strips the subpath prefix before
forwarding. Two rules for any setup:

- **Don't buffer** — these are SSE streams. Disable proxy buffering and use a long read
  timeout, or responses will arrive only after the agent finishes.
- **Subpath → strip the prefix.** Mounting at `/agent/` means the browser requests
  `/agent/api/...`; the proxy must forward `/api/...` to `:8300` (whose nginx knows `/api/`).

When serving over HTTPS, set `COOKIE_SECURE=true` in `.env` (so the session cookie gets the
`Secure` flag), and make sure `ALLOWED_ORIGINS` includes your public origin.

### Caddy

Root domain (Caddy provisions TLS automatically):

```caddyfile
agent.example.com {
    reverse_proxy localhost:8300
}
```

Under a subpath, e.g. `https://example.com/agent/` — `handle_path` strips the `/agent`
prefix before proxying. The `redir` sends the bare path to the trailing-slash form so
`document.baseURI` ends in `/` and the SPA's relative base resolves API URLs under
`/agent/` (without it, they'd resolve against the site root and break):

```caddyfile
example.com {
    # Bare path → trailing-slash form (so the SPA's relative API base is correct).
    redir /agent /agent/ 301

    handle_path /agent/* {
        reverse_proxy localhost:8300
    }
}
```

Caddy streams SSE and sets sane proxy timeouts by default, so no extra tuning is needed.

### nginx

Root domain:

```nginx
server {
    listen 443 ssl;
    server_name agent.example.com;

    ssl_certificate     /etc/letsencrypt/live/agent.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/agent.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8300;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Connection "";
        # SSE: stream tokens as they arrive.
        proxy_buffering off;
        proxy_read_timeout 3600s;
    }
}
```

Under a subpath, e.g. `https://example.com/agent/` — the trailing slash on `proxy_pass`
strips the `/agent/` prefix:

```nginx
# Redirect the bare path to the trailing-slash form.
location = /agent { return 301 /agent/; }

location /agent/ {
    proxy_pass http://127.0.0.1:8300/;   # trailing "/" strips the /agent/ prefix
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header Connection "";
    proxy_buffering off;
    proxy_read_timeout 3600s;
}
```

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
