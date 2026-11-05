"""Premium keyboards."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton as Btn
from aiogram.types import InlineKeyboardMarkup


def premium_keyboard(active: bool, enabled: bool) -> InlineKeyboardMarkup:
    rows: list[list[Btn]] = []
    if enabled and not active:
        rows.append([Btn(text="🔔 Notify me when payments launch", callback_data="prem:soon")])
    rows.append([Btn(text="🏠 Main menu", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
