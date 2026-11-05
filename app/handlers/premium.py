"""Premium information and subscription management."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.config import Settings
from app.database.models import User
from app.keyboards.premium import premium_keyboard
from app.services.premium import has_premium, premium_until_text
from app.utils.render import answer_callback, safe_edit

router = Router(name="premium")


def _premium_text(user: User, settings: Settings) -> str:
    active = has_premium(user, settings) and settings.premium_enabled
    lines = ["👑 <b>Cheers Premium</b>\n"]

    if not settings.premium_enabled:
        lines.append(
            "🎉 <b>Launch offer: Premium is free for everyone right now.</b>\n\n"
            "Payments aren't live yet, so all Premium features are unlocked at no cost."
        )
    elif active:
        lines.append(f"✅ <b>You're a Premium member!</b>\nExpires: {premium_until_text(user)}\n")
    else:
        lines.append(
            "Stand out, see who's interested, and meet more people every day.\n"
        )

    lines.append(
        "\n<b>Premium features</b>\n"
        f"🔍 Up to <b>{settings.premium_daily_discoveries}</b> profile discoveries per day "
        f"(free: {settings.free_daily_discoveries})\n"
        "💌 See exactly who liked you\n"
        "⚙️ Advanced filters, including recently active people\n"
        "✨ Priority placement in other people's discovery\n"
        "🛡 Priority support"
    )

    if settings.premium_enabled and not active:
        lines.append(
            f"\n💳 <b>Subscription</b>\nPayments are coming soon. "
            f"Contact {settings.support_contact} if you'd like early access."
        )
    elif active and settings.premium_enabled:
        lines.append("\nManage your plan by contacting support. Subscriptions are non-refundable.")
    else:
        lines.append("\nNo payment is required during launch. Enjoy! 🍻")

    return "\n".join(lines)


@router.message(Command("premium"))
async def cmd_premium(
    message: Message, state: FSMContext, user: User, settings: Settings
) -> None:
    await state.clear()
    await message.answer(
        _premium_text(user, settings),
        reply_markup=premium_keyboard(has_premium(user, settings), settings.premium_enabled),
    )


@router.callback_query(F.data == "menu:premium")
async def cb_premium(
    callback: CallbackQuery, state: FSMContext, user: User, settings: Settings
) -> None:
    await state.clear()
    await answer_callback(callback)
    await safe_edit(
        callback,
        _premium_text(user, settings),
        premium_keyboard(has_premium(user, settings), settings.premium_enabled),
    )


@router.callback_query(F.data == "prem:soon")
async def cb_premium_soon(callback: CallbackQuery, settings: Settings) -> None:
    await answer_callback(
        callback,
        f"💳 Payments are coming soon! Contact {settings.support_contact} for early access.",
        alert=True,
    )
