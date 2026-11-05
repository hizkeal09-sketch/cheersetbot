"""Administrator dashboard: stats, reports, users, premium, broadcast, audit."""

from __future__ import annotations

import asyncio
import contextlib
import html
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.constants import REPORT_REASON_LABELS, REPORT_STATUS_LABELS, ReportStatus
from app.database.models import Report
from app.keyboards.admin import (
    admin_back_keyboard,
    admin_broadcast_keyboard,
    admin_broadcast_resume_keyboard,
    admin_dashboard_keyboard,
    admin_report_detail_keyboard,
    admin_reports_keyboard,
    admin_user_detail_keyboard,
    admin_users_keyboard,
)
from app.services.admin import AdminService
from app.services.broadcast import (
    BroadcastProgress,
    create_broadcast_job,
    process_broadcast_job,
)
from app.services.errors import CheersError
from app.services.moderation import ModerationService
from app.services.premium import PremiumService
from app.services.users import UserService
from app.states.forms import AdminFlow
from app.utils.render import answer_callback, safe_edit
from app.utils.time import as_utc

logger = logging.getLogger(__name__)
_background_tasks: set[asyncio.Task] = set()

router = Router(name="admin")

PAGE_SIZE = 8


class AdminOnlyMiddleware(BaseMiddleware):
    """Reject every update from a Telegram ID that is not configured as admin."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        settings: Settings | None = data.get("settings")
        tg_user = data.get("event_from_user")
        if settings is None or tg_user is None or tg_user.id not in settings.admin_id_list:
            try:
                if isinstance(event, CallbackQuery):
                    await event.answer("⛔ Admin access only.", show_alert=True)
                elif isinstance(event, Message):
                    await event.answer("⛔ This command is for administrators only.")
            except TelegramAPIError:
                pass
            return None
        return await handler(event, data)


router.message.middleware(AdminOnlyMiddleware())
router.callback_query.middleware(AdminOnlyMiddleware())


def _stats_text(stats) -> str:
    return (
        "🛡 <b>Cheers Dating — Admin</b>\n\n"
        f"👥 Registered users: <b>{stats.total_users}</b>\n"
        f"🟢 Active (30 days): <b>{stats.active_users}</b>\n"
        f"📈 New today: <b>{stats.daily_registrations}</b> · This month: <b>{stats.monthly_registrations}</b>\n"
        f"💞 Matches: <b>{stats.total_matches}</b> (active: {stats.active_matches})\n"
        f"🚩 Open reports: <b>{stats.open_reports}</b>\n"
        f"🚫 Banned: <b>{stats.banned_users}</b>\n"
        f"👑 Premium: <b>{stats.premium_users}</b>"
    )


@router.message(Command("admin"))
async def cmd_admin(
    message: Message, state: FSMContext, session: AsyncSession, settings: Settings
) -> None:
    await state.clear()
    stats = await AdminService.stats(session, settings)
    await message.answer(_stats_text(stats), reply_markup=admin_dashboard_keyboard())


@router.callback_query(F.data == "adm:home")
async def cb_admin_home(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings
) -> None:
    await state.clear()
    stats = await AdminService.stats(session, settings)
    await answer_callback(callback)
    await safe_edit(callback, _stats_text(stats), admin_dashboard_keyboard())


@router.callback_query(F.data == "adm:stats")
async def cb_admin_stats(
    callback: CallbackQuery, session: AsyncSession, settings: Settings
) -> None:
    stats = await AdminService.stats(session, settings)
    await answer_callback(callback, "Stats refreshed.")
    await safe_edit(callback, _stats_text(stats), admin_dashboard_keyboard())


@router.callback_query(F.data.startswith("adm:reports:"))
async def cb_admin_reports(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    try:
        page = max(0, int((callback.data or "").split(":")[2]))
    except (ValueError, IndexError):
        page = 0
    reports, total = await ModerationService.list_reports(
        session, status=None, offset=page * PAGE_SIZE, limit=PAGE_SIZE
    )
    await answer_callback(callback)
    if not reports:
        await safe_edit(
            callback,
            "🚩 <b>Reports</b>\n\nNo reports found. 🎉",
            admin_back_keyboard("adm:home"),
        )
        return
    has_next = total > (page + 1) * PAGE_SIZE
    await safe_edit(
        callback,
        f"🚩 <b>Reports</b> — {total} total\n\nSelect a report to review.",
        admin_reports_keyboard(reports, page, has_next),
    )


def _report_text(report: Report) -> str:
    reporter = report.reporter
    reported = report.reported
    reason = REPORT_REASON_LABELS.get(report.reason, report.reason.value)
    status = REPORT_STATUS_LABELS.get(report.status, report.status.value)
    lines = [
        f"🚩 <b>Report #{report.id}</b>",
        f"Status: {status}",
        f"Reason: {reason}",
        "",
        f"Reporter: <b>{html.escape(reporter.first_name)}</b> "
        f"(db {reporter.id}, tg <code>{reporter.telegram_id}</code>)",
        f"Reported: <b>{html.escape(reported.first_name)}</b> "
        f"(db {reported.id}, tg <code>{reported.telegram_id}</code>)",
        f"Reported status: {'🚫 banned' if reported.is_banned else 'active'}",
    ]
    if report.details:
        lines += ["", f"Details: <i>{html.escape(report.details)}</i>"]
    if report.reviewed_by:
        when = as_utc(report.reviewed_at)
        lines.append(f"\nReviewed by tg {report.reviewed_by}" + (f" at {when:%d %b %Y %H:%M} UTC" if when else ""))
    return "\n".join(lines)


@router.callback_query(F.data.startswith("adm:report:"))
async def cb_admin_report(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    try:
        report_id = int((callback.data or "").split(":")[2])
        report = await ModerationService.get_report(session, report_id)
    except (ValueError, IndexError, CheersError) as exc:
        await answer_callback(callback, f"Report not found: {exc}", alert=True)
        return
    await answer_callback(callback)
    await safe_edit(callback, _report_text(report), admin_report_detail_keyboard(report))


@router.callback_query(F.data.startswith("adm:ban:"))
async def cb_admin_ban_from_report(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    try:
        _, _, user_part, report_part = (callback.data or "").split(":")
        user_id = int(user_part)
        report_id = int(report_part)
        target = await UserService.get_by_id(session, user_id)
        report = await ModerationService.get_report(session, report_id)
        await ModerationService.ban_user(
            session,
            callback.from_user.id,
            target,
            f"Banned from report #{report.id}: {report.reason.value}",
        )
        report = await ModerationService.set_report_status(
            session,
            report.id,
            ReportStatus.RESOLVED,
            callback.from_user.id,
            notes="Reported user banned.",
        )
    except (ValueError, CheersError) as exc:
        await answer_callback(callback, f"Could not ban: {exc}", alert=True)
        return

    with contextlib.suppress(TelegramAPIError):
        await bot.send_message(
            target.telegram_id,
            "🚫 Your Cheers Dating account has been suspended after a safety review.\n\n"
            "If you believe this is a mistake, contact support.",
        )
    await answer_callback(callback, "User banned and report resolved.")
    await safe_edit(callback, _report_text(report), admin_report_detail_keyboard(report))


@router.callback_query(F.data.startswith("adm:resolve:"))
async def cb_admin_resolve(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    await _set_report_state(callback, session, ReportStatus.RESOLVED)


@router.callback_query(F.data.startswith("adm:dismiss:"))
async def cb_admin_dismiss(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    await _set_report_state(callback, session, ReportStatus.DISMISSED)


async def _set_report_state(
    callback: CallbackQuery, session: AsyncSession, status: ReportStatus
) -> None:
    try:
        report_id = int((callback.data or "").split(":")[2])
        report = await ModerationService.get_report(session, report_id)
        report = await ModerationService.set_report_status(
            session, report.id, status, callback.from_user.id
        )
    except (ValueError, IndexError, CheersError) as exc:
        await answer_callback(callback, f"Could not update: {exc}", alert=True)
        return
    await answer_callback(callback, f"Report marked {status.value}.")
    await safe_edit(callback, _report_text(report), admin_report_detail_keyboard(report))


@router.callback_query(F.data.startswith("adm:users:"))
async def cb_admin_users(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    try:
        page = max(0, int((callback.data or "").split(":")[2]))
    except (ValueError, IndexError):
        page = 0
    users, total = await AdminService.list_users(
        session, offset=page * PAGE_SIZE, limit=PAGE_SIZE
    )
    await answer_callback(callback)
    if not users:
        await safe_edit(
            callback,
            "👥 <b>Users</b>\n\nNo registered users yet.",
            admin_back_keyboard("adm:home"),
        )
        return
    has_next = total > (page + 1) * PAGE_SIZE
    await safe_edit(
        callback,
        f"👥 <b>Users</b> — {total} registered\n\nSelect a user to manage.",
        admin_users_keyboard(users, page, has_next),
    )


@router.callback_query(F.data == "adm:search")
async def cb_admin_search(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFlow.search)
    await answer_callback(callback)
    await safe_edit(
        callback,
        "🔎 <b>Search users</b>\n\nSend a name, username, city, DB id or Telegram ID.",
        admin_back_keyboard("adm:home"),
    )


@router.message(StateFilter(AdminFlow.search), F.text)
async def msg_admin_search(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    query = (message.text or "").strip()
    users, total = await AdminService.list_users(session, query=query, offset=0, limit=PAGE_SIZE)
    await state.clear()
    if not users:
        await message.answer(
            f"🔎 No users found for <b>{html.escape(query)}</b>.",
            reply_markup=admin_back_keyboard("adm:home"),
        )
        return
    await message.answer(
        f"🔎 <b>Search results</b> — {total} match(es)\n\nSelect a user.",
        reply_markup=admin_users_keyboard(users, 0, total > PAGE_SIZE),
    )


@router.callback_query(F.data.startswith("adm:user:"))
async def cb_admin_user(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    try:
        user_id = int((callback.data or "").split(":")[2])
        user = await UserService.get_by_id(session, user_id)
        reports = await AdminService.report_count_against(session, user.id)
    except (ValueError, IndexError, CheersError) as exc:
        await answer_callback(callback, f"User not found: {exc}", alert=True)
        return
    await answer_callback(callback)
    text = (
        f"👤 <b>User #{user.id}</b>\n\n"
        f"Name: <b>{html.escape(user.first_name)}</b>\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Username: @{html.escape(user.username) if user.username else '—'}\n"
        f"Age: {user.age or '—'} · Gender: {user.gender.value if user.gender else '—'}\n"
        f"City: {html.escape(user.city or '—')}\n"
        f"Registered: {'yes' if user.is_registered else 'no'}\n"
        f"Status: {'🚫 banned' if user.is_banned else ('⏸ paused' if user.profile_paused else '🟢 active')}\n"
        f"Premium: {'👑 yes' if user.is_premium else 'no'} · Verified: {'✅' if user.is_verified else 'no'}\n"
        f"Reports against: <b>{reports}</b>"
    )
    await safe_edit(callback, text, admin_user_detail_keyboard(user))


@router.callback_query(F.data.startswith("adm:user_ban:"))
async def cb_admin_user_ban(
    callback: CallbackQuery, session: AsyncSession, bot: Bot
) -> None:
    try:
        user_id = int((callback.data or "").split(":")[2])
        target = await UserService.get_by_id(session, user_id)
    except (ValueError, IndexError, CheersError) as exc:
        await answer_callback(callback, f"User not found: {exc}", alert=True)
        return
    await ModerationService.ban_user(
        session,
        callback.from_user.id,
        target,
        "Violation of Cheers community rules (admin action).",
    )
    with contextlib.suppress(TelegramAPIError):
        await bot.send_message(
            target.telegram_id,
            "🚫 Your Cheers Dating account has been suspended by an administrator.\n\n"
            "If you believe this is a mistake, contact support.",
        )
    await answer_callback(callback, "User banned.")
    await _refresh_admin_user(callback, session, target.id)


@router.callback_query(F.data.startswith("adm:user_unban:"))
async def cb_admin_user_unban(
    callback: CallbackQuery, session: AsyncSession, bot: Bot
) -> None:
    try:
        user_id = int((callback.data or "").split(":")[2])
        target = await UserService.get_by_id(session, user_id)
    except (ValueError, IndexError, CheersError) as exc:
        await answer_callback(callback, f"User not found: {exc}", alert=True)
        return
    await ModerationService.unban_user(session, callback.from_user.id, target)
    with contextlib.suppress(TelegramAPIError):
        await bot.send_message(
            target.telegram_id,
            "✅ Your Cheers Dating account has been reinstated. Welcome back! Use /start to continue.",
        )
    await answer_callback(callback, "User unbanned.")
    await _refresh_admin_user(callback, session, target.id)


async def _refresh_admin_user(
    callback: CallbackQuery, session: AsyncSession, user_id: int
) -> None:
    user = await UserService.get_by_id(session, user_id)
    reports = await AdminService.report_count_against(session, user.id)
    text = (
        f"👤 <b>User #{user.id}</b>\n\n"
        f"Name: <b>{html.escape(user.first_name)}</b>\n"
        f"Telegram ID: <code>{user.telegram_id}</code>\n"
        f"Status: {'🚫 banned' if user.is_banned else ('⏸ paused' if user.profile_paused else '🟢 active')}\n"
        f"Premium: {'👑 yes' if user.is_premium else 'no'}\n"
        f"Reports against: <b>{reports}</b>"
    )
    await safe_edit(callback, text, admin_user_detail_keyboard(user))


@router.callback_query(F.data.startswith("adm:grant:"))
async def cb_admin_grant(
    callback: CallbackQuery, session: AsyncSession, bot: Bot
) -> None:
    try:
        user_id = int((callback.data or "").split(":")[2])
        target = await UserService.get_by_id(session, user_id)
    except (ValueError, IndexError, CheersError) as exc:
        await answer_callback(callback, f"User not found: {exc}", alert=True)
        return
    await PremiumService.grant(session, target, 30)
    await AdminService.log_action(
        session, callback.from_user.id, "grant_premium", target.id, "30 days"
    )
    with contextlib.suppress(TelegramAPIError):
        await bot.send_message(
            target.telegram_id,
            "👑 <b>You've been granted Cheers Premium for 30 days!</b>\n\nEnjoy more discoveries, advanced filters and more. 🍻",
        )
    await answer_callback(callback, "Premium granted for 30 days.")
    await _refresh_admin_user(callback, session, target.id)


@router.callback_query(F.data.startswith("adm:revoke:"))
async def cb_admin_revoke(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    try:
        user_id = int((callback.data or "").split(":")[2])
        target = await UserService.get_by_id(session, user_id)
    except (ValueError, IndexError, CheersError) as exc:
        await answer_callback(callback, f"User not found: {exc}", alert=True)
        return
    await PremiumService.revoke(session, target)
    await AdminService.log_action(
        session, callback.from_user.id, "revoke_premium", target.id
    )
    await answer_callback(callback, "Premium revoked.")
    await _refresh_admin_user(callback, session, target.id)


@router.callback_query(F.data == "adm:broadcast")
async def cb_admin_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFlow.broadcast)
    await answer_callback(callback)
    await safe_edit(
        callback,
        "📢 <b>Broadcast announcement</b>\n\n"
        "Send the message you want every registered, non-banned user to receive. "
        "Plain text only. Maximum 4,000 characters.\n\n"
        "Use /cancel to abort.",
        admin_back_keyboard("adm:home"),
    )


@router.message(StateFilter(AdminFlow.broadcast), F.text)
async def msg_broadcast(
    message: Message, state: FSMContext
) -> None:
    if (message.text or "").startswith("/"):
        await message.answer("Send the announcement as plain text, or use /cancel.")
        return
    text = (message.text or "").strip()
    if not 1 <= len(text) <= 4000:
        await message.answer("Announcement must be between 1 and 4,000 characters.")
        return
    await state.update_data(broadcast_text=text)
    await message.answer(
        "📢 <b>Preview</b>\n\n────────────\n"
        f"{html.escape(text)}\n────────────\n\n"
        "Send this to every active registered user?",
        reply_markup=admin_broadcast_keyboard(),
    )


@router.callback_query(F.data == "adm:broadcast_yes")
async def cb_admin_broadcast_yes(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    data = await state.get_data()
    text = data.get("broadcast_text")
    if not text:
        await answer_callback(callback, "No announcement text. Start again.", alert=True)
        return
    await state.clear()
    admin_id = callback.from_user.id

    job = await create_broadcast_job(session, text, admin_id)
    await answer_callback(callback, "Broadcast started.")
    await safe_edit(
        callback,
        "📢 <b>Broadcast in progress…</b>\n\nYou'll receive a summary when it finishes.",
        admin_back_keyboard("adm:home"),
    )

    if settings.is_serverless:
        # A Vercel function may be frozen right after this response, so the
        # broadcast runs inline for a bounded slice and stores its cursor.
        progress = await process_broadcast_job(
            bot,
            session_factory,
            job.id,
            max_seconds=settings.broadcast_inline_seconds,
        )
        if progress is not None and not progress.finished:
            await bot.send_message(
                admin_id,
                f"📢 <b>Broadcast still running</b>\n\n"
                f"✅ Sent so far: {progress.sent}\n❌ Failed: {progress.failed}\n\n"
                "Tap continue to send the next batch of recipients.",
                reply_markup=admin_broadcast_resume_keyboard(job.id),
            )
        return

    async def _run() -> None:
        try:
            await process_broadcast_job(
                bot,
                session_factory,
                job.id,
                max_seconds=3600,
            )
        except Exception:  # pragma: no cover - background safety net
            logger.exception("Broadcast failed")
            with contextlib.suppress(TelegramAPIError):
                await bot.send_message(admin_id, "⚠️ Broadcast failed. Check the logs.")

    task = asyncio.create_task(_run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


@router.callback_query(F.data.startswith("adm:bcast_resume:"))
async def cb_admin_broadcast_resume(
    callback: CallbackQuery,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    raw_job_id = callback.data.rsplit(":", 1)[-1]
    try:
        job_id = int(raw_job_id)
    except ValueError:
        await answer_callback(callback, "Invalid broadcast job.", alert=True)
        return

    await answer_callback(callback, "Continuing broadcast…")
    progress: BroadcastProgress | None = await process_broadcast_job(
        bot,
        session_factory,
        job_id,
        max_seconds=settings.broadcast_inline_seconds,
    )
    if progress is None:
        await callback.message.answer("Broadcast job not found.")
        return
    if progress.finished:
        return
    await callback.message.answer(
        f"📢 <b>Broadcast still running</b>\n\n"
        f"✅ Sent so far: {progress.sent}\n❌ Failed: {progress.failed}\n\n"
        "Tap continue to send the next batch of recipients.",
        reply_markup=admin_broadcast_resume_keyboard(job_id),
    )


@router.callback_query(F.data == "adm:broadcast_no")
async def cb_admin_broadcast_no(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await answer_callback(callback, "Broadcast cancelled.")
    await safe_edit(
        callback,
        "Broadcast cancelled. Nothing was sent.",
        admin_dashboard_keyboard(),
    )


@router.callback_query(F.data == "adm:audit")
async def cb_admin_audit(
    callback: CallbackQuery, session: AsyncSession
) -> None:
    actions = await AdminService.recent_actions(session, 15)
    await answer_callback(callback)
    if not actions:
        await safe_edit(
            callback,
            "📜 <b>Audit log</b>\n\nNo admin actions yet.",
            admin_back_keyboard("adm:home"),
        )
        return
    lines = ["📜 <b>Recent admin actions</b>\n"]
    for action in actions:
        when = as_utc(action.created_at)
        stamp = f"{when:%d %b %H:%M}" if when else "—"
        target = f" → user #{action.target_user_id}" if action.target_user_id else ""
        details = f" ({html.escape(action.details)})" if action.details else ""
        lines.append(f"• {stamp} · {action.action}{target}{details}")
    await safe_edit(callback, "\n".join(lines), admin_back_keyboard("adm:home"))
