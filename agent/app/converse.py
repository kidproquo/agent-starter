"""Run the agent for a non-SSE text channel and capture its answer as text.

Drives the SAME `run_agent` entry point the web UI uses — so tool behavior,
multi-turn memory (via conversation_id), and usage accounting are identical — by
draining its SSE stream and flattening the emitted render blocks into plain
text/markdown. Used by the Telegram bot; reusable by any text transport.
"""
from __future__ import annotations

import json

from .agent import run_agent
from .schemas import PromptContext, PromptRequest


def _parse_sse(chunk: bytes) -> tuple[str, dict] | None:
    event: str | None = None
    data_raw: str | None = None
    for line in chunk.decode("utf-8", "replace").splitlines():
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data_raw = line[5:].strip()
    if event is None:
        return None
    try:
        data = json.loads(data_raw) if data_raw else {}
    except json.JSONDecodeError:
        data = {}
    return event, data if isinstance(data, dict) else {}


def _block_to_text(b: dict) -> str:
    """Flatten one render block to markdown text (rendered to HTML on send)."""
    t = b.get("type")
    if t == "markdown":
        return (b.get("content") or "").strip()
    if t == "metric":
        unit = f" {b['unit']}" if b.get("unit") else ""
        return f"**{b.get('label', '')}**: {b.get('value', '')}{unit}".strip()
    if t == "table":
        head = f"**{b['title']}**\n" if b.get("title") else ""
        cols = b.get("columns") or []
        rows = b.get("rows") or []
        lines = [" | ".join(str(c) for c in cols)]
        lines += [" | ".join(str(c) for c in r) for r in rows[:30]]
        if len(rows) > 30:
            lines.append(f"… (+{len(rows) - 30} more)")
        return head + "```\n" + "\n".join(lines) + "\n```"
    if t == "timeline":
        head = f"**{b['title']}**\n" if b.get("title") else ""
        evs = b.get("events") or []
        return head + "\n".join(f"• {e.get('ts', '')} — {e.get('label', '')}" for e in evs)
    if t == "chart":
        return f"_[chart: {b.get('title') or 'open the app to view'}]_"
    return ""


async def run_captured(
    user,
    prompt: str,
    *,
    conversation_id: str | None = None,
    attachment_text: str | None = None,
) -> str:
    """Run one agent turn and return its user-visible answer as text."""
    req = PromptRequest(
        prompt=prompt,
        context=PromptContext(conversation_id=conversation_id, attachment_text=attachment_text),
    )
    blocks: list[dict] = []
    error: str | None = None
    async for chunk in run_agent(req, user=user):
        parsed = _parse_sse(chunk)
        if parsed is None:
            continue
        event, data = parsed
        if event == "block":
            blocks.append(data)
        elif event == "error":
            error = data.get("error") or error

    parts = [p for p in (_block_to_text(b) for b in blocks) if p]
    text = "\n\n".join(parts).strip()
    if not text:
        text = error or "I couldn't produce an answer to that."
    return text[:4000]
