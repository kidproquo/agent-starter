"""Telegram bot: a chat UI for the agent over long polling.

Lifecycle mirrors the app's other startup work (start/stop + an asyncio loop).
Each incoming message is attributed to the account its chat is linked to, run
through the agent, and the answer is sent back. Documents (PDF/text) are
extracted and fed to the agent as context — the same as the /chat/upload route.

Self-contained: the transport (telegram_api), binding (telegram_links), and
capture (converse) layers carry no app-specific assumptions, so this drops into
any agent built on this template.
"""
from __future__ import annotations

import asyncio
import logging
import types

from .agent import _session_history
from .config import settings
from .converse import run_captured
from .extract import extract_text
from .telegram_api import download_file, get_file, get_updates, send_chat_action, send_message
from .telegram_links import redeem_code, user_for_chat

logger = logging.getLogger("agent.telegram")

_task: asyncio.Task | None = None

_GREETING = (
    "👋 I'm your assistant.\n\n"
    "To connect this chat, open the app, choose \"Link Telegram\" to get a code, "
    "then send it here as:\n/link YOURCODE\n\n"
    "Once linked, just message me. You can also send a PDF or text file and I'll read it.\n\n"
    "Commands: /reset clears this chat's short-term memory."
)


async def _reply(chat_id, text: str) -> None:
    await send_message(chat_id, text)


async def _keep_typing(chat_id) -> None:
    """Re-send 'typing…' every few seconds while the agent works."""
    try:
        while True:
            await send_chat_action(chat_id, "typing")
            await asyncio.sleep(4)
    except asyncio.CancelledError:
        raise


async def _handle_document(user, chat_id, document: dict, photos: list, caption: str) -> str:
    if photos and not document:
        return ("I can read PDFs and text documents sent as a file. "
                "Image understanding isn't enabled in this starter.")
    file_id = document.get("file_id")
    filename = document.get("file_name") or "document"
    content_type = document.get("mime_type") or ""
    if content_type.startswith("image/"):
        return "I can read PDFs and text documents, but not images in this starter."
    if not file_id:
        return "I couldn't read that file."
    meta = await get_file(file_id)
    data = await download_file(meta["file_path"]) if meta and meta.get("file_path") else None
    if not data:
        return "I couldn't download that file from Telegram — try again?"
    try:
        attachment_text, _ = extract_text(filename, content_type, data)
    except ValueError as e:
        return f"I couldn't read {filename}: {e}"
    return await run_captured(
        user, caption or "Summarize this document.",
        conversation_id=f"telegram:{chat_id}", attachment_text=attachment_text,
    )


async def handle_update(update: dict) -> None:
    msg = update.get("message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return
    text = (msg.get("text") or "").strip()
    caption = (msg.get("caption") or "").strip()
    document = msg.get("document")
    photos = msg.get("photo") or []

    if text.startswith("/start"):
        await _reply(chat_id, _GREETING)
        return
    if text.startswith("/link"):
        parts = text.split(maxsplit=1)
        code = parts[1].strip() if len(parts) > 1 else ""
        title = chat.get("title") or chat.get("username") or chat.get("first_name")
        user_id = await redeem_code(code, chat_id, title)
        await _reply(
            chat_id,
            "✅ Linked! This chat is now connected — ask me anything." if user_id
            else "That code is invalid or expired. Get a fresh one in the app and try again.",
        )
        return
    if text.startswith("/reset"):
        _session_history.pop(f"telegram:{chat_id}", None)
        await _reply(chat_id, "Cleared this chat's short-term memory — starting fresh.")
        return

    has_attachment = bool(document or photos)
    if not text and not has_attachment:
        return  # ignore stickers, locations, etc.

    user_row = await user_for_chat(chat_id)
    if user_row is None:
        await _reply(chat_id, "This chat isn't linked yet. Send /link <code> with a code from the app.")
        return

    user = types.SimpleNamespace(
        id=user_row["id"], username=user_row["username"],
        role=user_row.get("role", "user"), is_admin=user_row["is_admin"],
    )
    typing = asyncio.create_task(_keep_typing(chat_id))
    try:
        if has_attachment:
            answer = await _handle_document(user, chat_id, document or {}, photos, caption)
        else:
            answer = await run_captured(user, text, conversation_id=f"telegram:{chat_id}")
    except Exception as e:  # noqa: BLE001
        logger.exception("telegram: handling failed for chat %s", chat_id)
        answer = f"Sorry — something went wrong handling that ({type(e).__name__})."
    finally:
        typing.cancel()
        try:
            await typing
        except asyncio.CancelledError:
            pass
    await _reply(chat_id, answer)


async def _run_loop() -> None:
    from .telegram_api import get_me

    try:
        me = await get_me()
    except Exception:  # noqa: BLE001
        me = None
    logger.info("telegram bot started%s", f" as @{me['username']}" if me and me.get("username") else "")
    offset: int | None = None
    while True:
        try:
            updates = await get_updates(offset, settings.telegram_poll_timeout)
            for up in updates:
                offset = up["update_id"] + 1
                try:
                    await handle_update(up)
                except Exception as e:  # noqa: BLE001
                    logger.warning("telegram: failed to handle update: %s: %s", type(e).__name__, e)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.warning("telegram getUpdates failed: %s: %s", type(e).__name__, e)
            await asyncio.sleep(3)


def start_telegram_bot() -> None:
    global _task
    if _task is not None:
        return
    _task = asyncio.create_task(_run_loop())


async def stop_telegram_bot() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    _task = None
