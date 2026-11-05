"""Reporting, blocking, bans, and moderation queues."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import ReportReason, ReportStatus
from app.database.models import AdminAction, Block, Match, Report, User
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
