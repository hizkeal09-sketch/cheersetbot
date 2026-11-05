"""Reporting, blocking, and user-facing safety flows."""

from __future__ import annotations

import html

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.types import InlineKeyboardButton as Btn
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.constants import REPORT_REASON_LABELS, ReportReason
from app.database.models import Report, User
from app.keyboards.safety import (
    block_confirm_keyboard,
    report_details_keyboard,
    report_reasons_keyboard,
    report_submitted_keyboard,
    user_picker_keyboard,
)
from app.services.errors import CheersError
from app.services.matches import MatchService
from app.services.moderation import ModerationService
from app.services.users import UserService
from app.states.forms import ChatStates, ReportFlow
from app.utils.render import answer_callback, safe_edit
from app.utils.validators import ValidationError, validate_report_details

router = Router(name="safety")


async def _notify_admins(
    bot: Bot,
    settings: Settings,
    report: Report,
    reporter: User,
    reported: User,
) -> None:
    reason = REPORT_REASON_LABELS.get(report.reason, report.reason.value)
    details = f"\nDetails: {html.escape(report.details)}" if report.details else ""
    text = (
        f"🚩 <b>New report #{report.id}</b>\n\n"
        f"Reporter: {html.escape(reporter.first_name)} (id {reporter.id}, tg {reporter.telegram_id})\n"
        f"Reported: {html.escape(reported.first_name)} (id {reported.id}, tg {reported.telegram_id})\n"
        f"Reason: {reason}{details}\n\n"
        f"Reported user has {reported.is_banned and 'an active ban' or 'no active ban'}.\n"
        "Open the admin dashboard to review."
    )
    for admin_id in settings.admin_id_list:
        try:
            await bot.send_message(
                admin_id,
                text,
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[Btn(text="🛡 Review report", callback_data=f"adm:report:{report.id}")]]
                ),
            )
        except TelegramAPIError:
            continue


async def _begin_report(
    target: User,
    state: FSMContext,
    *,
    edit_callback: CallbackQuery | None = None,
    message: Message | None = None,
) -> None:
    await state.set_state(ReportFlow.reason)
    await state.update_data(
        target_id=target.id, target_name=target.first_name
    )
    text = (
        f"🚩 <b>Report {html.escape(target.first_name)}</b>\n\n"
        "What happened? Reports are confidential and reviewed by our team."
    )
    if edit_callback:
        await safe_edit(edit_callback, text, report_reasons_keyboard())
    elif message:
        await message.answer(text, reply_markup=report_reasons_keyboard())


@router.message(Command("report"))
async def cmd_report(
    message: Message, state: FSMContext, user: User, session: AsyncSession
) -> None:
    current = await state.get_state()
    if current == ChatStates.active.state:
        data = await state.get_data()
        match_id = data.get("match_id")
        if match_id:
            try:
                match = await MatchService.get_active_for_user(session, user.id, int(match_id))
                await _begin_report(match.other_user(user.id), state, message=message)
                return
            except CheersError:
                pass

    try:
        matches = await MatchService.list_active(session, user.id)
    except CheersError:
        matches = []
    if not matches:
        await message.answer(
            "🚩 You can report someone from their profile card, or from a chat.\n\n"
            "If you are in a chat, open it and tap <b>Report</b>.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [Btn(text="💬 Matches", callback_data="menu:matches")],
                    [Btn(text="🏠 Main menu", callback_data="menu:home")],
                ]
            ),
        )
        return
    users = [match.other_user(user.id) for match in matches[:8]]
    await message.answer(
        "🚩 <b>Report someone</b>\n\nChoose the person you want to report.",
        reply_markup=user_picker_keyboard(users, "report:pick"),
    )


@router.callback_query(F.data.regexp(r"^report:pick:\d+$"))
async def cb_report_pick(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    try:
        target_id = int((callback.data or "").split(":")[2])
        target = await UserService.get_by_id(session, target_id)
    except (ValueError, IndexError, CheersError) as exc:
        await answer_callback(callback, f"Could not open report: {exc}", alert=True)
        return
    await answer_callback(callback)
    await _begin_report(target, state, edit_callback=callback)


@router.callback_query(F.data.regexp(r"^report:\d+$"))
async def cb_report_start(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    try:
        target_id = int((callback.data or "").split(":")[1])
        target = await UserService.get_by_id(session, target_id)
    except (ValueError, IndexError, CheersError) as exc:
        await answer_callback(callback, f"Could not open report: {exc}", alert=True)
        return
    if target.telegram_id == callback.from_user.id:
        await answer_callback(callback, "You cannot report yourself.", alert=True)
        return
    await answer_callback(callback)
    await _begin_report(target, state, edit_callback=callback)


@router.callback_query(StateFilter(ReportFlow.reason), F.data.startswith("rep:reason:"))
async def cb_report_reason(callback: CallbackQuery, state: FSMContext) -> None:
    raw = (callback.data or "").split(":")[-1]
    try:
        reason = ReportReason(raw)
    except ValueError:
        await answer_callback(callback, "Invalid reason.", alert=True)
        return
    await state.update_data(reason=reason.value)
    await state.set_state(ReportFlow.details)
    await answer_callback(callback)
    await safe_edit(
        callback,
        "📝 <b>Add any details</b> (optional)\n\n"
        "Share anything that helps our moderators — for example what was said or sent.\n"
        "Do not include personal contact details.",
        report_details_keyboard(),
    )


@router.message(StateFilter(ReportFlow.details), F.text)
async def msg_report_details(
    message: Message, state: FSMContext, session: AsyncSession, user: User, bot: Bot, settings: Settings
) -> None:
    try:
        details = validate_report_details(message.text or "") or None
    except ValidationError as exc:
        await message.answer(f"⚠️ {exc}")
        return
    await _submit_report(message, state, session, user, bot, settings, details)


@router.callback_query(StateFilter(ReportFlow.details), F.data == "rep:skip")
async def cb_report_skip(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    bot: Bot,
    settings: Settings,
) -> None:
    await answer_callback(callback)
    await _submit_report(callback.message, state, session, user, bot, settings, None, callback=callback)


async def _submit_report(
    message: Message | None,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    bot: Bot,
    settings: Settings,
    details: str | None,
    callback: CallbackQuery | None = None,
) -> None:
    data = await state.get_data()
    target_id = data.get("target_id")
    reason_raw = data.get("reason")
    if not target_id or not reason_raw:
        await state.clear()
        if callback:
            await safe_edit(
                callback,
                "This report session expired. Please start again with /report.",
                InlineKeyboardMarkup(
                    inline_keyboard=[[Btn(text="🏠 Main menu", callback_data="menu:home")]]
                ),
            )
        elif message:
            await message.answer("This report session expired. Please start again with /report.")
        return

    try:
        target = await UserService.get_by_id(session, int(target_id))
        report = await ModerationService.report_user(
            session, user, target.id, ReportReason(reason_raw), details
        )
    except CheersError as exc:
        await state.clear()
        if callback:
            await answer_callback(callback, exc.user_message, alert=True)
            await safe_edit(
                callback,
                f"⚠️ {exc.user_message}",
                InlineKeyboardMarkup(
                    inline_keyboard=[[Btn(text="🏠 Main menu", callback_data="menu:home")]]
                ),
            )
        elif message:
            await message.answer(f"⚠️ {exc.user_message}")
        return

    await state.clear()
    await _notify_admins(bot, settings, report, user, target)
    text = (
        "✅ <b>Report received</b>\n\n"
        "Thank you for helping keep Cheers safe. Our moderation team will review this. "
        "You can also block this person so they can't contact you."
    )
    if callback:
        await safe_edit(callback, text, report_submitted_keyboard(target.id))
    elif message:
        await message.answer(text, reply_markup=report_submitted_keyboard(target.id))


@router.callback_query(F.data == "rep:cancel")
async def cb_report_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await answer_callback(callback, "Report cancelled.")
    await safe_edit(
        callback,
        "Report cancelled. You're back in control. 🍻",
        InlineKeyboardMarkup(
            inline_keyboard=[
                [Btn(text="🏠 Main menu", callback_data="menu:home")],
                [Btn(text="💬 Matches", callback_data="menu:matches")],
            ]
        ),
    )


@router.message(Command("block"))
async def cmd_block(
    message: Message, state: FSMContext, user: User, session: AsyncSession
) -> None:
    current = await state.get_state()
    if current == ChatStates.active.state:
        data = await state.get_data()
        match_id = data.get("match_id")
        if match_id:
            try:
                match = await MatchService.get_active_for_user(session, user.id, int(match_id))
                partner = match.other_user(user.id)
                await message.answer(
                    f"🚫 <b>Block {html.escape(partner.first_name)}?</b>\n\n"
                    "They will not be able to message you or see your profile. "
                    "Your match will end.",
                    reply_markup=block_confirm_keyboard(partner.id),
                )
                return
            except CheersError:
                pass

    matches = await MatchService.list_active(session, user.id)
    if not matches:
        await message.answer(
            "🚫 You can block someone from their profile card or from a chat.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[Btn(text="🏠 Main menu", callback_data="menu:home")]]
            ),
        )
        return
    users = [match.other_user(user.id) for match in matches[:8]]
    await message.answer(
        "🚫 <b>Block someone</b>\n\nChoose the person you want to block.",
        reply_markup=user_picker_keyboard(users, "block:pick"),
    )


@router.callback_query(F.data.regexp(r"^block:pick:\d+$"))
async def cb_block_pick(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    try:
        target_id = int((callback.data or "").split(":")[2])
        target = await UserService.get_by_id(session, target_id)
    except (ValueError, IndexError, CheersError) as exc:
        await answer_callback(callback, f"Could not open block: {exc}", alert=True)
        return
    await answer_callback(callback)
    await safe_edit(
        callback,
        f"🚫 <b>Block {html.escape(target.first_name)}?</b>\n\n"
        "They will not be able to message you or see your profile. Your match will end.",
        block_confirm_keyboard(target.id),
    )


@router.callback_query(F.data.regexp(r"^block:\d+$"))
async def cb_block_start(
    callback: CallbackQuery, session: AsyncSession, user: User
) -> None:
    try:
        target_id = int((callback.data or "").split(":")[1])
        target = await UserService.get_by_id(session, target_id)
    except (ValueError, IndexError, CheersError) as exc:
        await answer_callback(callback, f"Could not block: {exc}", alert=True)
        return
    if target.id == user.id:
        await answer_callback(callback, "You cannot block yourself.", alert=True)
        return
    await answer_callback(callback)
    await safe_edit(
        callback,
        f"🚫 <b>Block {html.escape(target.first_name)}?</b>\n\n"
        "They will not be able to message you or see your profile. Your match will end.",
        block_confirm_keyboard(target.id),
    )


@router.callback_query(F.data.startswith("block:yes:"))
async def cb_block_confirm(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, user: User
) -> None:
    try:
        target_id = int((callback.data or "").split(":")[2])
        target = await UserService.get_by_id(session, target_id)
        added = await ModerationService.block_user(session, user, target.id)
    except (ValueError, IndexError, CheersError) as exc:
        await answer_callback(callback, f"Could not block: {exc}", alert=True)
        return
    await state.clear()
    await answer_callback(callback, "Blocked." if added else "Already blocked.")
    await safe_edit(
        callback,
        f"🚫 <b>{html.escape(target.first_name)} has been blocked.</b>\n\n"
        "They can no longer message you or see your profile. If this was a safety concern, "
        "you can also report them from your matches or with /report.",
        InlineKeyboardMarkup(
            inline_keyboard=[
                [Btn(text="🏠 Main menu", callback_data="menu:home")],
                [Btn(text="🔍 Discover", callback_data="menu:discover")],
            ]
        ),
    )


@router.callback_query(F.data == "block:no")
async def cb_block_cancel(callback: CallbackQuery) -> None:
    await answer_callback(callback, "Cancelled.")
    await safe_edit(
        callback,
        "No one was blocked. 🍻",
        InlineKeyboardMarkup(
            inline_keyboard=[
                [Btn(text="🏠 Main menu", callback_data="menu:home")],
                [Btn(text="💬 Matches", callback_data="menu:matches")],
            ]
        ),
    )
