#!/usr/bin/env bash
#
# new-project.sh — scaffold a new project from this Agent Starter template,
# rebrand it, then build, launch, and validate its Docker Compose stack.
#
# Usage:
#   scripts/new-project.sh --name "FamilAI" --out ~/dev/familai \
#       --primary "#7c3aed" [--secondary "#f59e0b"] [--env PATH] [--force]
#
# Inputs:
#   --name        Display name (e.g. "FamilAI"). A lowercase slug is derived
#                 from it for package/image names (e.g. "familai").
#   --out         Output folder for the new project (created; must be empty
#                 unless --force).
#   --primary     Theme primary color (any CSS color, e.g. "#7c3aed").
#   --secondary   Theme secondary/accent color (optional).
#   --env         Path to a .env to seed the project with. Defaults to the
#                 template's .env.example (so you get a working admin login
#                 out of the box — change the password before exposing it).
#   --force       Allow a non-empty --out folder.
#   --no-validate Build + leave instructions but skip bringing the stack up.
#
# Output: a ready-to-hack project in --out with its Compose stack running and
# validated (healthz, branded frontend, admin login round-trip).
set -euo pipefail

# --- Template identity (the source this project is bootstrapped from) --------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE_NAME="agent-starter"
TEMPLATE_URL="$(git -C "$TEMPLATE_ROOT" remote get-url origin 2>/dev/null || true)"
TEMPLATE_URL="${TEMPLATE_URL:-https://github.com/kidproquo/agent-starter}"
TEMPLATE_URL="${TEMPLATE_URL%.git}"

die() { echo "error: $*" >&2; exit 1; }
note() { echo "==> $*"; }

# --- Parse args --------------------------------------------------------------
NAME="" OUT="" PRIMARY="" SECONDARY="" ENV_SRC="" FORCE=0 VALIDATE=1
while [ $# -gt 0 ]; do
  case "$1" in
    --name)        NAME="${2:?}"; shift 2 ;;
    --out)         OUT="${2:?}"; shift 2 ;;
    --primary)     PRIMARY="${2:?}"; shift 2 ;;
    --secondary)   SECONDARY="${2:?}"; shift 2 ;;
    --env)         ENV_SRC="${2:?}"; shift 2 ;;
    --force)       FORCE=1; shift ;;
    --no-validate) VALIDATE=0; shift ;;
    -h|--help)     sed -n '2,30p' "$0"; exit 0 ;;
    *)             die "unknown argument: $1" ;;
  esac
done

[ -n "$NAME" ]    || die "--name is required"
[ -n "$OUT" ]     || die "--out is required"
[ -n "$PRIMARY" ] || die "--primary (theme color) is required"
ENV_SRC="${ENV_SRC:-$TEMPLATE_ROOT/.env.example}"
[ -f "$ENV_SRC" ] || die "env file not found: $ENV_SRC"

for t in rsync curl python3 docker; do command -v "$t" >/dev/null || die "missing required tool: $t"; done
docker compose version >/dev/null 2>&1 || die "docker compose v2 is required"

# Derive a slug: lowercase, non-alphanumeric -> hyphen, trim/collapse hyphens.
SLUG="$(printf '%s' "$NAME" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//; s/-+/-/g')"
[ -n "$SLUG" ] || die "could not derive a slug from --name '$NAME'"

# Resolve OUT to an absolute path without requiring it to exist yet.
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
if [ "$FORCE" -ne 1 ] && [ -n "$(ls -A "$OUT" 2>/dev/null)" ]; then
  die "--out '$OUT' is not empty (use --force to override)"
fi

note "Template : $TEMPLATE_ROOT"
note "Name     : $NAME  (slug: $SLUG)"
note "Output   : $OUT"
note "Theme    : primary=$PRIMARY${SECONDARY:+ secondary=$SECONDARY}"
note "Env seed : $ENV_SRC"

# --- 1. Copy the template (no VCS/build/secret artifacts) --------------------
note "Copying template ..."
rsync -a \
  --exclude '.git' --exclude 'node_modules' --exclude '.venv' --exclude 'venv' \
  --exclude 'dist' --exclude 'build' --exclude '__pycache__' --exclude '*.egg-info' \
  --exclude '.env' --exclude '*.db' --exclude '.pytest_cache' --exclude '.ruff_cache' \
  --exclude 'scripts' \
  "$TEMPLATE_ROOT"/ "$OUT"/

# Seed the project's .env from the chosen source.
cp "$ENV_SRC" "$OUT/.env"

# --- 2. Rebrand + apply theme (one structured pass) --------------------------
note "Rebranding and applying theme ..."
DISP="$NAME" SLUG="$SLUG" PRIMARY="$PRIMARY" SECONDARY="$SECONDARY" \
TEMPLATE_NAME="$TEMPLATE_NAME" TEMPLATE_URL="$TEMPLATE_URL" \
python3 - "$OUT" <<'PY'
import os, sys, pathlib

root = pathlib.Path(sys.argv[1])
DISP = os.environ["DISP"]
SLUG = os.environ["SLUG"]
PRIMARY = os.environ["PRIMARY"]
SECONDARY = os.environ.get("SECONDARY", "")
TNAME = os.environ["TEMPLATE_NAME"]
TURL = os.environ["TEMPLATE_URL"]

TEXT_EXT = {".md", ".ts", ".tsx", ".js", ".py", ".toml", ".json", ".html",
            ".yml", ".yaml", ".conf", ".css", ".txt", ".example"}
NAMED = {"Dockerfile"}

# Literal swaps cover every branded string in the template: UI headers, README/
# CLAUDE headings, FastAPI title, package names, docker image names, the export
# report footer/filename, and the backend description.
SWAPS = [
    ("Agent Starter", DISP),       # display name in UI + docs
    ("agent-starter", SLUG),       # package/image/filename slug
    ("Starter backend", f"{DISP} backend"),
    ("full-stack starter", "full-stack app"),
]

def is_text(p):
    return p.suffix in TEXT_EXT or p.name in NAMED

for p in root.rglob("*"):
    if not p.is_file() or not is_text(p):
        continue
    try:
        s = p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    out = s
    for a, b in SWAPS:
        out = out.replace(a, b)
    if out != s:
        p.write_text(out, encoding="utf-8")

# --- Theme: replace primary (and optionally secondary) palette entries -------
theme = root / "src" / "theme.ts"
if theme.exists():
    import re
    t = theme.read_text(encoding="utf-8")
    t = re.sub(r"primary:\s*\{[^}]*\}",
               f"primary: {{ main: '{PRIMARY}' }}", t, count=1)
    if SECONDARY:
        t = re.sub(r"secondary:\s*\{[^}]*\}",
                   f"secondary: {{ main: '{SECONDARY}' }}", t, count=1)
    theme.write_text(t, encoding="utf-8")

# --- Make the frontend host port overridable for conflict-free validation ----
compose = root / "docker-compose.yml"
if compose.exists():
    c = compose.read_text(encoding="utf-8")
    c = c.replace('"8300:80"', '"${FRONTEND_PORT:-8300}:80"')
    compose.write_text(c, encoding="utf-8")

# --- Source attribution (added AFTER swaps so the template name survives) -----
attrib = f"> Bootstrapped from the [{TNAME}]({TURL}) template."
for fname in ("README.md", "CLAUDE.md"):
    f = root / fname
    if not f.exists():
        continue
    lines = f.read_text(encoding="utf-8").split("\n")
    for i, line in enumerate(lines):
        if line.startswith("# "):
            lines.insert(i + 1, "")
            lines.insert(i + 2, attrib)
            break
    f.write_text("\n".join(lines), encoding="utf-8")

print(f"rebranded -> {DISP} ({SLUG})")
PY

# --- 3. Fresh git history ----------------------------------------------------
note "Initializing fresh git history ..."
git -C "$OUT" init -q -b main
git -C "$OUT" add -A
git -C "$OUT" -c user.name="${GIT_AUTHOR_NAME:-$(git config user.name 2>/dev/null || echo project)}" \
              -c user.email="${GIT_AUTHOR_EMAIL:-$(git config user.email 2>/dev/null || echo project@local)}" \
  commit -q -m "Initial commit: $NAME

Bootstrapped from the $TEMPLATE_NAME template ($TEMPLATE_URL)."

if [ "$VALIDATE" -ne 1 ]; then
  note "Skipping validation (--no-validate). Project ready at: $OUT"
  exit 0
fi

# --- 4. Build, launch, validate ----------------------------------------------
COMPOSE=(docker compose -p "$SLUG" --project-directory "$OUT" -f "$OUT/docker-compose.yml")

# Pick a free host port in the 8300+ range for the frontend.
FRONTEND_PORT=""
for p in $(seq 8300 8399); do
  if ! (exec 3<>"/dev/tcp/127.0.0.1/$p") 2>/dev/null; then FRONTEND_PORT="$p"; break; fi
  exec 3>&- 2>/dev/null || true
done
[ -n "$FRONTEND_PORT" ] || die "no free host port found in 8300-8399"
export FRONTEND_PORT
note "Using host port $FRONTEND_PORT for the frontend"

note "Building images ..."
"${COMPOSE[@]}" build

note "Starting stack ..."
"${COMPOSE[@]}" up -d

cleanup_on_fail() {
  echo "--- agent logs ---" >&2
  "${COMPOSE[@]}" logs --tail 40 agent >&2 || true
  die "validation failed; stack left up for inspection (see logs above)"
}

BASE="http://localhost:$FRONTEND_PORT"

note "Waiting for /healthz ..."
ok=0
for _ in $(seq 1 60); do
  if curl -sf "$BASE/api/healthz" >/dev/null 2>&1; then ok=1; break; fi
  sleep 1
done
[ "$ok" -eq 1 ] || cleanup_on_fail
echo "    healthz: $(curl -s "$BASE/api/healthz")"

note "Checking branded frontend ..."
title="$(curl -s "$BASE/" | grep -o '<title>[^<]*</title>' || true)"
echo "    $title"
echo "$title" | grep -qF "$NAME" || cleanup_on_fail

note "Validating admin login round-trip ..."
ADMIN_USER="$(grep -E '^ADMIN_USERNAME=' "$OUT/.env" | head -1 | cut -d= -f2- || true)"
ADMIN_PASS="$(grep -E '^ADMIN_PASSWORD=' "$OUT/.env" | head -1 | cut -d= -f2- || true)"
ADMIN_USER="${ADMIN_USER:-admin}"
if [ -n "$ADMIN_PASS" ]; then
  jar="$(mktemp)"
  code="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/auth/login" \
            -H 'Content-Type: application/json' \
            -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}" -c "$jar")"
  me="$(curl -s "$BASE/api/auth/me" -b "$jar" || true)"
  rm -f "$jar"
  echo "    login HTTP $code; /auth/me -> $me"
  [ "$code" = "200" ] && echo "$me" | grep -q '"role":"admin"' || cleanup_on_fail
else
  echo "    (no ADMIN_PASSWORD in env; skipping login check)"
fi

# --- Done --------------------------------------------------------------------
cat <<EOF

✅ $NAME is ready and validated.

  Project : $OUT
  Stack   : running ($SLUG) — frontend at $BASE
  Login   : $ADMIN_USER / (from $OUT/.env)

Manage it:
  docker compose -p $SLUG --project-directory "$OUT" ps
  docker compose -p $SLUG --project-directory "$OUT" logs -f agent
  docker compose -p $SLUG --project-directory "$OUT" down        # stop
  FRONTEND_PORT=8300 docker compose -p $SLUG --project-directory "$OUT" up -d   # default port

Next: add a provider API key to $OUT/.env and restart to enable chat.
EOF
