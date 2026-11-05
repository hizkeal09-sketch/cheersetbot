"""Shared keyboards."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton as Btn
from aiogram.types import (
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)


def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [Btn(text="🔍 Discover", callback_data="menu:discover"), Btn(text="💬 Matches", callback_data="menu:matches")],
        [Btn(text="💌 Likes", callback_data="menu:likes"), Btn(text="👤 My profile", callback_data="menu:profile")],
        [Btn(text="⚙️ Settings", callback_data="menu:settings"), Btn(text="👑 Premium", callback_data="menu:premium")],
        [Btn(text="❓ Help & safety", callback_data="menu:help")],
    ]
    if is_admin:
        rows.append([Btn(text="🛡 Admin dashboard", callback_data="adm:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[Btn(text="🏠 Main menu", callback_data="menu:home")]]
    )


def onboarding_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [Btn(text="✅ I'm 18 or older — let's go", callback_data="reg:age_ok")],
            [Btn(text="🔒 Privacy & safety", callback_data="reg:privacy")],
            [Btn(text="❓ Help", callback_data="menu:help")],
        ]
    )


def cancel_keyboard(callback: str = "reg:cancel") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[Btn(text="✖️ Cancel", callback_data=callback)]]
    )


def location_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Share my location", request_location=True)],
            [KeyboardButton(text="⏭ Skip")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_reply_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()
