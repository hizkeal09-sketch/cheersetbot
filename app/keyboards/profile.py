"""Profile and edit-profile keyboards."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton as Btn
from aiogram.types import InlineKeyboardMarkup

from app.constants import INTENTION_LABELS, INTERESTS


def profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [Btn(text="✏️ Edit profile", callback_data="edit:menu")],
            [Btn(text="⚙️ Discovery filters", callback_data="f:menu")],
            [
                Btn(text="⚙️ Settings", callback_data="menu:settings"),
                Btn(text="👑 Premium", callback_data="menu:premium"),
            ],
            [Btn(text="🏠 Main menu", callback_data="menu:home")],
        ]
    )


def edit_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                Btn(text="👤 First name", callback_data="edit:field:first_name"),
                Btn(text="🎂 Date of birth", callback_data="edit:field:birth_date"),
            ],
            [
                Btn(text="📍 City", callback_data="edit:field:city"),
                Btn(text="📝 Bio", callback_data="edit:field:bio"),
            ],
            [
                Btn(text="✨ Interests", callback_data="edit:field:interests"),
                Btn(text="💞 Intentions", callback_data="edit:field:intention"),
            ],
            [Btn(text="📸 Photos", callback_data="edit:field:photos")],
            [
                Btn(text="⬅️ Back to profile", callback_data="menu:profile"),
                Btn(text="🏠 Menu", callback_data="menu:home"),
            ],
        ]
    )


def edit_interests_keyboard(selected: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[Btn]] = []
    row: list[Btn] = []
    for key, label in INTERESTS.items():
        prefix = "✅ " if key in selected else ""
        row.append(Btn(text=prefix + label, callback_data=f"edit:int:{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([Btn(text="✅ Save interests", callback_data="edit:int_done")])
    rows.append([Btn(text="⬅️ Back", callback_data="edit:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def edit_intentions_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [Btn(text=label, callback_data=f"edit:goal:{value.value}")]
        for value, label in INTENTION_LABELS.items()
    ]
    rows.append([Btn(text="⬅️ Back", callback_data="edit:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def edit_photos_keyboard(has_photo: bool) -> InlineKeyboardMarkup:
    rows: list[list[Btn]] = []
    if has_photo:
        rows.append([Btn(text="✅ Save photos", callback_data="edit:photos_done")])
    rows.append([Btn(text="⬅️ Cancel", callback_data="edit:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
