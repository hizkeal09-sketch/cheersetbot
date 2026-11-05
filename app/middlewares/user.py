"""Loads (or creates) the user row and blocks banned accounts."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config import Settings
from app.services.users import UserService

logger = logging.getLogger(__name__)


class UserMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._last_ban_notice: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        session = data.get("session")
        if tg_user is None or session is None:
            return await handler(event, data)

        user = await UserService.get_or_create(session, tg_user)
        await UserService.touch(session, user)
        data["user"] = user

        if user.is_banned and tg_user.id not in self.settings.admin_id_list:
            now = time.monotonic()
            last = self._last_ban_notice.get(user.id, 0.0)
            if now - last > 60:
                self._last_ban_notice[user.id] = now
                reason = f"\nReason: {user.ban_reason}" if user.ban_reason else ""
                text = (
                    "🚫 <b>Your account is suspended.</b>"
                    f"{reason}\n\nIf you believe this is a mistake, contact "
                    f"{self.settings.support_contact}."
                )
                try:
                    if isinstance(event, CallbackQuery):
                        await event.answer("Your account is suspended. Contact support.", show_alert=True)
                    elif isinstance(event, Message):
                        await event.answer(text)
                except TelegramBadRequest:
                    pass
            return None

        return await handler(event, data)
