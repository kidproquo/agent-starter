"""Admin endpoints to change the LLM model + API keys at runtime.

Stores overrides in SQLite (config table); the agent reads the effective config
on every turn, so changes take effect on the next conversation with NO restart
(unlike drift, which rewrites .env and recreates the container).

Security: admin-only. API keys are WRITE-ONLY — GET returns a masked hint
(last 4 chars) and a `set` flag, never the secret. PUT accepts a new key only
when the admin types one; a blank field leaves the stored key untouched.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel

from .auth.deps import UserContext, require_role
from .config_store import effective_config, set_overrides

router = APIRouter(prefix="/admin/llm-settings", tags=["admin"])

_PROVIDERS = ("anthropic", "openai", "gemini")


def _detect_provider(model: str) -> str:
    bare = model.split("/", 1)[-1] if "/" in model else model
    if model.startswith(("ollama/", "ollama_chat/")):
        return "ollama"
    if bare.startswith("claude-") or model.startswith("anthropic/"):
        return "anthropic"
    if bare.startswith(("gpt-", "o1", "o3")):
        return "openai"
    if bare.startswith("gemini-") or model.startswith("gemini/"):
        return "gemini"
    return "unknown"


def _mask(key: str) -> dict:
    if not key:
        return {"set": False, "hint": ""}
    tail = key[-4:] if len(key) >= 4 else key
    return {"set": True, "hint": f"…{tail}"}


class KeyState(BaseModel):
    set: bool
    hint: str


class LlmSettingsOut(BaseModel):
    model: str
    effort: str
    max_tokens: int
    current_provider: str
    # Masked, write-only key state — the secrets themselves are never returned.
    keys: dict[str, KeyState]


class LlmSettingsUpdate(BaseModel):
    model: Optional[str] = None
    effort: Optional[str] = None
    max_tokens: Optional[int] = None
    # A non-empty string sets/replaces the key; omit or send "" to keep current.
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None


class ValidateRequest(BaseModel):
    model: str
    credential: str


class ValidateResponse(BaseModel):
    valid: bool
    message: str


async def _validate_via_litellm(model: str, api_key: str) -> tuple[bool, str]:
    """Run a 5-token completion through litellm to exercise the real auth path."""
    try:
        import litellm
    except ImportError:
        return False, "litellm not installed"

    def _do() -> None:
        litellm.completion(
            model=model,
            messages=[{"role": "user", "content": "ok"}],
            max_tokens=5,
            api_key=api_key or None,
            timeout=15.0,
        )

    try:
        await asyncio.to_thread(_do)
        return True, ""
    except Exception as e:  # noqa: BLE001
        kind = e.__class__.__name__
        if kind == "AuthenticationError":
            return False, f"provider rejected the credential — {e}"
        if kind == "NotFoundError":
            return False, f"model not available with this credential — {e}"
        if kind in ("APIConnectionError", "ConnectError", "ConnectTimeout"):
            return False, f"can't reach the provider — {e}"
        return False, f"{kind}: {e}"


@router.get("", response_model=LlmSettingsOut)
async def get_llm_settings(_admin: UserContext = Depends(require_role("admin"))) -> LlmSettingsOut:
    cfg = await effective_config()
    return LlmSettingsOut(
        model=cfg["model"],
        effort=cfg["effort"],
        max_tokens=cfg["max_tokens"],
        current_provider=_detect_provider(cfg["model"]),
        keys={
            "anthropic": KeyState(**_mask(cfg["anthropic_api_key"])),
            "openai": KeyState(**_mask(cfg["openai_api_key"])),
            "gemini": KeyState(**_mask(cfg["gemini_api_key"])),
        },
    )


@router.post("/validate", response_model=ValidateResponse)
async def validate_credential(
    body: ValidateRequest = Body(...),
    _admin: UserContext = Depends(require_role("admin")),
) -> ValidateResponse:
    cred = body.credential.strip()
    if not cred:
        return ValidateResponse(valid=False, message="credential is empty")
    if _detect_provider(body.model) not in _PROVIDERS:
        return ValidateResponse(
            valid=False, message=f"don't know how to validate model '{body.model}'"
        )
    ok, msg = await _validate_via_litellm(body.model, cred)
    return ValidateResponse(valid=ok, message="" if ok else msg)


@router.put("")
async def update_llm_settings(
    body: LlmSettingsUpdate = Body(...),
    _admin: UserContext = Depends(require_role("admin")),
) -> dict:
    updates: dict[str, str] = {}
    if body.model is not None:
        updates["model"] = body.model.strip()
    if body.effort is not None:
        updates["effort"] = body.effort.strip()
    if body.max_tokens is not None:
        updates["max_tokens"] = str(int(body.max_tokens))
    # Keys: only persist when a non-empty value was typed.
    for field in ("anthropic_api_key", "openai_api_key", "gemini_api_key"):
        val = getattr(body, field)
        if val:
            updates[field] = val.strip()

    if not updates:
        return {"changed": False}

    # Validate a changed credential against the target model before saving, so
    # a bad key fails here with a clear message instead of on the next conversation.
    target_model = updates.get("model") or (await effective_config())["model"]
    for field in ("anthropic_api_key", "openai_api_key", "gemini_api_key"):
        if field in updates:
            ok, msg = await _validate_via_litellm(target_model, updates[field])
            if not ok:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail={"validation_errors": [{"field": field, "message": msg}]},
                )

    await set_overrides(updates)
    return {"changed": True, "updated_keys": sorted(updates.keys())}
