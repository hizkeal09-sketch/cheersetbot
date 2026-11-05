"""Discovery, filter, and likes keyboards."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton as Btn
from aiogram.types import InlineKeyboardMarkup

from app.constants import AGE_PRESETS, CITIES, GENDER_LABELS_SHORT
from app.database.models import UserFilter


def discovery_card_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                Btn(text="❤️ Like", callback_data=f"like:{user_id}"),
                Btn(text="👎 Pass", callback_data=f"pass:{user_id}"),
            ],
            [
                Btn(text="🚩 Report", callback_data=f"report:{user_id}"),
                Btn(text="🚫 Block", callback_data=f"block:{user_id}"),
            ],
            [
                Btn(text="⚙️ Filters", callback_data="f:menu"),
                Btn(text="🏠 Menu", callback_data="menu:home"),
            ],
        ]
    )


def filters_keyboard(flt: UserFilter) -> InlineKeyboardMarkup:
    rows: list[list[Btn]] = []
    for index, (min_age, max_age, label) in enumerate(AGE_PRESETS):
        active = flt.min_age == min_age and flt.max_age == max_age
        rows.append(
            [
                Btn(
                    text=("✅ " if active else "") + f"{label}",
                    callback_data=f"f:age:{index}",
                )
            ]
        )
    # Two age presets per row keeps the UI compact.
    compact: list[list[Btn]] = []
    for index in range(0, len(rows), 2):
        compact.append([row[0] for row in rows[index : index + 2]])
    compact.append([Btn(text="🌐 Any age (18–99)", callback_data="f:age:any")])

    gender_row = [Btn(text="🌐 Any", callback_data="f:gender:any")]
    for gender, label in GENDER_LABELS_SHORT.items():
        gender_row.append(Btn(text=label, callback_data=f"f:gender:{gender.value}"))
    compact.append(gender_row[:3])
    if len(gender_row) > 3:
        compact.append(gender_row[3:])

    city_text = f"📍 City: {flt.city}" if flt.city else "📍 City: Any"
    active_text = "✅ Active recently" if flt.active_recently_only else "🕒 Active recently"
    compact.append(
        [
            Btn(text=city_text, callback_data="f:city_menu"),
            Btn(text=active_text, callback_data="f:active"),
        ]
    )
    compact.append(
        [
            Btn(text="♻️ Reset", callback_data="f:reset"),
            Btn(text="✅ Done", callback_data="f:done"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=compact)


def filter_cities_keyboard() -> InlineKeyboardMarkup:
    rows: list[list[Btn]] = []
    row: list[Btn] = []
    for index, city in enumerate(CITIES):
        row.append(Btn(text=city, callback_data=f"f:city:{index}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([Btn(text="🌐 Any city", callback_data="f:city:any")])
    rows.append([Btn(text="⬅️ Back to filters", callback_data="f:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def likes_summary_keyboard(page: int, has_next: bool) -> InlineKeyboardMarkup:
    rows: list[list[Btn]] = []
    nav: list[Btn] = []
    if page > 0:
        nav.append(Btn(text="⬅️ Previous", callback_data=f"likes:page:{page - 1}"))
    if has_next:
        nav.append(Btn(text="Next ➡️", callback_data=f"likes:page:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([Btn(text="🏠 Menu", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def likes_card_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [Btn(text="❤️ Like back", callback_data=f"likes:back:{user_id}")],
            [
                Btn(text="🚩 Report", callback_data=f"report:{user_id}"),
                Btn(text="🚫 Block", callback_data=f"block:{user_id}"),
            ],
        ]
    )
