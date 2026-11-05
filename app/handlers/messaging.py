"""Private text and photo relay between matched users."""

from __future__ import annotations

import html

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton as Btn
from aiogram.types import InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.constants import MessageKind
from app.database.models import User
from app.keyboards.matches import chat_reply_keyboard
from app.services.errors import CheersError, ContactInfoBlockedError, NotMatchedError
from app.services.messages import MessageService
from app.states.forms import ChatStates
from app.utils.validators import ValidationError

router = Router(name="messaging")


@router.message(Command("end"))
async def cmd_end(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    await state.clear()
    if current == ChatStates.active.state:
        await message.answer(
            "✖️ Chat closed.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [Btn(text="💬 Matches", callback_data="menu:matches")],
                    [Btn(text="🏠 Main menu", callback_data="menu:home")],
                ]
            ),
        )
    else:
        await message.answer("You're not in a chat right now.")


@router.message(StateFilter(ChatStates.active), F.text)
async def relay_text(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    bot: Bot,
    settings: Settings,
) -> None:
    text = (message.text or "").strip()
    if text.startswith("/"):
        await message.answer("Type your message, or use /end to leave this chat.")
        return
    await _relay(
        message,
        state,
        session,
        user,
        bot,
        settings,
        kind=MessageKind.TEXT,
        text=text,
    )


@router.message(StateFilter(ChatStates.active), F.photo)
async def relay_photo(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    bot: Bot,
    settings: Settings,
) -> None:
    caption = (message.caption or "").strip() or None
    if caption and len(caption) > 900:
        await message.answer("📝 Photo caption is too long. Keep it under 900 characters.")
        return
    await _relay(
        message,
        state,
        session,
        user,
        bot,
        settings,
        kind=MessageKind.PHOTO,
        text=caption,
        photo_file_id=message.photo[-1].file_id if message.photo else None,
    )


async def _relay(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    bot: Bot,
    settings: Settings,
    *,
    kind: MessageKind,
    text: str | None,
    photo_file_id: str | None = None,
) -> None:
    data = await state.get_data()
    match_id = data.get("match_id")
    if not match_id:
        await state.clear()
        await message.answer("This chat session expired. Open your matches and tap Chat again.")
        return

    try:
        _record, recipient, match = await MessageService.store_message(
            session,
            user,
            int(match_id),
            kind=kind,
            text=text,
            photo_file_id=photo_file_id,
            settings=settings,
        )
    except ContactInfoBlockedError as exc:
        await message.answer(f"🔒 {exc.user_message}")
        return
    except NotMatchedError as exc:
        await state.clear()
        await message.answer(
            f"💔 {exc.user_message}",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [Btn(text="💬 Matches", callback_data="menu:matches")],
                    [Btn(text="🏠 Main menu", callback_data="menu:home")],
                ]
            ),
        )
        return
    except ValidationError as exc:
        await message.answer(f"⚠️ {exc}")
        return
    except CheersError as exc:
        await message.answer(f"⚠️ {exc.user_message}")
        return

    name = html.escape(user.first_name)
    try:
        if kind == MessageKind.TEXT:
            await bot.send_message(
                recipient.telegram_id,
                f"💬 <b>{name}</b>\n{html.escape(text or '')}",
                reply_markup=chat_reply_keyboard(match.id),
            )
        else:
            caption = f"📷 <b>Photo from {name}</b>"
            if text:
                caption += f"\n\n{html.escape(text)}"
            await bot.send_photo(
                recipient.telegram_id,
                photo=photo_file_id,
                caption=caption,
                reply_markup=chat_reply_keyboard(match.id),
            )
        await session.commit()
    except TelegramAPIError:
        await session.rollback()
        await message.answer(
            "⚠️ This person can't receive messages right now. Please try again later."
        )
        return
    except Exception:
        await session.rollback()
        raise

    await MessageService.mark_read(session, user, match.id)
