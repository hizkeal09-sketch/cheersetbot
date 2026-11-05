"""Report, block, and safety keyboards."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton as Btn
from aiogram.types import InlineKeyboardMarkup

from app.constants import REPORT_REASON_LABELS
from app.database.models import User
from app.utils.time import calculate_age


def report_reasons_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [Btn(text=label, callback_data=f"rep:reason:{reason.value}")]
        for reason, label in REPORT_REASON_LABELS.items()
    ]
    rows.append([Btn(text="✖️ Cancel", callback_data="rep:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def report_details_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [Btn(text="⏭ Skip details", callback_data="rep:skip")],
            [Btn(text="✖️ Cancel", callback_data="rep:cancel")],
        ]
    )


def report_submitted_keyboard(target_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [Btn(text="🚫 Block this person", callback_data=f"block:{target_id}")],
            [Btn(text="🏠 Main menu", callback_data="menu:home")],
        ]
    )


def block_confirm_keyboard(target_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                Btn(text="🚫 Yes, block", callback_data=f"block:yes:{target_id}"),
                Btn(text="✖️ Cancel", callback_data="block:no"),
            ]
        ]
    )


def user_picker_keyboard(users: list[User], prefix: str) -> InlineKeyboardMarkup:
    rows: list[list[Btn]] = []
    for user in users:
        age = calculate_age(user.birth_date) if user.birth_date else ""
        label = f"{user.first_name}, {age}" if age else user.first_name
        rows.append([Btn(text=label[:30], callback_data=f"{prefix}:{user.id}")])
    rows.append([Btn(text="🏠 Main menu", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def block_noop_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[Btn(text="🏠 Main menu", callback_data="menu:home")]]
    )
