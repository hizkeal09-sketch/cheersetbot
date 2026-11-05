"""Per-user anti-spam middleware."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config import Settings
from app.utils.rate_limit import SlidingWindowLimiter


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.limiter = SlidingWindowLimiter(
            settings.rate_limit_events, settings.rate_limit_window_seconds
        )

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is None or tg_user.id in self.settings.admin_id_list:
            return await handler(event, data)

        if not self.limiter.is_allowed(tg_user.id):
            try:
                if isinstance(event, (CallbackQuery, Message)):
                    await event.answer("⏳ Slow down a little — try again in a few seconds.")
            except TelegramBadRequest:
                pass
            return None

        return await handler(event, data)
