"""Keep unregistered users inside the onboarding flow."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config import Settings

logger = logging.getLogger(__name__)

ALLOWED_COMMANDS = {"/start", "/help", "/cancel", "/privacy"}
ALLOWED_CALLBACK_PREFIXES = ("reg:", "menu:help", "menu:home")


class RegistrationGateMiddleware(BaseMiddleware):
    """Prevent half-registered accounts from using dating features."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("user")
        tg_user = data.get("event_from_user")
        if user is None or tg_user is None:
            return await handler(event, data)
        if user.is_registered or tg_user.id in self.settings.admin_id_list:
            return await handler(event, data)

        state = data.get("state")
        state_active = state is not None and await state.get_state() is not None

        if isinstance(event, Message):
            text = (event.text or "").strip()
            if text.startswith("/"):
                command = text.split(maxsplit=1)[0].split("@")[0].lower()
                if command in ALLOWED_COMMANDS:
                    return await handler(event, data)
            elif state_active:
                # Multi-step registration input (name, bio, photos, location).
                return await handler(event, data)
        if isinstance(event, CallbackQuery) and (event.data or "").startswith(
            ALLOWED_CALLBACK_PREFIXES
        ):
            return await handler(event, data)

        text = (
            "👋 <b>Welcome to Cheers Dating!</b>\n\n"
            "Let's finish setting up your profile first, then you can start meeting people.\n\n"
            "Tap /start to continue."
        )
        try:
            if isinstance(event, CallbackQuery):
                await event.answer("Please finish your profile first. Tap /start.", show_alert=True)
            elif isinstance(event, Message):
                await event.answer(text)
        except TelegramBadRequest:
            pass
        return None
