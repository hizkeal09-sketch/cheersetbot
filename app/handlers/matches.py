"""Matches list, match details, chat sessions, and unmatching."""

from __future__ import annotations

import html

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.types import InlineKeyboardButton as Btn
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.keyboards.matches import (
    chat_keyboard,
    match_actions_keyboard,
    matches_keyboard,
    unmatch_confirm_keyboard,
)
from app.services.errors import CheersError, NotRegisteredError
from app.services.matches import MatchService
from app.services.messages import MessageService
from app.services.users import UserService
from app.states.forms import ChatStates
from app.utils.render import answer_callback, safe_edit, send_profile_card

router = Router(name="matches")

PAGE_SIZE = 8


@router.message(Command("matches"))
async def cmd_matches(
    message: Message, state: FSMContext, user: User, session: AsyncSession, bot: Bot
) -> None:
    await state.clear()
    try:
        await _send_matches(bot, message.chat.id, user, session, 0)
    except NotRegisteredError as exc:
        await message.answer(exc.user_message)


@router.callback_query(F.data == "menu:matches")
async def cb_matches(
    callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession, bot: Bot
) -> None:
    await state.clear()
    await answer_callback(callback)
    await _send_matches(bot, callback.from_user.id, user, session, 0)


@router.callback_query(F.data.startswith("match:page:"))
async def cb_matches_page(
    callback: CallbackQuery, user: User, session: AsyncSession, bot: Bot
) -> None:
    try:
        page = max(0, int((callback.data or "").split(":")[2]))
    except (ValueError, IndexError):
        page = 0
    await answer_callback(callback)
    await _send_matches(bot, callback.from_user.id, user, session, page)


@router.callback_query(F.data == "match:list")
async def cb_match_list(
    callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession, bot: Bot
) -> None:
    await state.clear()
    await answer_callback(callback)
    await _send_matches(bot, callback.from_user.id, user, session, 0)


async def _send_matches(
    bot: Bot, chat_id: int, user: User, session: AsyncSession, page: int
) -> None:
    UserService.ensure_registered(user)
    matches = await MatchService.list_active(session, user.id)
    total_matches = await MatchService.count_total(session)
    today_matches = await MatchService.count_today(session)
    if not matches:
        await bot.send_message(
            chat_id,
            f"💬 <b>No matches yet</b>\n\n"
            f"🔥 Today's matches on Cheers: <b>{today_matches}</b>\n"
            f"Total matches on Cheers: <b>{total_matches}</b>\n\n"
            "Discovery is where the magic starts. Like people who catch your eye — "
            "when they like you back, you'll match here.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [Btn(text="🔍 Discover people", callback_data="menu:discover")],
                    [Btn(text="🏠 Main menu", callback_data="menu:home")],
                ]
            ),
        )
        return

    start = page * PAGE_SIZE
    page_items = matches[start : start + PAGE_SIZE]
    if not page_items:
        page = 0
        page_items = matches[:PAGE_SIZE]
    has_next = len(matches) > start + PAGE_SIZE
    await bot.send_message(
        chat_id,
        f"💬 <b>Your matches</b>\n\n"
        f"{len(matches)} mutual match(es) · {total_matches} total matches on Cheers · "
        f"🔥 {today_matches} matches today!\n\n"
        "Tap a person to view their profile, or chat right away.",
        reply_markup=matches_keyboard(page_items, user, page, has_next),
    )


@router.callback_query(F.data.startswith("match:open:"))
async def cb_match_open(
    callback: CallbackQuery, user: User, session: AsyncSession, bot: Bot
) -> None:
    try:
        match_id = int((callback.data or "").split(":")[2])
        match = await MatchService.get_active_for_user(session, user.id, match_id)
        partner = match.other_user(user.id)
    except CheersError as exc:
        await answer_callback(callback, exc.user_message, alert=True)
        return
    await answer_callback(callback)
    await send_profile_card(
        bot,
        callback.from_user.id,
        partner,
        header="💞 <b>You matched</b>",
        reply_markup=match_actions_keyboard(match.id, partner.id),
    )


@router.callback_query(F.data.startswith("chat:open:"))
async def cb_chat_open(
    callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession, bot: Bot
) -> None:
    try:
        match_id = int((callback.data or "").split(":")[2])
    except (ValueError, IndexError):
        await answer_callback(callback, "Invalid match.", alert=True)
        return
    await _open_chat(callback, state, user, session, bot, match_id)


async def _open_chat(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    bot: Bot,
    match_id: int,
) -> None:
    try:
        match = await MatchService.get_active_for_user(session, user.id, match_id)
        partner = match.other_user(user.id)
    except CheersError as exc:
        await answer_callback(callback, exc.user_message, alert=True)
        return

    await state.set_state(ChatStates.active)
    await state.update_data(match_id=match.id, partner_id=partner.id)
    await MessageService.mark_read(session, user, match.id)
    await answer_callback(callback)
    await bot.send_message(
        callback.from_user.id,
        f"💬 <b>Chat with {html.escape(partner.first_name)}</b>\n\n"
        "Send a text or photo below. It will be delivered privately.\n\n"
        "🔒 Contact details and links are blocked for your safety.\n"
        "Use the button below to leave the chat.",
        reply_markup=chat_keyboard(match.id, partner.id),
    )


@router.callback_query(F.data == "chat:end")
async def cb_chat_end(
    callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession, bot: Bot
) -> None:
    await state.clear()
    await answer_callback(callback, "Chat closed.")
    await safe_edit(
        callback,
        "💬 Chat closed. Your conversation is safe in <b>Matches</b> whenever you return.",
        InlineKeyboardMarkup(
            inline_keyboard=[
                [Btn(text="💬 Matches", callback_data="menu:matches")],
                [Btn(text="🔍 Discover", callback_data="menu:discover")],
                [Btn(text="🏠 Main menu", callback_data="menu:home")],
            ]
        ),
    )


@router.callback_query(F.data.startswith("match:chat:"))
async def cb_match_chat(
    callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession, bot: Bot
) -> None:
    # Alias used by the match list and match detail card.
    try:
        match_id = int((callback.data or "").split(":")[2])
    except (ValueError, IndexError):
        await answer_callback(callback, "Invalid match.", alert=True)
        return
    await _open_chat(callback, state, user, session, bot, match_id)


@router.callback_query(F.data.startswith("match:unmatch:"))
async def cb_unmatch(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    try:
        match_id = int((callback.data or "").split(":")[2])
        await MatchService.get_active_for_user(session, user.id, match_id)
    except CheersError as exc:
        await answer_callback(callback, exc.user_message, alert=True)
        return
    await answer_callback(callback)
    await safe_edit(
        callback,
        "💔 <b>End this match?</b>\n\n"
        "You will no longer be able to message each other. This cannot be undone.",
        unmatch_confirm_keyboard(match_id),
    )


@router.callback_query(F.data.startswith("match:unmatch_yes:"))
async def cb_unmatch_confirm(
    callback: CallbackQuery, state: FSMContext, user: User, session: AsyncSession
) -> None:
    try:
        match_id = int((callback.data or "").split(":")[2])
        await MatchService.unmatch(session, user.id, match_id)
    except (ValueError, IndexError):
        await answer_callback(callback, "Invalid match.", alert=True)
        return
    except CheersError as exc:
        await answer_callback(callback, exc.user_message, alert=True)
        return
    data = await state.get_data()
    if data.get("match_id") == match_id:
        await state.clear()
    await answer_callback(callback, "Match ended.")
    await safe_edit(
        callback,
        "💔 <b>Match ended.</b>\n\nYour profile is still active. There are plenty more "
        "great people to meet.",
        InlineKeyboardMarkup(
            inline_keyboard=[
                [Btn(text="🔍 Discover", callback_data="menu:discover")],
                [Btn(text="💬 Matches", callback_data="menu:matches")],
            ]
        ),
    )
