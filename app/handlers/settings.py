"""Settings: pause, privacy, blocked list, language placeholder, deletion."""

from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.types import InlineKeyboardButton as Btn
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.keyboards.common import remove_reply_keyboard
from app.keyboards.settings import (
    blocked_list_keyboard,
    delete_confirm_keyboard,
    delete_warning_keyboard,
    privacy_keyboard,
    settings_keyboard,
)
from app.services.errors import CheersError
from app.services.moderation import ModerationService
from app.services.users import UserService
from app.states.forms import DeleteAccount
from app.utils.render import answer_callback, safe_edit

router = Router(name="settings")


def _settings_text(user: User) -> str:
    status = []
    if user.is_banned:
        status.append("🚫 Suspended")
    if user.profile_paused:
        status.append("⏸ Paused")
    if user.is_premium:
        status.append("👑 Premium")
    if user.is_verified:
        status.append("✅ Verified")
    status_text = " · ".join(status) if status else "🟢 Active"
    return (
        "⚙️ <b>Settings</b>\n\n"
        f"👤 <b>{html.escape(user.first_name)}</b>, {user.age or '—'} · 📍 {html.escape(user.city or '—')}\n"
        f"Status: {status_text}\n\n"
        "Manage your profile, discovery filters, privacy and account here."
    )


async def _show_settings(target: CallbackQuery | Message, user: User) -> None:
    if isinstance(target, CallbackQuery):
        await safe_edit(target, _settings_text(user), settings_keyboard(user))
    else:
        await target.answer(_settings_text(user), reply_markup=settings_keyboard(user))


@router.message(Command("settings"))
async def cmd_settings(
    message: Message, state: FSMContext, user: User
) -> None:
    await state.clear()
    await _show_settings(message, user)


@router.callback_query(F.data == "menu:settings")
async def cb_settings(
    callback: CallbackQuery, state: FSMContext, user: User
) -> None:
    await state.clear()
    await answer_callback(callback)
    await _show_settings(callback, user)


@router.callback_query(F.data == "set:back")
async def cb_settings_back(
    callback: CallbackQuery, state: FSMContext, user: User
) -> None:
    await state.clear()
    await answer_callback(callback)
    await _show_settings(callback, user)


@router.message(Command("pause"))
async def cmd_pause(
    message: Message, state: FSMContext, session: AsyncSession, user: User
) -> None:
    await state.clear()
    if user.profile_paused:
        await message.answer(
            "⏸ Your profile is already paused. You're hidden from discovery.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [Btn(text="▶️ Resume profile", callback_data="set:resume")],
                    [Btn(text="⚙️ Settings", callback_data="menu:settings")],
                ]
            ),
        )
        return
    await UserService.set_paused(session, user, True)
    await message.answer(
        "⏸ <b>Profile paused.</b>\n\n"
        "You're hidden from discovery and won't appear to new people. "
        "Existing matches and chats are still available. Resume any time.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [Btn(text="▶️ Resume profile", callback_data="set:resume")],
                [Btn(text="🗑 Delete account", callback_data="set:delete")],
                [Btn(text="🏠 Main menu", callback_data="menu:home")],
            ]
        ),
    )


@router.callback_query(F.data == "set:pause")
async def cb_pause(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    await UserService.set_paused(session, user, True)
    await answer_callback(callback, "Profile paused.")
    await safe_edit(
        callback,
        "⏸ <b>Profile paused.</b>\n\n"
        "You're hidden from discovery. Existing matches and chats are still available.",
        InlineKeyboardMarkup(
            inline_keyboard=[
                [Btn(text="▶️ Resume profile", callback_data="set:resume")],
                [Btn(text="⚙️ Settings", callback_data="menu:settings")],
            ]
        ),
    )


@router.callback_query(F.data == "set:resume")
async def cb_resume(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
) -> None:
    await state.clear()
    await UserService.set_paused(session, user, False)
    await answer_callback(callback, "Welcome back! Profile active.")
    await safe_edit(
        callback,
        "▶️ <b>Your profile is active again.</b>\n\nReady to meet someone new?",
        InlineKeyboardMarkup(
            inline_keyboard=[
                [Btn(text="🔍 Discover", callback_data="menu:discover")],
                [Btn(text="🏠 Main menu", callback_data="menu:home")],
            ]
        ),
    )


@router.callback_query(F.data == "set:privacy")
async def cb_privacy(callback: CallbackQuery) -> None:
    from app.handlers.common import PRIVACY_TEXT

    await answer_callback(callback)
    await safe_edit(callback, PRIVACY_TEXT, privacy_keyboard())


@router.callback_query(F.data == "set:language")
async def cb_language(callback: CallbackQuery) -> None:
    await answer_callback(
        callback,
        "🌐 English is live today. አማርኛ (Amharic) is coming in a future update — "
        "your profile works in both.",
        alert=True,
    )


@router.callback_query(F.data == "set:blocked")
async def cb_blocked(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    blocked = await ModerationService.blocked_users(session, user)
    await answer_callback(callback)
    if not blocked:
        await safe_edit(
            callback,
            "🚫 <b>Blocked users</b>\n\nYou haven't blocked anyone. If someone makes you "
            "uncomfortable, block them from their profile or chat.",
            InlineKeyboardMarkup(
                inline_keyboard=[[Btn(text="⬅️ Back", callback_data="set:back")]]
            ),
        )
        return
    await safe_edit(
        callback,
        f"🚫 <b>Blocked users ({len(blocked)})</b>\n\nTap to unblock someone. "
        "Unblocking does not restore an old match.",
        blocked_list_keyboard(blocked),
    )


@router.callback_query(F.data.startswith("set:unblock:"))
async def cb_unblock(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    try:
        target_id = int((callback.data or "").split(":")[2])
    except (ValueError, IndexError):
        await answer_callback(callback, "Invalid user.", alert=True)
        return
    removed = await ModerationService.unblock_user(session, user, target_id)
    await answer_callback(callback, "Unblocked." if removed else "Not blocked.")
    blocked = await ModerationService.blocked_users(session, user)
    if blocked:
        await safe_edit(
            callback,
            f"🚫 <b>Blocked users ({len(blocked)})</b>\n\nTap to unblock someone.",
            blocked_list_keyboard(blocked),
        )
    else:
        await safe_edit(
            callback,
            "🚫 <b>Blocked users</b>\n\nYour blocked list is now empty.",
            InlineKeyboardMarkup(
                inline_keyboard=[[Btn(text="⬅️ Back", callback_data="set:back")]]
            ),
        )


@router.message(Command("deleteaccount"))
async def cmd_delete_account(
    message: Message, state: FSMContext, user: User
) -> None:
    await state.clear()
    await message.answer(
        "🗑 <b>Delete your Cheers account?</b>\n\n"
        "This permanently deletes your profile, photos, matches and chats. "
        "This cannot be undone.",
        reply_markup=delete_warning_keyboard(),
    )


@router.callback_query(F.data == "set:delete")
async def cb_delete(
    callback: CallbackQuery, user: User
) -> None:
    await answer_callback(callback)
    await safe_edit(
        callback,
        "🗑 <b>Delete your Cheers account?</b>\n\n"
        "This permanently deletes your profile, photos, matches and chats. "
        "This cannot be undone.",
        delete_warning_keyboard(),
    )


@router.callback_query(F.data == "set:delete_confirm")
async def cb_delete_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DeleteAccount.confirm)
    await answer_callback(callback)
    await safe_edit(
        callback,
        "⚠️ <b>Final confirmation</b>\n\n"
        "Type <code>DELETE</code> in this chat to permanently delete your account.\n"
        "Or tap the button below to cancel.",
        delete_confirm_keyboard(),
    )


@router.callback_query(F.data == "set:delete_cancel")
async def cb_delete_cancel(
    callback: CallbackQuery, state: FSMContext, user: User
) -> None:
    await state.clear()
    await answer_callback(callback, "Deletion cancelled.")
    await _show_settings(callback, user)


@router.message(StateFilter(DeleteAccount.confirm), F.text)
async def msg_delete_confirm(
    message: Message, state: FSMContext, session: AsyncSession, user: User
) -> None:
    if (message.text or "").strip().upper() != "DELETE":
        await message.answer(
            "Type <code>DELETE</code> exactly to confirm, or tap the cancel button.",
            reply_markup=delete_confirm_keyboard(),
        )
        return
    try:
        await UserService.delete_account(session, user)
    except CheersError as exc:
        await message.answer(f"⚠️ {exc.user_message}")
        return
    await state.clear()
    await message.answer(
        "💔 <b>Your account has been deleted.</b>\n\n"
        "Your profile, photos and matches are gone. We're sorry to see you go — "
        "you're welcome back any time with /start.",
        reply_markup=remove_reply_keyboard(),
    )
