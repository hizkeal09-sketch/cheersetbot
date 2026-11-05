"""Cheers Dating application entrypoint."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError

from app.bot import create_dispatcher
from app.commands import BOT_COMMANDS
from app.config import Settings, get_settings
from app.database.session import (
    create_engine,
    create_session_factory,
    init_models,
    verify_schema,
)
from app.logging_config import setup_logging

logger = logging.getLogger(__name__)


async def run(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    settings.validate_runtime()
    setup_logging(settings)
    logger.info("Starting Cheers Dating bot (env=%s)", settings.environment)

    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    try:
        if settings.auto_create_tables:
            logger.warning("AUTO_CREATE_TABLES is enabled; creating schema without migrations")
            await init_models(engine)
        elif not await verify_schema(engine):
            raise RuntimeError(
                "Database schema is missing. Run 'alembic upgrade head' before starting the bot."
            )

        bot = Bot(
            token=settings.bot_token.get_secret_value(),
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML,
                link_preview_is_disabled=True,
            ),
        )
        try:
            me = await bot.get_me()
            logger.info("Connected as @%s", me.username)
            try:
                await bot.set_my_commands(BOT_COMMANDS)
            except TelegramAPIError:
                logger.warning("Could not publish bot commands", exc_info=True)

            dp = create_dispatcher(settings, session_factory)
            await bot.delete_webhook(drop_pending_updates=settings.drop_pending_updates)
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                handle_signals=True,
            )
        finally:
            await bot.session.close()
    finally:
        await engine.dispose()
        logger.info("Cheers Dating stopped")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
