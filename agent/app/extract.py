"""Server-side text extraction for uploaded documents.

Turns an uploaded PDF / HTML / plain-text file into text the agent can reason
over. Called inline by the multipart `/chat/upload` route so the extracted text
never round-trips to the browser — the file is uploaded once, extracted here,
and fed straight into the agent as `attachment_text`.

PDF extraction uses `pypdf`. If you don't need file uploads, delete this module,
the `/chat/upload` route in main.py, and the `pypdf` dependency.
"""
from __future__ import annotations

import io
import re

# Documents can be large. /chat truncates attachment_text to 60k chars anyway,
# but we keep more so the agent can field follow-ups against a larger excerpt.
MAX_TEXT_CHARS = 200_000


def _strip_html(raw: str) -> str:
    """Crude HTML→text: drop script/style and tags, unescape
    the few common entities, collapse whitespace. Good enough to feed an LLM."""
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    for entity, char in (
        ("&nbsp;", " "), ("&#160;", " "), ("&amp;", "&"),
        ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'"),
    ):
        raw = raw.replace(entity, char)
    raw = re.sub(r"[ \t ]+", " ", raw)
    raw = re.sub(r"\n\s*\n\s*\n+", "\n\n", raw)
    return raw.strip()


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n\n".join(parts).strip()


def extract_text(filename: str | None, content_type: str | None, data: bytes) -> tuple[str, bool]:
    """Extract plain text from an uploaded file. Returns (text, truncated).

    Raises ValueError if the file can't be parsed or yields no text.
    """
    name = (filename or "upload").strip().lower()
    ctype = (content_type or "").lower()

    try:
        if name.endswith(".pdf") or "pdf" in ctype:
            text = _extract_pdf(data)
        else:
            decoded = data.decode("utf-8", errors="ignore")
            if name.endswith((".htm", ".html")) or "html" in ctype:
                text = _strip_html(decoded)
            else:
                text = decoded.strip()
    except Exception as e:  # noqa: BLE001 — caller maps this to a 422
        raise ValueError(f"could not extract text: {e}") from e

    if not text:
        raise ValueError("no extractable text found")

    truncated = len(text) > MAX_TEXT_CHARS
    return text[:MAX_TEXT_CHARS], truncated
