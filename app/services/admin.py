"""Administrator statistics, user management, and audit log."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.models import (
    AdminAction,
    Match,
    Report,
    User,
)
from app.services.moderation import ModerationService
from app.utils.time import local_today, utcnow

logger = logging.getLogger(__name__)


@dataclass
class AdminStats:
    total_users: int
    active_users: int
    daily_registrations: int
    monthly_registrations: int
    total_matches: int
    active_matches: int
    open_reports: int
    banned_users: int
    premium_users: int


class AdminService:
    @staticmethod
    def _period_starts(settings: Settings) -> tuple[datetime, datetime]:
        tz = ZoneInfo(settings.app_timezone)
        today = local_today(settings.app_timezone)
        day_start = datetime.combine(today, time.min, tzinfo=tz)
        month_start = day_start.replace(day=1)
        return (
            day_start.astimezone(UTC),
            month_start.astimezone(UTC),
        )

    @staticmethod
    async def stats(session: AsyncSession, settings: Settings) -> AdminStats:
        day_start, month_start = AdminService._period_starts(settings)
        now = utcnow()

        async def count(condition) -> int:
            return int(
                await session.scalar(
                    sa.select(sa.func.count()).select_from(User).where(condition)
                )
                or 0
            )

        registered = User.registration_completed_at.is_not(None)
        total_users = await count(registered)
        active_users = await count(
            sa.and_(registered, User.last_active_at >= now - timedelta(days=30)),
        )
        daily = await count(sa.and_(registered, User.registration_completed_at >= day_start))
        monthly = await count(sa.and_(registered, User.registration_completed_at >= month_start))
        banned = await count(User.is_banned.is_(True))
        premium = await count(User.is_premium.is_(True))

        total_matches = int(
            await session.scalar(sa.select(sa.func.count()).select_from(Match)) or 0
        )
        active_matches = int(
            await session.scalar(
                sa.select(sa.func.count())
                .select_from(Match)
                .where(Match.is_active.is_(True))
            )
            or 0
        )
        open_reports = await ModerationService.count_open_reports(session)

        return AdminStats(
            total_users=total_users,
            active_users=active_users,
            daily_registrations=daily,
            monthly_registrations=monthly,
            total_matches=total_matches,
            active_matches=active_matches,
            open_reports=open_reports,
            banned_users=banned,
            premium_users=premium,
        )

    @staticmethod
    async def list_users(
        session: AsyncSession, query: str | None = None, offset: int = 0, limit: int = 8
    ) -> tuple[list[User], int]:
        conditions = [User.registration_completed_at.is_not(None)]
        if query:
            q = query.strip()
            pattern = f"%{q}%"
            search = [
                User.first_name.ilike(pattern),
                User.username.ilike(pattern),
                User.city.ilike(pattern),
            ]
            if q.isdigit():
                search.append(User.id == int(q))
                search.append(User.telegram_id == int(q))
            conditions.append(sa.or_(*search))

        total = int(
            await session.scalar(
                sa.select(sa.func.count()).select_from(User).where(*conditions)
            )
            or 0
        )
        result = await session.scalars(
            sa.select(User)
            .where(*conditions)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.unique()), total

    @staticmethod
    async def report_count_against(session: AsyncSession, user_id: int) -> int:
        return int(
            await session.scalar(
                sa.select(sa.func.count())
                .select_from(Report)
                .where(Report.reported_id == user_id)
            )
            or 0
        )

    @staticmethod
    async def recent_actions(session: AsyncSession, limit: int = 10) -> list[AdminAction]:
        result = await session.scalars(
            sa.select(AdminAction).order_by(AdminAction.created_at.desc()).limit(limit)
        )
        return list(result)

    @staticmethod
    async def log_action(
        session: AsyncSession,
        admin_telegram_id: int,
        action: str,
        target_user_id: int | None = None,
        details: str | None = None,
    ) -> None:
        session.add(
            AdminAction(
                admin_telegram_id=admin_telegram_id,
                action=action,
                target_user_id=target_user_id,
                details=details,
            )
        )
        await session.commit()
