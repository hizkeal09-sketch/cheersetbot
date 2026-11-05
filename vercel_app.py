"""Vercel ASGI entrypoint for the Cheers Dating Telegram bot.

Vercel functions are stateless, so the bot runs in webhook mode instead of long
polling and keeps its FSM state in PostgreSQL/Neon. Telegram posts every update
to ``POST /api/telegram``; the shared secret in the
``X-Telegram-Bot-Api-Secret-Token`` header authenticates the request.

The dispatcher, bot and engine are created once per function instance (module
scope) and reused across requests. This avoids re-attaching aiogram routers to
a fresh dispatcher on every invocation, which aiogram forbids.
"""

from __future__ import annotations

import hmac
import logging
from typing import Any

import sqlalchemy as sa
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.bot import create_dispatcher
from app.commands import BOT_COMMANDS
from app.config import get_settings
from app.database.fsm_storage import DatabaseStorage
from app.database.session import (
    create_engine,
    create_session_factory,
    init_models,
    verify_schema,
)
from app.logging_config import setup_logging
from app.services.broadcast import process_pending_broadcasts

logger = logging.getLogger(__name__)


def _constant_time_equals(left: str, right: str) -> bool:
    if not left or not right:
        return False
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


settings = get_settings()
setup_logging(settings)

engine = create_engine(settings.database_url, serverless=settings.is_serverless)
session_factory = create_session_factory(engine)
storage = DatabaseStorage(session_factory)

bot = Bot(
    token=settings.bot_token.get_secret_value(),
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML,
        link_preview_is_disabled=True,
    ),
)
dispatcher = create_dispatcher(settings, session_factory, storage=storage)


async def ensure_schema() -> None:
    """Verify (or create) the database schema once per warm instance."""
    if settings.auto_create_tables:
        logger.warning("AUTO_CREATE_TABLES is enabled; creating schema without migrations")
        await init_models(engine)
    elif not await verify_schema(engine):
        raise HTTPException(
            status_code=503,
            detail="Database schema is missing. Run 'alembic upgrade head' against Neon.",
        )
    try:
        await bot.set_my_commands(BOT_COMMANDS)
    except Exception:  # pragma: no cover - Telegram may be temporarily unavailable
        logger.warning("Could not publish bot commands", exc_info=True)


app = FastAPI(
    title="Cheers Dating",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "service": "cheers-dating",
        "status": "ok",
        "environment": settings.environment,
    }


@app.get("/api/health")
async def health() -> JSONResponse:
    """Liveness probe with a real database round-trip."""
    try:
        async with engine.connect() as connection:
            await connection.execute(sa.text("SELECT 1"))
    except Exception:
        logger.exception("Database health check failed")
        return JSONResponse(status_code=503, content={"status": "error", "database": False})
    return JSONResponse(content={"status": "ok", "database": True})


@app.post("/api/telegram")
async def telegram_webhook(request: Request) -> JSONResponse:
    """Receive Telegram updates."""
    if not settings.webhook_secret.get_secret_value().strip():
        return JSONResponse(status_code=503, content={"ok": False, "error": "webhook secret not configured"})

    expected = settings.webhook_secret.get_secret_value().strip()
    provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not _constant_time_equals(provided, expected):
        logger.warning("Rejected webhook request with an invalid secret")
        return JSONResponse(status_code=401, content={"ok": False, "error": "unauthorized"})

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"ok": False, "error": "invalid json"})

    try:
        update = Update.model_validate(payload)
    except Exception:
        logger.warning("Received an update that does not match the Telegram schema")
        return JSONResponse(status_code=200, content={"ok": True})

    try:
        await ensure_schema()
    except HTTPException as exc:
        logger.error("Webhook rejected: %s", exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": exc.detail})

    try:
        await dispatcher.feed_update(bot, update)
    except Exception:
        # Never answer with a 5xx: Telegram would retry the update and the bot
        # could act twice (duplicate likes, duplicate messages, ...).
        logger.exception("Unhandled error while processing update %s", update.update_id)
    return JSONResponse(status_code=200, content={"ok": True})


@app.post("/api/setup")
async def setup_webhook(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """Register the webhook with Telegram. Requires ``SETUP_TOKEN``."""
    expected_token = settings.setup_token.get_secret_value().strip()
    if not expected_token:
        raise HTTPException(status_code=404, detail="Not found")

    if not authorization or not _constant_time_equals(authorization, f"Bearer {expected_token}"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    await ensure_schema()
    await bot.set_webhook(
        url=settings.webhook_endpoint,
        secret_token=settings.webhook_secret.get_secret_value().strip(),
        allowed_updates=dispatcher.resolve_used_update_types(),
        drop_pending_updates=settings.drop_pending_updates,
    )
    info = await bot.get_webhook_info()
    return {
        "ok": True,
        "url": info.url,
        "pending_update_count": info.pending_update_count,
        "allowed_updates": sorted(dispatcher.resolve_used_update_types()),
    }


@app.post("/api/cron/broadcast")
async def cron_broadcast(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """Continue paused broadcasts. Requires ``CRON_SECRET``."""
    expected_token = settings.cron_secret.get_secret_value().strip()
    if not expected_token:
        raise HTTPException(status_code=404, detail="Not found")

    if not authorization or not _constant_time_equals(authorization, f"Bearer {expected_token}"):
        raise HTTPException(status_code=401, detail="Unauthorized")

    await ensure_schema()
    results = await process_pending_broadcasts(bot, session_factory, max_seconds=50.0)
    return {
        "ok": True,
        "processed": len(results),
        "results": [
            {
                "job_id": item.job_id,
                "sent": item.sent,
                "failed": item.failed,
                "finished": item.finished,
                "status": item.status,
            }
            for item in results
        ],
    }
