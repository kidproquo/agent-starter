from __future__ import annotations

import json
from typing import Any, AsyncGenerator

import litellm

from .config import settings
from .config_store import apply_provider_keys, effective_config
from .auth.usage import record_usage
from .schemas import PromptRequest
from .stream import sse
from .tools import all_handlers, all_tools
from .tools.context import ToolContext

# Drop provider-unsupported params (e.g. reasoning_effort on non-reasoning models)
# instead of raising, so the same code path works across litellm providers.
litellm.drop_params = True


# Per-conversation conversation history. Keyed by conversation_id, value is the
# list[dict] of LiteLLM/OpenAI-shape message objects accumulated across turns
# (role ∈ {system, user, assistant, tool}). In-memory only — a server restart
# loses it. For single-user usage this is fine; the frontend's persisted
# Zustand store still shows past turns for display, the agent just answers the
# next prompt fresh on a cold cache.
_session_history: dict[str, list[dict]] = {}

# Token-saving knobs for the session-history pipeline:
# - Tool results over this many bytes get truncated when persisted. The full
#   output was consumed by the assistant on the turn that produced it;
#   subsequent turns just need a hint. 4 KB ≈ 1k tokens.
_MAX_TOOL_RESULT_BYTES = 4096
# - Keep at most this many user-initiated turns per conversation.
_MAX_TURNS = 20


def _compact_history_for_save(messages: list[dict]) -> list[dict]:
    """Cap large tool-result content before persisting to session history.

    OpenAI-shape tool results live in `{role: "tool", tool_call_id, content}`
    messages; the content is a JSON-stringified payload. We truncate the
    string when it exceeds _MAX_TOOL_RESULT_BYTES — the assistant already
    consumed the full output on the turn it was produced; later turns only
    need to remember the call happened.
    """
    out: list[dict] = []
    for msg in messages:
        if msg.get("role") == "tool":
            body = msg.get("content")
            if isinstance(body, str) and len(body) > _MAX_TOOL_RESULT_BYTES:
                truncated = (
                    body[:_MAX_TOOL_RESULT_BYTES]
                    + f"\n… [tool result truncated for history: {len(body)} bytes "
                    "total. Re-call the tool if you need the full output.]"
                )
                out.append({**msg, "content": truncated})
                continue
        out.append(msg)
    return out


def _trim_to_recent_turns(messages: list[dict], max_turns: int = _MAX_TURNS) -> list[dict]:
    """Drop older user-initiated turns from the front, keeping the last N.

    Cut at user-prompt boundaries (role=user) so every kept segment starts
    with a user prompt and preserves the assistant→tool_calls→tool pairing
    the OpenAI/LiteLLM API requires. A leading system message is preserved.
    """
    prompt_indices = [i for i, m in enumerate(messages) if m.get("role") == "user"]
    if len(prompt_indices) <= max_turns:
        return messages
    cut = prompt_indices[-max_turns]
    if messages and messages[0].get("role") == "system":
        return [messages[0], *messages[cut:]]
    return messages[cut:]


def _normalize_usage(u: Any) -> dict[str, int]:
    """Map provider-specific litellm usage to a stable 4-kind shape.

      - input: uncached, billed-per-token prompt tokens (fresh only).
      - output: completion / assistant tokens.
      - cache_read: prompt tokens served from a cache hit.
      - cache_creation: prompt tokens written to cache (Anthropic-only).

    OpenAI's `prompt_tokens` INCLUDES `cached_tokens` (a subset); Anthropic via
    LiteLLM reports `cache_read_input_tokens` separately. We detect which shape
    we got and subtract appropriately so "input" is always fresh-only.
    """
    empty = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    if u is None:
        return empty
    prompt = getattr(u, "prompt_tokens", 0) or 0
    completion = getattr(u, "completion_tokens", 0) or 0
    cache_read_anthropic = getattr(u, "cache_read_input_tokens", 0) or 0
    cache_creation = getattr(u, "cache_creation_input_tokens", 0) or 0
    cache_read_openai = 0
    details = getattr(u, "prompt_tokens_details", None)
    if details is not None:
        if isinstance(details, dict):
            cache_read_openai = details.get("cached_tokens", 0) or 0
        else:
            cache_read_openai = getattr(details, "cached_tokens", 0) or 0
    cache_read = cache_read_anthropic + cache_read_openai
    if cache_read_anthropic:
        # Anthropic via LiteLLM: prompt_tokens excludes cached; use as-is.
        input_tokens = prompt
    else:
        # OpenAI/Gemini: prompt_tokens INCLUDES cached; subtract for fresh input.
        input_tokens = max(0, prompt - cache_read_openai)
    return {
        "input_tokens": input_tokens,
        "output_tokens": completion,
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_creation,
    }


SYSTEM_PROMPT = """\
You are a helpful, precise assistant that answers by calling tools.

You have tools in three groups:

1. **Task tools** — the example `compute` (arithmetic) and `sample_series` (generates a \
chart data `ref`). Replace these with your domain's tools. Prefer calling a tool over \
doing the work in your head, so results are reproducible.

2. **User management** (admins only) — list/create/update users. The operator line at the \
top of the user message tells you who you're serving and whether these are available.

3. **Emit tools** — `make_markdown`, `make_metric`, `make_table`, `make_chart`, and \
`make_timeline`. This is how you produce the user-visible answer.

How you work:

- **Gather real data first.** Call the task tools to get concrete values; don't invent \
facts. If something is unavailable, say so plainly.
- **Emit your answer via the emit tools.** Anything you type as plain text is treated as \
internal scratchpad reasoning, shown to the user separately — it is NOT the answer. The \
user-visible response must be built from emit-tool blocks.
- Open with a one-line summary in `make_markdown`, use `make_metric` cards for headline \
numbers, `make_chart` for any series (pass it a `ref` from a data tool), and `make_table` \
for tabular data. Keep it focused.
- Be honest about uncertainty; thin evidence means a tentative conclusion.\
"""


def _summarize_for_event(name: str, result: Any) -> str:
    """Compact one-line preview for the UI's tool-call chip."""
    if not isinstance(result, dict):
        return type(result).__name__
    if "error" in result:
        return f"error: {result['error']}"
    if name == "compute":
        return f"{result.get('operation')} → {result.get('result')}"
    if name == "sample_series":
        return f"{result.get('n_points', 0)} pts · ref {result.get('ref', '?')}"
    if name in ("list_users", "create_user", "update_user", "delete_user"):
        return result.get("summary") or "ok"
    if name.startswith("make_"):
        return result.get("emitted", "ok")
    return "ok"


def _build_user_content(req: PromptRequest) -> str:
    content = req.prompt
    if not req.context:
        return content
    if req.context.attachment_text:
        excerpt = req.context.attachment_text.strip()
        content += (
            "\n\n[attached document text follows — use it as context]\n\n"
            f"\"\"\"\n{excerpt[:60000]}\n\"\"\""
        )
    return content


def _operator_prefix(user: Any) -> str:
    """A short identity line so the model knows who it's serving and whether
    user-management tools are available to them."""
    if user is None:
        return ""
    cap = "admin (may manage users via the user tools)" if user.is_admin else "user (standard access)"
    return f"[operator: {user.username} · role={user.role} · {cap}]\n\n"


async def run_agent(req: PromptRequest, user: Any = None) -> AsyncGenerator[bytes, None]:
    """Run the litellm tool-use loop and yield SSE bytes for the response stream."""
    events: list[bytes] = []

    async def emit(event: str, data: Any) -> None:
        events.append(sse(event, data))

    ctx = ToolContext(emit=emit, request=req.context, user=user)
    handlers = all_handlers()
    tools = all_tools()

    # Effective LLM config: an admin's DB override, else env/Settings. Resolved
    # per turn so settings-modal changes take effect with no restart.
    cfg = await effective_config()
    apply_provider_keys(cfg)
    model = cfg["model"]
    max_tokens = cfg["max_tokens"]
    effort = cfg["effort"]

    conversation_id = req.context.conversation_id if req.context else None

    # Conversation memory: when the same conversation_id submits multiple turns,
    # prepend prior user/assistant/tool messages so follow-ups ("what about
    # its competitor?", "redo that with a 10% discount rate") chain coherently.
    # History is OpenAI-shape (LiteLLM's canonical format). In-memory only.
    prior = _session_history.get(conversation_id, []) if conversation_id else []
    # Drop any leading system message from prior — we re-prepend the latest
    # SYSTEM_PROMPT below so prompt edits between turns take effect.
    if prior and prior[0].get("role") == "system":
        prior = prior[1:]

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *prior,
        {"role": "user", "content": _operator_prefix(user) + _build_user_content(req)},
    ]

    # Accumulate token usage across every iteration of this turn (each tool-use
    # round-trip is a separate litellm call with its own usage chunk).
    turn_usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }

    yield sse("start", {"engine": model})

    try:
        for _iteration in range(settings.max_iterations):
            text_parts: list[str] = []
            tool_calls: dict[int, dict] = {}

            response = await litellm.acompletion(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=max_tokens,
                temperature=settings.temperature,
                reasoning_effort=effort or None,
                stream=True,
                stream_options={"include_usage": True},
            )

            async for chunk in response:
                if getattr(chunk, "usage", None):
                    for k, v in _normalize_usage(chunk.usage).items():
                        turn_usage[k] += v
                choices = getattr(chunk, "choices", None)
                if not choices:
                    continue
                delta = choices[0].delta
                if delta is None:
                    continue

                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning:
                    yield sse("thinking", {"text": reasoning})

                if getattr(delta, "content", None):
                    text_parts.append(delta.content)
                    yield sse("narrative", {"text": delta.content})

                for tc in getattr(delta, "tool_calls", None) or []:
                    idx = tc.index
                    slot = tool_calls.setdefault(idx, {"id": None, "name": "", "arguments": ""})
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function and tc.function.name:
                        slot["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        slot["arguments"] += tc.function.arguments

            calls = [tool_calls[i] for i in sorted(tool_calls)]

            if not calls:
                # No more tools — record the final assistant turn so the next
                # prompt on this conversation sees it, then persist + surface usage.
                messages.append({"role": "assistant", "content": "".join(text_parts)})
                if conversation_id:
                    compacted = _compact_history_for_save(messages)
                    _session_history[conversation_id] = _trim_to_recent_turns(compacted)
                # Attribute this turn's tokens to the operator (best-effort —
                # a usage write failure must not break the response).
                if user is not None:
                    try:
                        await record_usage(user.username, model, turn_usage)
                    except Exception:  # noqa: BLE001
                        pass
                yield sse(
                    "metadata",
                    {"engine": model, "stop_reason": "stop", "usage": dict(turn_usage)},
                )
                yield sse("done", {})
                return

            # Record the assistant turn (text + tool calls) before executing tools.
            messages.append(
                {
                    "role": "assistant",
                    "content": "".join(text_parts) or None,
                    "tool_calls": [
                        {
                            "id": c["id"],
                            "type": "function",
                            "function": {"name": c["name"], "arguments": c["arguments"] or "{}"},
                        }
                        for c in calls
                    ],
                }
            )

            for c in calls:
                yield sse("tool_call", {"id": c["id"], "name": c["name"], "args": _safe_json(c["arguments"])})

                handler = handlers.get(c["name"])
                if handler is None:
                    result: Any = {"error": f"unknown tool: {c['name']}"}
                else:
                    try:
                        args = json.loads(c["arguments"] or "{}")
                        result = await handler(ctx, args)
                    except Exception as e:  # noqa: BLE001
                        result = {"error": f"{type(e).__name__}: {e}"}

                # Flush any SSE the tool queued (block / data events).
                while events:
                    yield events.pop(0)

                yield sse(
                    "tool_result",
                    {
                        "id": c["id"],
                        "name": c["name"],
                        "summary": _summarize_for_event(c["name"], result),
                        "is_error": isinstance(result, dict) and "error" in result,
                    },
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": c["id"],
                        "content": json.dumps(result, default=str),
                    }
                )

        yield sse("error", {"error": "agent loop exceeded iteration cap"})
        yield sse("done", {})
    except Exception as e:  # noqa: BLE001
        yield sse("error", {"error": f"{type(e).__name__}: {e}"})
        yield sse("done", {})


def _safe_json(raw: str) -> Any:
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {"_raw": raw}
