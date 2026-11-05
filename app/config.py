"""Application configuration loaded from environment variables / .env."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.utils.urls import normalize_database_url


class Settings(BaseSettings):
    """Typed application settings.

    Secrets are never hardcoded; they are read from the environment or a
    local ``.env`` file that is excluded from version control.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    bot_token: SecretStr = SecretStr("")
    database_url: str = "sqlite+aiosqlite:///./cheers.db"

    admin_ids: str = ""
    support_contact: str = "@cheers_support"

    environment: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"
    log_file: str | None = "logs/cheers.log"
    app_timezone: str = "Africa/Addis_Ababa"
    drop_pending_updates: bool = False
    auto_create_tables: bool = False

    # Serverless / webhook deployment (Vercel). Polling is used locally and in
    # Docker; a webhook plus persistent FSM storage is required on Vercel.
    serverless: bool = False
    vercel: bool = False
    webhook_path: str = "/api/telegram"
    webhook_url: str = ""
    webhook_secret: SecretStr = SecretStr("")
    setup_token: SecretStr = SecretStr("")
    cron_secret: SecretStr = SecretStr("")
    broadcast_inline_seconds: float = Field(default=20.0, ge=1.0, le=50.0)

    premium_enabled: bool = False
    free_daily_discoveries: int = Field(default=30, ge=1, le=10_000)
    premium_daily_discoveries: int = Field(default=300, ge=1, le=100_000)

    allow_contact_sharing: bool = False

    rate_limit_events: int = Field(default=12, ge=1, le=1_000)
    rate_limit_window_seconds: int = Field(default=10, ge=1, le=3_600)

    @field_validator("log_level")
    @classmethod
    def _valid_log_level(cls, value: str) -> str:
        value = value.upper().strip()
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
        if value not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(allowed)}")
        return value

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @field_validator("webhook_url")
    @classmethod
    def _normalize_webhook_url(cls, value: str) -> str:
        return value.strip().rstrip("/")

    @field_validator("webhook_path")
    @classmethod
    def _normalize_webhook_path(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return "/api/telegram"
        return value if value.startswith("/") else f"/{value}"

    @property
    def admin_id_list(self) -> set[int]:
        """Return configured admin Telegram IDs, ignoring malformed entries."""
        result: set[int] = set()
        for raw in re.split(r"[,\s]+", self.admin_ids.strip()):
            if not raw:
                continue
            try:
                result.add(int(raw))
            except ValueError:
                continue
        return result

    @property
    def is_serverless(self) -> bool:
        """True when running inside an ephemeral serverless function."""
        return self.serverless or self.vercel

    @property
    def webhook_endpoint(self) -> str:
        return f"{self.webhook_url}{self.webhook_path}"

    def validate_webhook(self) -> None:
        """Validate the webhook configuration used by the Vercel entrypoint."""
        if not self.webhook_url:
            raise RuntimeError(
                "WEBHOOK_URL is not set. Use the public https URL of the deployment, "
                "for example https://cheersetbot.vercel.app"
            )
        if not self.webhook_url.startswith("https://"):
            raise RuntimeError("WEBHOOK_URL must start with https:// so Telegram accepts it.")
        secret = self.webhook_secret.get_secret_value().strip()
        if not secret:
            raise RuntimeError(
                "WEBHOOK_SECRET is not set. Generate a random value with "
                "characters A-Z, a-z, 0-9, _ or -."
            )
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", secret):
            raise RuntimeError(
                "WEBHOOK_SECRET may only contain A-Z, a-z, 0-9, _ and - "
                "(Telegram's secret token requirements)."
            )

    def validate_runtime(self) -> None:
        """Fail fast with a helpful message when required config is missing."""
        token = self.bot_token.get_secret_value().strip()
        if not token:
            raise RuntimeError(
                "BOT_TOKEN is not set. Copy .env.example to .env and add the token "
                "you received from @BotFather."
            )
        if "REPLACE_WITH" in token.upper():
            raise RuntimeError(
                "BOT_TOKEN still contains the placeholder value. Replace it in .env "
                "with the real token from @BotFather."
            )
        if ":" not in token:
            raise RuntimeError("BOT_TOKEN does not look like a valid Telegram bot token.")
        if not self.database_url.strip():
            raise RuntimeError("DATABASE_URL is empty.")
        if self.environment == "production" and not self.admin_id_list:
            raise RuntimeError("ADMIN_IDS must be set in production.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
