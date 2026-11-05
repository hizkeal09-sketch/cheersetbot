"""Error handling."""

from __future__ import annotations

import logging

from aiogram.exceptions import TelegramAPIError
from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)


async def error_handler(event: ErrorEvent) -> None:
    logger.exception("Unhandled update error: %s", event.exception, exc_info=event.exception)

    update = event.update
    try:
        if update.callback_query:
            await update.callback_query.answer(
                "⚠️ Something went wrong. Please try again.", show_alert=True
            )
        elif update.message:
            await update.message.answer("⚠️ Something went wrong. Please try again in a moment.")
    except (TelegramAPIError, AttributeError):
        pass
