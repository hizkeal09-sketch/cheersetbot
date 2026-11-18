"""Administrator dashboard keyboards."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton as Btn
from aiogram.types import InlineKeyboardMarkup

from app.constants import PHOTO_MODERATION_LABELS, PhotoModerationStatus
from app.database.models import Report, User, UserPhoto


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
                Btn(text="📸 Photo Moderation", callback_data="adm:moderation"),
                Btn(text="🚩 User Moderation", callback_data="adm:moderation"),
            ],
            [
                Btn(text="📢 Broadcast", callback_data="adm:broadcast"),
                Btn(text="📜 Audit log", callback_data="adm:audit"),
            ],
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
    rows.append([Btn(text="📝 Add/Edit notes", callback_data=f"adm:report_notes:{report.id}")])
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
            [Btn(text="📝 Add/Edit notes", callback_data=f"adm:user_notes:{user.id}")],
            [Btn(text="🗑 Delete user data", callback_data=f"adm:user_delete:{user.id}")],
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


def admin_photo_moderation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [Btn(text="📸 Pending Photos", callback_data="adm:photos:pending:0")],
            [Btn(text="🚩 Flagged Photos", callback_data="adm:photos:flagged:0")],
            [Btn(text="⬅️ Dashboard", callback_data="adm:home")],
        ]
    )


def admin_photos_list_keyboard(
    photos: list[UserPhoto], page: int, has_next: bool, filter_type: str = "pending"
) -> InlineKeyboardMarkup:
    rows: list[list[Btn]] = []
    for photo in photos:
        status_label = PHOTO_MODERATION_LABELS.get(
            PhotoModerationStatus(photo.moderation_status), photo.moderation_status
        )
        rows.append(
            [
                Btn(
                    text=f"📸 Photo #{photo.id} · {status_label}",
                    callback_data=f"adm:photo:{photo.id}",
                )
            ]
        )
    nav: list[Btn] = []
    if page > 0:
        nav.append(Btn(text="⬅️ Previous", callback_data=f"adm:photos:{filter_type}:{page - 1}"))
    if has_next:
        nav.append(Btn(text="Next ➡️", callback_data=f"adm:photos:{filter_type}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append(
        [
            Btn(text="🔎 Filter: Pending", callback_data="adm:photos:pending:0"),
            Btn(text="🚩 Filter: Flagged", callback_data="adm:photos:flagged:0"),
        ]
    )
    rows.append([Btn(text="⬅️ Moderation", callback_data="adm:moderation")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_photo_detail_keyboard(photo: UserPhoto) -> InlineKeyboardMarkup:
    status = PhotoModerationStatus(photo.moderation_status)
    rows: list[list[Btn]] = []
    if status == PhotoModerationStatus.PENDING:
        rows.append(
            [
                Btn(text="✅ Approve", callback_data=f"adm:photo_approve:{photo.id}"),
                Btn(text="❌ Reject", callback_data=f"adm:photo_reject:{photo.id}"),
            ]
        )
    elif status == PhotoModerationStatus.REJECTED:
        rows.append(
            [Btn(text="✅ Re-approve", callback_data=f"adm:photo_approve:{photo.id}")]
        )
    elif status == PhotoModerationStatus.FLAGGED:
        rows.append(
            [
                Btn(text="✅ Approve", callback_data=f"adm:photo_approve:{photo.id}"),
                Btn(text="❌ Reject", callback_data=f"adm:photo_reject:{photo.id}"),
            ]
        )
    rows.append([Btn(text="⬅️ Back to photos", callback_data="adm:photos:pending:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_moderation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [Btn(text="🚩 Flagged Users", callback_data="adm:flagged:0")],
            [Btn(text="⚠️ Suspicious Users", callback_data="adm:suspicious:0")],
            [Btn(text="⬅️ Dashboard", callback_data="adm:home")],
        ]
    )


def admin_flagged_users_keyboard(
    users: list[User], page: int, has_next: bool
) -> InlineKeyboardMarkup:
    rows: list[list[Btn]] = []
    for user in users:
        score_indicator = "🔴" if user.suspicion_score >= 50 else "🟡" if user.suspicion_score >= 30 else "🟢"
        rows.append(
            [
                Btn(
                    text=f"#{user.id} {user.first_name[:18]}{score_indicator} (s:{user.suspicion_score})",
                    callback_data=f"adm:user:{user.id}",
                )
            ]
        )
    nav: list[Btn] = []
    if page > 0:
        nav.append(Btn(text="⬅️ Previous", callback_data=f"adm:flagged:{page - 1}"))
    if has_next:
        nav.append(Btn(text="Next ➡️", callback_data=f"adm:flagged:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([Btn(text="⬅️ Moderation", callback_data="adm:moderation")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_user_action_keyboard(user: User) -> InlineKeyboardMarkup:
    rows: list[list[Btn]] = []
    if user.is_flagged:
        rows.append(
            [Btn(text="✅ Unflag User", callback_data=f"adm:user_unflag:{user.id}")]
        )
    else:
        rows.append(
            [Btn(text="🚩 Flag User", callback_data=f"adm:user_flag:{user.id}")]
        )
    if user.new_account_restricted_until:
        rows.append(
            [Btn(text="✅ Unrestrict User", callback_data=f"adm:user_unrestrict:{user.id}")]
        )
    else:
        rows.append(
            [Btn(text="⏰ Restrict 24h", callback_data=f"adm:user_restrict:{user.id}")]
        )
    if user.is_banned:
        rows.append([Btn(text="✅ Unban User", callback_data=f"adm:user_unban:{user.id}")])
    else:
        rows.append([Btn(text="🚫 Suspend 7d", callback_data=f"adm:user_suspend:{user.id}")])
    rows.append([Btn(text="⚠️ Warn User", callback_data=f"adm:user_warn:{user.id}")])
    rows.append([Btn(text="⬅️ Back to Moderation", callback_data="adm:moderation")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
