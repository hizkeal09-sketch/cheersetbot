"""Administrator dashboard keyboards."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton as Btn
from aiogram.types import InlineKeyboardMarkup

from app.database.models import Report, User


def admin_dashboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                Btn(text="📊 Refresh stats", callback_data="adm:stats"),
                Btn(text="🚩 Reports", callback_data="adm:reports:0"),
            ],
            [
                Btn(text="👥 Users", callback_data="adm:users:0"),
                Btn(text="🔎 Search", callback_data="adm:search"),
            ],
            [
                Btn(text="📢 Broadcast", callback_data="adm:broadcast"),
                Btn(text="📜 Audit log", callback_data="adm:audit"),
            ],
            [Btn(text="🏠 Main menu", callback_data="menu:home")],
        ]
    )


def admin_reports_keyboard(reports: list[Report], page: int, has_next: bool) -> InlineKeyboardMarkup:
    rows: list[list[Btn]] = [
        [
            Btn(
                text=f"#{report.id} · {report.reporter.first_name} → {report.reported.first_name}",
                callback_data=f"adm:report:{report.id}",
            )
        ]
        for report in reports
    ]
    nav: list[Btn] = []
    if page > 0:
        nav.append(Btn(text="⬅️ Previous", callback_data=f"adm:reports:{page - 1}"))
    if has_next:
        nav.append(Btn(text="Next ➡️", callback_data=f"adm:reports:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([Btn(text="⬅️ Dashboard", callback_data="adm:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_report_detail_keyboard(report: Report) -> InlineKeyboardMarkup:
    rows = [
        [
            Btn(
                text="🚫 Ban reported user",
                callback_data=f"adm:ban:{report.reported_id}:{report.id}",
            )
        ]
    ]
    if report.status.value in ("open", "reviewing"):
        rows.append(
            [
                Btn(text="✅ Resolve", callback_data=f"adm:resolve:{report.id}"),
                Btn(text="⚪ Dismiss", callback_data=f"adm:dismiss:{report.id}"),
            ]
        )
    rows.append([Btn(text="⬅️ Reports", callback_data="adm:reports:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_users_keyboard(users: list[User], page: int, has_next: bool) -> InlineKeyboardMarkup:
    rows: list[list[Btn]] = []
    for user in users:
        status = ""
        if user.is_banned:
            status = " 🚫"
        elif user.profile_paused:
            status = " ⏸"
        rows.append(
            [
                Btn(
                    text=f"#{user.id} {user.first_name[:20]}{status}",
                    callback_data=f"adm:user:{user.id}",
                )
            ]
        )
    nav: list[Btn] = []
    if page > 0:
        nav.append(Btn(text="⬅️ Previous", callback_data=f"adm:users:{page - 1}"))
    if has_next:
        nav.append(Btn(text="Next ➡️", callback_data=f"adm:users:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append(
        [
            Btn(text="🔎 Search", callback_data="adm:search"),
            Btn(text="⬅️ Dashboard", callback_data="adm:home"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_user_detail_keyboard(user: User) -> InlineKeyboardMarkup:
    if user.is_banned:
        ban_button = Btn(text="✅ Unban user", callback_data=f"adm:user_unban:{user.id}")
    else:
        ban_button = Btn(text="🚫 Ban user", callback_data=f"adm:user_ban:{user.id}")
    if user.is_premium:
        premium_button = Btn(text="❌ Revoke premium", callback_data=f"adm:revoke:{user.id}")
    else:
        premium_button = Btn(text="👑 Grant 30d premium", callback_data=f"adm:grant:{user.id}")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [ban_button, premium_button],
            [Btn(text="🚩 View reports", callback_data="adm:reports:0")],
            [Btn(text="⬅️ Users", callback_data="adm:users:0")],
        ]
    )


def admin_broadcast_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                Btn(text="📢 Send to everyone", callback_data="adm:broadcast_yes"),
                Btn(text="✖️ Cancel", callback_data="adm:broadcast_no"),
            ]
        ]
    )


def admin_broadcast_resume_keyboard(job_id: int) -> InlineKeyboardMarkup:
    """Continue a paused broadcast (used on serverless deployments)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                Btn(
                    text="▶️ Continue broadcast",
                    callback_data=f"adm:bcast_resume:{job_id}",
                )
            ]
        ]
    )


def admin_back_keyboard(target: str = "adm:home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[Btn(text="⬅️ Back", callback_data=target)]]
    )
