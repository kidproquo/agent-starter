"""Model metadata endpoint.

`GET /models/pricing` returns LiteLLM's pricing table for every model LiteLLM
knows about, in a per-1M-token shape. The frontend (`src/lib/pricing.ts`) uses
it to compute token costs in the usage display, falling back to its bundled
static table until this resolves.

Pricing is public vendor information, so the endpoint is unauthenticated
(matching the rest of this single-user agent).

Cache: pricing rarely changes within a process lifetime, so the response is
computed once and reused. A restart picks up whatever pricing the bundled
LiteLLM version ships with.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter

router = APIRouter(prefix="/models", tags=["models"])


_cached: Optional[dict] = None


def _build_pricing() -> dict:
    """Translate LiteLLM's `model_cost` dict (per-token USD) into a
    per-1M-token shape. Returns `{model_id: {input_per_mtok, output_per_mtok,
    cache_read_per_mtok, cache_write_per_mtok}}`. Non-chat entries (embeddings,
    image models) and zero-priced entries (local models) are filtered out.
    """
    try:
        import litellm
    except ImportError:  # pragma: no cover (litellm is a hard dep)
        return {}

    out: dict[str, dict[str, float]] = {}
    cost_table = getattr(litellm, "model_cost", {}) or {}
    for model_id, info in cost_table.items():
        if not isinstance(info, dict):
            continue
        # Keep chat-shaped models only; missing mode → assume chat.
        mode = info.get("mode", "chat")
        if mode not in ("chat", "completion"):
            continue
        in_per_token = float(info.get("input_cost_per_token") or 0)
        out_per_token = float(info.get("output_cost_per_token") or 0)
        cache_read_per_token = float(info.get("cache_read_input_token_cost") or 0)
        cache_write_per_token = float(info.get("cache_creation_input_token_cost") or 0)
        # Skip entries with no pricing at all (local models / stubs).
        if not any((in_per_token, out_per_token, cache_read_per_token, cache_write_per_token)):
            continue
        out[model_id] = {
            "input_per_mtok": in_per_token * 1_000_000,
            "output_per_mtok": out_per_token * 1_000_000,
            "cache_read_per_mtok": cache_read_per_token * 1_000_000,
            "cache_write_per_mtok": cache_write_per_token * 1_000_000,
        }
    return out


@router.get("/pricing")
async def get_pricing() -> dict:
    global _cached
    if _cached is None:
        _cached = {
            "source": "litellm",
            "currency": "USD",
            "unit": "per_million_tokens",
            "models": _build_pricing(),
        }
    return _cached
