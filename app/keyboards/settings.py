"""Settings keyboards."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton as Btn
from aiogram.types import InlineKeyboardMarkup

from app.database.models import User


def settings_keyboard(user: User) -> InlineKeyboardMarkup:
    pause_button = (
        Btn(text="▶️ Resume profile", callback_data="set:resume")
        if user.profile_paused
        else Btn(text="⏸ Pause profile", callback_data="set:pause")
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                Btn(text="👤 My profile", callback_data="menu:profile"),
                Btn(text="⚙️ Filters", callback_data="f:menu"),
            ],
            [pause_button],
            [
                Btn(text="🚫 Blocked users", callback_data="set:blocked"),
                Btn(text="🔒 Privacy", callback_data="set:privacy"),
            ],
            [
                Btn(text="👑 Premium", callback_data="menu:premium"),
                Btn(text="🌐 Language: English", callback_data="set:language"),
            ],
            [Btn(text="🗑 Delete account", callback_data="set:delete")],
            [Btn(text="🏠 Main menu", callback_data="menu:home")],
        ]
    )


def privacy_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [Btn(text="⬅️ Back to settings", callback_data="set:back")],
            [Btn(text="🏠 Main menu", callback_data="menu:home")],
        ]
    )


def blocked_list_keyboard(users: list[User]) -> InlineKeyboardMarkup:
    rows: list[list[Btn]] = []
    for user in users:
        rows.append(
            [Btn(text=f"🔓 Unblock {user.first_name[:24]}", callback_data=f"set:unblock:{user.id}")]
        )
    rows.append([Btn(text="⬅️ Back to settings", callback_data="set:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def delete_warning_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [Btn(text="🗑 Delete my account permanently", callback_data="set:delete_confirm")],
            [Btn(text="✖️ Keep my account", callback_data="set:back")],
        ]
    )


def delete_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[Btn(text="✖️ Cancel deletion", callback_data="set:delete_cancel")]]
    )
