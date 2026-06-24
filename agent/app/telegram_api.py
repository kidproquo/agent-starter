"""Thin async Telegram Bot API client (+ markdown -> Telegram HTML rendering).

Self-contained: httpx + a bot token. Only the calls the bot needs — long-poll
for updates, send a message, fetch/download a file, identify the bot, show a
typing indicator. send_message renders the agent's markdown as Telegram HTML
with a stripped-plaintext fallback so a formatting quirk never blocks delivery.
"""
from __future__ import annotations

import html as _html
import logging
import re

import httpx

from .config import settings

logger = logging.getLogger("agent.telegram")

_MAX_LEN = 3900  # headroom under Telegram's 4096 cap once HTML entities are added


def _api(method: str) -> str:
    return f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"


def to_telegram_html(md: str) -> str:
    """Convert GitHub-flavored markdown into the small HTML subset Telegram
    supports (<b>/<i>/<code>/<pre>/<a>). Heuristic but balanced-by-construction,
    so output is valid; send_message falls back to plain text if Telegram rejects it."""
    s = _html.escape(md or "", quote=False)  # escape & < >
    s = re.sub(r"```[^\n`]*\n?(.*?)```", lambda m: "<pre>" + m.group(1).rstrip("\n") + "</pre>", s, flags=re.S)
    s = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", s)

    def _link(m: re.Match) -> str:
        return f'<a href="{m.group(2).replace(chr(34), "%22")}">{m.group(1)}</a>'

    s = re.sub(r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)", _link, s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<!_)__(.+?)__(?!_)", r"<b>\1</b>", s)

    lines = []
    for line in s.split("\n"):
        heading = re.match(r"\s*#{1,6}\s+(.*)", line)
        if heading:
            lines.append("<b>" + heading.group(1).strip() + "</b>")
            continue
        bullet = re.match(r"(\s*)[-*+]\s+(.*)", line)
        if bullet:
            lines.append(bullet.group(1) + "• " + bullet.group(2))
            continue
        lines.append(line)
    s = "\n".join(lines)

    s = re.sub(r"(?<![\*\w])\*([^*\n]+)\*(?![\*\w])", r"<i>\1</i>", s)
    s = re.sub(r"(?<![_\w])_([^_\n]+)_(?![_\w])", r"<i>\1</i>", s)
    return s


def _strip_markdown(s: str) -> str:
    """Plain-text fallback: drop markdown markers so nothing renders literally."""
    s = re.sub(r"```[^\n`]*\n?(.*?)```", r"\1", s, flags=re.S)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"__(.+?)__", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"(?m)^\s*#{1,6}\s+", "", s)
    s = re.sub(r"(?m)^\s*[-*+]\s+", "• ", s)
    return s


async def get_updates(offset: int | None, timeout: int) -> list[dict]:
    """Long-poll for new updates. Returns the `result` list (possibly empty)."""
    body: dict = {"timeout": timeout, "allowed_updates": ["message"]}
    if offset is not None:
        body["offset"] = offset
    async with httpx.AsyncClient(timeout=timeout + 10) as client:
        r = await client.post(_api("getUpdates"), json=body)
    r.raise_for_status()
    data = r.json()
    return data.get("result", []) if data.get("ok") else []


async def _post_message(chat_id, text: str, parse_mode: str | None) -> tuple[bool, int]:
    body: dict = {"chat_id": chat_id, "text": text}
    if parse_mode:
        body["parse_mode"] = parse_mode
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(_api("sendMessage"), json=body)
        if r.status_code >= 400:
            logger.warning("telegram sendMessage to %s failed: HTTP %s %s", chat_id, r.status_code, r.text[:200])
            return False, r.status_code
        return True, r.status_code
    except Exception as e:  # noqa: BLE001
        logger.warning("telegram sendMessage to %s errored: %s: %s", chat_id, type(e).__name__, e)
        return False, 0


async def send_message(chat_id, text: str) -> bool:
    """Send a message, rendering markdown as Telegram HTML, with a stripped
    plain-text fallback if Telegram rejects the HTML. Returns True on success."""
    text = (text or "").strip()[:_MAX_LEN] or "(no content)"
    ok, _ = await _post_message(chat_id, to_telegram_html(text), "HTML")
    if ok:
        return True
    ok, _ = await _post_message(chat_id, _strip_markdown(text), None)
    return ok


async def send_chat_action(chat_id, action: str = "typing") -> None:
    """Show a transient status (e.g. "typing…"); Telegram clears it after ~5s."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(_api("sendChatAction"), json={"chat_id": chat_id, "action": action})
    except Exception:  # noqa: BLE001
        pass


async def get_file(file_id: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(_api("getFile"), json={"file_id": file_id})
        data = r.json()
        return data.get("result") if data.get("ok") else None
    except Exception:  # noqa: BLE001
        return None


async def download_file(file_path: str) -> bytes | None:
    url = f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_path}"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.get(url)
        return r.content if r.status_code < 400 else None
    except Exception:  # noqa: BLE001
        return None


async def get_me() -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(_api("getMe"))
        data = r.json()
        return data.get("result") if data.get("ok") else None
    except Exception:  # noqa: BLE001
        return None


_bot_username: str | None = None


async def bot_username() -> str | None:
    """The bot's @username (cached). Needed to build t.me/<bot>?start=<code> links."""
    global _bot_username
    if _bot_username is None:
        me = await get_me()
        if me:
            _bot_username = me.get("username")
    return _bot_username


def _qr_data_uri(data: str) -> str | None:
    """A PNG data: URI of `data` as a QR code, or None if segno is unavailable."""
    try:
        import segno
    except ImportError:
        return None
    return segno.make(data, error="m").png_data_uri(scale=5, border=2)


async def deep_link_and_qr(code: str) -> tuple[str | None, str | None]:
    """Build the t.me deep link for a /link code and a QR image data URI for it.
    Either may be None (no bot username / no QR lib), so callers fall back to the code."""
    username = await bot_username()
    if not username:
        return None, None
    link = f"https://t.me/{username}?start={code}"
    return link, _qr_data_uri(link)
