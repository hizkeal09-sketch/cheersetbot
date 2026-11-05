"""Matches and chat keyboards."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton as Btn
from aiogram.types import InlineKeyboardMarkup

from app.database.models import Match, User
from app.utils.time import calculate_age


def _name(user: User) -> str:
    age = calculate_age(user.birth_date) if user.birth_date else ""
    label = f"{user.first_name}, {age}" if age else user.first_name
    return label[:28]


def matches_keyboard(
    matches: list[Match], user: User, page: int, has_next: bool
) -> InlineKeyboardMarkup:
    rows: list[list[Btn]] = []
    for match in matches:
        partner = match.other_user(user.id)
        rows.append(
            [
                Btn(text=f"👤 {_name(partner)}", callback_data=f"match:open:{match.id}"),
                Btn(text="💬 Chat", callback_data=f"match:chat:{match.id}"),
            ]
        )
    nav: list[Btn] = []
    if page > 0:
        nav.append(Btn(text="⬅️ Previous", callback_data=f"match:page:{page - 1}"))
    if has_next:
        nav.append(Btn(text="Next ➡️", callback_data=f"match:page:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([Btn(text="🏠 Main menu", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def match_actions_keyboard(match_id: int, partner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [Btn(text="💬 Open chat", callback_data=f"match:chat:{match_id}")],
            [
                Btn(text="🚩 Report", callback_data=f"report:{partner_id}"),
                Btn(text="🚫 Block", callback_data=f"block:{partner_id}"),
            ],
            [Btn(text="💔 Unmatch", callback_data=f"match:unmatch:{match_id}")],
            [Btn(text="⬅️ All matches", callback_data="match:list")],
        ]
    )


def unmatch_confirm_keyboard(match_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                Btn(text="💔 Yes, unmatch", callback_data=f"match:unmatch_yes:{match_id}"),
                Btn(text="⬅️ Keep match", callback_data=f"match:open:{match_id}"),
            ]
        ]
    )


def chat_keyboard(match_id: int, partner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                Btn(text="🚩 Report", callback_data=f"report:{partner_id}"),
                Btn(text="🚫 Block", callback_data=f"block:{partner_id}"),
            ],
            [Btn(text="✖️ End chat", callback_data="chat:end")],
        ]
    )


def chat_reply_keyboard(match_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[Btn(text="↩️ Reply", callback_data=f"chat:open:{match_id}")]]
    )
