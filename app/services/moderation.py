"""Reporting, blocking, bans, and moderation queues."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import PhotoModerationStatus, ReportReason, ReportStatus
from app.database.models import AdminAction, Block, Match, Report, User, UserPhoto
from app.services.errors import InvalidTargetError, ReportAlreadyOpenError
from app.services.matches import MatchService
from app.utils.time import utcnow
from app.utils.validators import validate_report_details


class ModerationService:
    @staticmethod
    async def report_user(
        session: AsyncSession,
        reporter: User,
        reported_id: int,
        reason: ReportReason,
        details: str | None = None,
    ) -> Report:
        if reporter.id == reported_id:
            raise InvalidTargetError("You cannot report yourself.")
        reported = await session.get(User, reported_id)
        if reported is None:
            raise InvalidTargetError()

        existing = await session.scalar(
            sa.select(Report).where(
                Report.reporter_id == reporter.id,
                Report.reported_id == reported_id,
                Report.status.in_((ReportStatus.OPEN, ReportStatus.REVIEWING)),
            )
        )
        if existing:
            raise ReportAlreadyOpenError()

        report = Report(
            reporter_id=reporter.id,
            reported_id=reported_id,
            reason=reason,
            details=validate_report_details(details) if details else None,
            status=ReportStatus.OPEN,
        )
        session.add(report)
        await session.commit()
        return report

    @staticmethod
    async def block_user(session: AsyncSession, blocker: User, blocked_id: int) -> bool:
        if blocker.id == blocked_id:
            raise InvalidTargetError("You cannot block yourself.")
        blocked = await session.get(User, blocked_id)
        if blocked is None:
            raise InvalidTargetError()

        existing = await session.scalar(
            sa.select(Block).where(
                Block.blocker_id == blocker.id, Block.blocked_id == blocked_id
            )
        )
        if existing:
            return False
        session.add(Block(blocker_id=blocker.id, blocked_id=blocked_id))
        await MatchService.deactivate_between(session, blocker.id, blocked_id)
        await session.commit()
        return True

    @staticmethod
    async def unblock_user(session: AsyncSession, blocker: User, blocked_id: int) -> bool:
        block = await session.scalar(
            sa.select(Block).where(
                Block.blocker_id == blocker.id, Block.blocked_id == blocked_id
            )
        )
        if block is None:
            return False
        await session.delete(block)
        await session.commit()
        return True

    @staticmethod
    async def blocked_users(session: AsyncSession, blocker: User) -> list[User]:
        result = await session.scalars(
            sa.select(User)
            .join(Block, Block.blocked_id == User.id)
            .where(Block.blocker_id == blocker.id)
            .order_by(Block.created_at.desc())
        )
        return list(result.unique())

    @staticmethod
    async def is_blocked(session: AsyncSession, first_id: int, second_id: int) -> bool:
        block = await session.scalar(
            sa.select(Block).where(
                sa.or_(
                    sa.and_(Block.blocker_id == first_id, Block.blocked_id == second_id),
                    sa.and_(Block.blocker_id == second_id, Block.blocked_id == first_id),
                )
            )
        )
        return block is not None

    @staticmethod
    async def ban_user(
        session: AsyncSession,
        admin_telegram_id: int,
        user: User,
        reason: str,
    ) -> User:
        user.is_banned = True
        user.profile_paused = True
        user.is_active = False
        user.ban_reason = reason
        await session.execute(
            sa.update(Match)
            .where(
                Match.is_active.is_(True),
                (Match.user_a_id == user.id) | (Match.user_b_id == user.id),
            )
            .values(is_active=False, ended_at=utcnow())
        )
        session.add(
            AdminAction(
                admin_telegram_id=admin_telegram_id,
                action="ban_user",
                target_user_id=user.id,
                details=reason,
            )
        )
        await session.commit()
        return user

    @staticmethod
    async def unban_user(
        session: AsyncSession, admin_telegram_id: int, user: User
    ) -> User:
        user.is_banned = False
        user.ban_reason = None
        user.is_active = True
        session.add(
            AdminAction(
                admin_telegram_id=admin_telegram_id,
                action="unban_user",
                target_user_id=user.id,
            )
        )
        await session.commit()
        return user

    @staticmethod
    async def list_reports(
        session: AsyncSession,
        status: ReportStatus | None = None,
        offset: int = 0,
        limit: int = 10,
    ) -> tuple[list[Report], int]:
        conditions = []
        if status:
            conditions.append(Report.status == status)
        total = int(
            await session.scalar(
                sa.select(sa.func.count()).select_from(Report).where(*conditions)
            )
            or 0
        )
        result = await session.scalars(
            sa.select(Report)
            .where(*conditions)
            .order_by(Report.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.unique()), total

    @staticmethod
    async def get_report(session: AsyncSession, report_id: int) -> Report:
        report = await session.get(Report, report_id)
        if report is None:
            raise InvalidTargetError("Report not found.")
        return report

    @staticmethod
    async def set_report_status(
        session: AsyncSession,
        report_id: int,
        status: ReportStatus,
        admin_telegram_id: int,
        notes: str | None = None,
    ) -> Report:
        report = await ModerationService.get_report(session, report_id)
        report.status = status
        report.reviewed_by = admin_telegram_id
        report.reviewed_at = utcnow()
        if notes:
            report.admin_notes = notes
        session.add(
            AdminAction(
                admin_telegram_id=admin_telegram_id,
                action=f"report_{status.value}",
                target_user_id=report.reported_id,
                details=f"Report #{report.id}",
            )
        )
        await session.commit()
        return report

    @staticmethod
    async def count_open_reports(session: AsyncSession) -> int:
        return int(
            await session.scalar(
                sa.select(sa.func.count())
                .select_from(Report)
                .where(Report.status.in_((ReportStatus.OPEN, ReportStatus.REVIEWING)))
            )
            or 0
        )

    @staticmethod
    async def list_pending_photos(
        session: AsyncSession, offset: int = 0, limit: int = 10
    ) -> tuple[list[UserPhoto], int]:
        """List photos pending moderation."""
        total = int(
            await session.scalar(
                sa.select(sa.func.count())
                .select_from(UserPhoto)
                .where(UserPhoto.moderation_status == PhotoModerationStatus.PENDING)
            )
            or 0
        )
        result = await session.scalars(
            sa.select(UserPhoto)
            .where(UserPhoto.moderation_status == PhotoModerationStatus.PENDING)
            .order_by(UserPhoto.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.unique()), total

    @staticmethod
    async def get_photo(session: AsyncSession, photo_id: int) -> UserPhoto:
        photo = await session.get(UserPhoto, photo_id)
        if photo is None:
            raise InvalidTargetError("Photo not found.")
        return photo

    @staticmethod
    async def moderate_photo(
        session: AsyncSession,
        photo_id: int,
        admin_telegram_id: int,
        status: PhotoModerationStatus,
        reason: str | None = None,
    ) -> UserPhoto:
        """Approve or reject a photo."""
        photo = await ModerationService.get_photo(session, photo_id)
        photo.moderation_status = status
        photo.moderation_reason = reason
        session.add(
            AdminAction(
                admin_telegram_id=admin_telegram_id,
                action=f"photo_{status.value}",
                target_user_id=photo.user_id,
                details=f"Photo #{photo.id}",
            )
        )
        await session.commit()
        return photo

    @staticmethod
    async def count_pending_photos(session: AsyncSession) -> int:
        return int(
            await session.scalar(
                sa.select(sa.func.count())
                .select_from(UserPhoto)
                .where(UserPhoto.moderation_status == PhotoModerationStatus.PENDING)
            )
            or 0
        )

    @staticmethod
    async def flag_user(
        session: AsyncSession,
        admin_telegram_id: int,
        user: User,
        reason: str,
        suspicion_score_increase: int = 10,
    ) -> User:
        """Flag a user as suspicious."""
        user.is_flagged = True
        user.flag_reason = reason
        user.suspicion_score = min(100, user.suspicion_score + suspicion_score_increase)
        session.add(
            AdminAction(
                admin_telegram_id=admin_telegram_id,
                action="flag_user",
                target_user_id=user.id,
                details=f"Reason: {reason}, score: {user.suspicion_score}",
            )
        )
        await session.commit()
        return user

    @staticmethod
    async def unflag_user(
        session: AsyncSession, admin_telegram_id: int, user: User
    ) -> User:
        """Unflag a user."""
        user.is_flagged = False
        user.flag_reason = None
        user.suspicion_score = max(0, user.suspicion_score - 10)
        session.add(
            AdminAction(
                admin_telegram_id=admin_telegram_id,
                action="unflag_user",
                target_user_id=user.id,
                details="User unflagged",
            )
        )
        await session.commit()
        return user

    @staticmethod
    async def increase_suspicion_score(
        session: AsyncSession, user: User, points: int, reason: str
    ) -> User:
        """Increase suspicion score for a user."""
        user.suspicion_score = min(100, user.suspicion_score + points)
        if user.suspicion_score >= 50 and not user.is_flagged:
            user.is_flagged = True
            user.flag_reason = f"Auto-flagged: suspicion score {user.suspicion_score}"
        session.add(
            AdminAction(
                admin_telegram_id=0,  # System action
                action="increase_suspicion",
                target_user_id=user.id,
                details=f"+{points} points: {reason}, total: {user.suspicion_score}",
            )
        )
        await session.commit()
        return user

    @staticmethod
    async def get_flagged_users(
        session: AsyncSession, offset: int = 0, limit: int = 10
    ) -> tuple[list[User], int]:
        """Get list of flagged users."""
        total = int(
            await session.scalar(
                sa.select(sa.func.count())
                .select_from(User)
                .where(User.is_flagged.is_(True))
            )
            or 0
        )
        result = await session.scalars(
            sa.select(User)
            .where(User.is_flagged.is_(True))
            .order_by(User.suspicion_score.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.unique()), total

    @staticmethod
    async def get_suspicious_users(
        session: AsyncSession, min_score: int = 30, offset: int = 0, limit: int = 10
    ) -> tuple[list[User], int]:
        """Get users with high suspicion score."""
        total = int(
            await session.scalar(
                sa.select(sa.func.count())
                .select_from(User)
                .where(User.suspicion_score >= min_score)
            )
            or 0
        )
        result = await session.scalars(
            sa.select(User)
            .where(User.suspicion_score >= min_score)
            .order_by(User.suspicion_score.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.unique()), total

    @staticmethod
    async def restrict_new_account(
        session: AsyncSession, user: User, hours: int = 24
    ) -> User:
        """Restrict a new account from messaging for N hours."""
        from datetime import timedelta

        user.new_account_restricted_until = utcnow() + timedelta(hours=hours)
        session.add(
            AdminAction(
                admin_telegram_id=0,  # System action
                action="restrict_new_account",
                target_user_id=user.id,
                details=f"Restricted for {hours} hours",
            )
        )
        await session.commit()
        return user

    @staticmethod
    async def unrestrict_new_account(
        session: AsyncSession, user: User
    ) -> User:
        """Remove new account restrictions."""
        user.new_account_restricted_until = None
        await session.commit()
        return user

    @staticmethod
    async def check_message_limit(
        session: AsyncSession, user: User
    ) -> tuple[bool, str | None]:
        """Check if user can send messages. Returns (allowed, reason)."""
        from datetime import date, timedelta

        today = date.today()

        # Reset daily counter if new day
        if user.last_message_reset != today:
            user.messages_today = 0
            user.last_message_reset = today
            await session.commit()

        # Check if new account is restricted
        if user.new_account_restricted_until:
            from datetime import datetime

            if utcnow() < user.new_account_restricted_until:
                remaining = user.new_account_restricted_until - utcnow()
                hours = remaining.total_seconds() / 3600
                return False, f"New account restricted. Messaging available in {hours:.1f} hours."

        # Check daily message limit for new accounts (less than 7 days old)
        if user.registration_completed_at:
            days_since_reg = (utcnow() - user.registration_completed_at).days
            if days_since_reg < 7:
                if user.messages_today >= 20:
                    return False, "Daily message limit reached for new accounts (20/day)."

        return True, None

    @staticmethod
    async def increment_message_count(
        session: AsyncSession, user: User
    ) -> None:
        """Increment message count for today."""
        from datetime import date

        today = date.today()
        if user.last_message_reset != today:
            user.messages_today = 1
            user.last_message_reset = today
        else:
            user.messages_today += 1
        await session.commit()
