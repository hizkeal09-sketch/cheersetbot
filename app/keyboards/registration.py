"""Registration keyboards."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton as Btn
from aiogram.types import InlineKeyboardMarkup

from app.constants import CITIES, GENDER_LABELS, INTENTION_LABELS, INTERESTS, PREFERENCE_LABELS


def _chunks(items: list[tuple[str, str]], per_row: int = 2) -> list[list[Btn]]:
    rows: list[list[Btn]] = []
    for index in range(0, len(items), per_row):
        rows.append([Btn(text=label, callback_data=cb) for label, cb in items[index : index + per_row]])
    return rows


def gender_keyboard() -> InlineKeyboardMarkup:
    rows = _chunks(
        [(label, f"reg:gender:{gender.value}") for gender, label in GENDER_LABELS.items()]
    )
    rows.append([Btn(text="✖️ Cancel", callback_data="reg:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def preference_keyboard() -> InlineKeyboardMarkup:
    rows = _chunks(
        [(label, f"reg:pref:{pref.value}") for pref, label in PREFERENCE_LABELS.items()]
    )
    rows.append([Btn(text="✖️ Cancel", callback_data="reg:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def city_keyboard() -> InlineKeyboardMarkup:
    rows = _chunks(
        [(city, f"reg:city:{index}") for index, city in enumerate(CITIES)]
    )
    rows.append([Btn(text="🌍 Other city", callback_data="reg:city:other")])
    rows.append([Btn(text="✖️ Cancel", callback_data="reg:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def interests_keyboard(selected: list[str]) -> InlineKeyboardMarkup:
    items = []
    for key, label in INTERESTS.items():
        prefix = "✅ " if key in selected else ""
        items.append((prefix + label, f"reg:int:{key}"))
    rows = _chunks(items)
    rows.append([Btn(text="✅ Done", callback_data="reg:int_done")])
    rows.append([Btn(text="✖️ Cancel", callback_data="reg:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def intention_keyboard() -> InlineKeyboardMarkup:
    rows = _chunks(
        [(label, f"reg:goal:{intention.value}") for intention, label in INTENTION_LABELS.items()],
        per_row=1,
    )
    rows.append([Btn(text="✖️ Cancel", callback_data="reg:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def photos_keyboard(has_photo: bool) -> InlineKeyboardMarkup:
    rows: list[list[Btn]] = []
    if has_photo:
        rows.append([Btn(text="✅ Continue", callback_data="reg:photo_done")])
        rows.append([Btn(text="🗑 Remove last photo", callback_data="reg:photo_remove")])
    rows.append([Btn(text="✖️ Cancel", callback_data="reg:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [Btn(text="🎉 Create my profile", callback_data="reg:confirm")],
            [Btn(text="🔄 Start over", callback_data="reg:restart")],
            [Btn(text="✖️ Cancel", callback_data="reg:cancel")],
        ]
    )
