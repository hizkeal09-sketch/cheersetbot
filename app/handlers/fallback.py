"""Last-resort handlers for unknown messages and stale buttons."""

from __future__ import annotations

import contextlib

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.types import InlineKeyboardButton as Btn

from app.config import Settings
from app.database.models import User
from app.keyboards.common import main_menu
from app.states.forms import ChatStates
from app.utils.render import answer_callback

router = Router(name="fallback")


@router.message()
async def fallback_message(
    message: Message, state: FSMContext, user: User, settings: Settings
) -> None:
    current = await state.get_state()
    group = current.split(":", 1)[0] if current else ""

    if group in {"Registration", "EditProfile"}:
        await message.answer(
            "📝 Please use the buttons above, or send the information requested. "
            "Type /cancel to stop."
        )
        return
    if current == ChatStates.active.state:
        await message.answer(
            "💬 I can relay text and photos. Send a message, or use /end to leave the chat."
        )
        return
    if not user.is_registered:
        await message.answer("👋 Tap /start to begin your Cheers Dating profile.")
        return

    await message.answer(
        "🤔 I didn't quite catch that. Here's your menu — what would you like to do?",
        reply_markup=main_menu(message.from_user.id in settings.admin_id_list),
    )


@router.callback_query()
async def fallback_callback(callback: CallbackQuery, user: User) -> None:
    await answer_callback(callback, "This button has expired. Opening the menu for you.")
    if user.is_registered:
        with contextlib.suppress(Exception):
            await callback.message.answer(
                "🏠 Here's your menu.",
                reply_markup=main_menu(),
            )
    else:
        await callback.message.answer(
            "Tap /start to begin.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[Btn(text="🍻 Start", callback_data="reg:age_ok")]]
            ),
        )
