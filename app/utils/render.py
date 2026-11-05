"""Presentation helpers for profile cards and safe message edits."""

from __future__ import annotations

import contextlib
import html
import logging
from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from app.constants import (
    GENDER_LABELS_SHORT,
    INTENTION_LABELS,
    INTERESTS,
    PREFERENCE_LABELS_SHORT,
)
from app.database.models import User
from app.utils.time import calculate_age

logger = logging.getLogger(__name__)


def profile_card_text(user: User, *, include_header: str | None = None) -> str:
    """Build an HTML profile card without exposing usernames or Telegram IDs."""
    name = html.escape(user.first_name)
    age = calculate_age(user.birth_date) if user.birth_date else "—"
    verified = " ✅" if user.is_verified else ""
    premium = " 👑" if user.is_premium else ""

    lines: list[str] = []
    if include_header:
        lines.append(include_header)
        lines.append("")
    lines.append(f"<b>{name}{verified}{premium}, {age}</b>")

    location_parts = []
    if user.city:
        location_parts.append(f"📍 {html.escape(user.city)}, Ethiopia")
    if user.gender:
        location_parts.append(GENDER_LABELS_SHORT.get(user.gender, ""))
    if user.interested_in:
        location_parts.append(f"looking for {PREFERENCE_LABELS_SHORT.get(user.interested_in, '')}")
    if location_parts:
        lines.append(" · ".join(part for part in location_parts if part))

    if user.intention:
        lines.append(f"💞 {INTENTION_LABELS.get(user.intention, '')}")

    if user.bio:
        lines.append("")
        lines.append(f"<i>{html.escape(user.bio)}</i>")

    labels = [INTERESTS[item] for item in (user.interests or []) if item in INTERESTS]
    if labels:
        lines.append("")
        lines.append("✨ " + " · ".join(labels))

    return "\n".join(lines)


def profile_summary(user: User) -> str:
    """Short one-line summary used in lists."""
    age = calculate_age(user.birth_date) if user.birth_date else "—"
    city = f" · 📍 {html.escape(user.city)}" if user.city else ""
    badge = " 👑" if user.is_premium else ""
    return f"<b>{html.escape(user.first_name)}{badge}, {age}</b>{city}"


async def send_profile_card(
    bot: Bot,
    chat_id: int,
    user: User,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    header: str | None = None,
    footer: str | None = None,
) -> Message:
    text = profile_card_text(user, include_header=header)
    if footer:
        text = f"{text}\n\n{footer}"

    # Telegram caption limit is 1024 characters. Cards are designed to fit,
    # but trim as a final guard without splitting an HTML entity.
    if len(text) > 1020:
        text = text[:1000].rsplit(" ", 1)[0] + "…"

    photo_id = user.photos[0].file_id if user.photos else None
    if photo_id:
        try:
            return await bot.send_photo(
                chat_id=chat_id,
                photo=photo_id,
                caption=text,
                reply_markup=reply_markup,
            )
        except TelegramBadRequest as exc:
            logger.warning("Could not send profile photo (%s); falling back to text", exc)
    return await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)


async def safe_delete(message: Message | None) -> None:
    if message is None:
        return
    with contextlib.suppress(TelegramBadRequest):
        await message.delete()


async def safe_edit(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Edit the callback message, falling back to delete + send when needed."""
    message = callback.message
    if not isinstance(message, Message):
        if callback.bot:
            await callback.bot.send_message(callback.from_user.id, text, reply_markup=reply_markup)
        return
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return
        await safe_delete(message)
        try:
            await message.answer(text, reply_markup=reply_markup)
        except TelegramBadRequest:
            logger.exception("Failed to send replacement UI message")


async def answer_callback(callback: CallbackQuery, text: str | None = None, alert: bool = False) -> None:
    with contextlib.suppress(TelegramBadRequest):
        await callback.answer(text or "", show_alert=alert)


def deep_get(data: dict[str, Any], key: str, default: Any = None) -> Any:
    return data.get(key, default)
