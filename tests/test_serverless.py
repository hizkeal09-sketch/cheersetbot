"""Serverless and Neon deployment checks."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from app.config import Settings
from app.utils.urls import normalize_database_url


def test_neon_url_is_normalized_for_asyncpg() -> None:
    source = (
        "postgresql://cheers:secret@ep-foo.us-east-1.aws.neon.tech/cheers"
        "?sslmode=require&channel_binding=require"
    )

    assert normalize_database_url(source) == (
        "postgresql+asyncpg://cheers:secret@ep-foo.us-east-1.aws.neon.tech/cheers"
        "?ssl=require"
    )


def test_vercel_webhook_settings_are_validated() -> None:
    settings = Settings(
        _env_file=None,
        bot_token="123456:TEST_TOKEN",
        database_url="postgresql://cheers:secret@ep-foo.us-east-1.aws.neon.tech/cheers?sslmode=require",
        admin_ids="1",
        environment="production",
        vercel=True,
        webhook_url="https://cheersetbot.vercel.app",
        webhook_secret="abc_123-XYZ",
        log_file=None,
    )
    settings.validate_webhook()


def test_vercel_app_entrypoint_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "vercel_app.py").exists()

    spec = importlib.util.spec_from_file_location("vercel_app", root / "vercel_app.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert hasattr(module, "app")
