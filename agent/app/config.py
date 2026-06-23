from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- LLM (litellm) ---
    # `model` is any litellm model string, e.g.:
    #   anthropic/claude-opus-4-8   (default)
    #   openai/gpt-4o
    #   gemini/gemini-1.5-pro
    # The matching provider key (ANTHROPIC_API_KEY / OPENAI_API_KEY / ...) must be in the env.
    # NOTE: an admin can override the model/effort/keys at runtime via the LLM
    # settings modal (stored in the DB) — see config_store.effective_config.
    model: str = "anthropic/claude-opus-4-8"
    max_tokens: int = 8000
    temperature: float = 0.2
    # Reasoning effort for models that support it (low|medium|high). Dropped automatically
    # for models that don't, since litellm.drop_params is enabled.
    reasoning_effort: str = "medium"
    max_iterations: int = 16

    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Auth / DB ---
    # SQLite file holding users, sessions, per-user usage, and runtime LLM
    # config. In Docker this lives on a named volume so it survives redeploys.
    db_path: str = "/data/app.db"
    # First-admin bootstrap. If set, an admin with these credentials is
    # created (or its password/role reconciled) on every startup, guaranteeing
    # a login path. Read from ADMIN_USERNAME / ADMIN_PASSWORD.
    admin_username: str = Field(default="", validation_alias="ADMIN_USERNAME")
    admin_password: str = Field(default="", validation_alias="ADMIN_PASSWORD")
    # Set the session cookie's Secure flag. Leave false when reaching the app
    # over plain http (e.g. http://host:8300); set true when it's only served
    # behind TLS so the cookie never travels in the clear.
    cookie_secure: bool = False
    # Simple in-process login throttle.
    login_max_failures: int = 8
    login_window_seconds: int = 900

    # --- Telegram bot (optional chat UI) ---
    # Create a bot with @BotFather and paste its token to enable a Telegram chat
    # front-end for the agent. The bot long-polls (no public webhook needed); a
    # chat links to an account via a one-time /link <code>. Leave unset to disable.
    telegram_bot_token: str = Field(default="", validation_alias="TELEGRAM_BOT_TOKEN")
    telegram_poll_timeout: int = 25  # long-poll getUpdates wait (seconds)
    telegram_link_code_ttl_min: int = 15

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token)


settings = Settings()  # type: ignore[call-arg]
