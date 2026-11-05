"""Profile discovery, filters, likes, and daily limits."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.constants import (
    Gender,
    Preference,
    Religion,
    ReportStatus,
    ViewAction,
)
from app.database.models import (
    Block,
    DailyUsage,
    Like,
    Match,
    ProfileView,
    Report,
    User,
    UserFilter,
)
from app.services.errors import (
    AccountBannedError,
    DailyLimitReached,
    ProfilePausedError,
    TargetUnavailableError,
)
from app.services.matches import MatchService
from app.services.premium import daily_discovery_limit
from app.services.users import UserService
from app.utils.time import birth_date_bounds, local_today, utcnow
from app.utils.validators import ValidationError, validate_city


@dataclass
class LikeResult:
    matched: bool
    match: Match | None = None
    already_liked: bool = False


class DiscoveryService:
    @staticmethod
    async def _get_usage(
        session: AsyncSession, user_id: int, tz_name: str
    ) -> DailyUsage:
        today = local_today(tz_name)
        usage = await session.scalar(
            sa.select(DailyUsage).where(
                DailyUsage.user_id == user_id, DailyUsage.usage_date == today
            )
        )
        if usage:
            return usage

        usage = DailyUsage(user_id=user_id, usage_date=today)
        try:
            async with session.begin_nested():
                session.add(usage)
                await session.flush()
            return usage
        except IntegrityError:
            existing = await session.scalar(
                sa.select(DailyUsage).where(
                    DailyUsage.user_id == user_id, DailyUsage.usage_date == today
                )
            )
            if existing is None:
                raise
            return existing

    @staticmethod
    async def remaining_discoveries(
        session: AsyncSession, user: User, settings: Settings
    ) -> int:
        limit = daily_discovery_limit(user, settings)
        usage = await DiscoveryService._get_usage(session, user.id, settings.app_timezone)
        await session.commit()
        return max(0, limit - usage.discoveries)

    @staticmethod
    async def get_next_candidate(
        session: AsyncSession, viewer: User, settings: Settings
    ) -> User | None:
        if viewer.is_banned:
            raise AccountBannedError()
        UserService.ensure_registered(viewer)
        if viewer.profile_paused:
            raise ProfilePausedError()

        limit = daily_discovery_limit(viewer, settings)
        usage = await DiscoveryService._get_usage(session, viewer.id, settings.app_timezone)
        if usage.discoveries >= limit:
            raise DailyLimitReached(limit)

        flt = viewer.filter
        min_age = flt.min_age if flt else 18
        max_age = flt.max_age if flt else 60
        oldest_birth_date, newest_birth_date = birth_date_bounds(min_age, max_age)

        blocked_by_me = sa.select(Block.blocked_id).where(Block.blocker_id == viewer.id)
        blocked_me = sa.select(Block.blocker_id).where(Block.blocked_id == viewer.id)
        viewed = sa.select(ProfileView.viewed_id).where(ProfileView.viewer_id == viewer.id)
        reported = sa.select(Report.reported_id).where(
            Report.reporter_id == viewer.id,
            Report.status.in_((ReportStatus.OPEN, ReportStatus.REVIEWING)),
        )
        matched = sa.union(
            sa.select(Match.user_b_id.label("id")).where(
                Match.user_a_id == viewer.id, Match.is_active.is_(True)
            ),
            sa.select(Match.user_a_id.label("id")).where(
                Match.user_b_id == viewer.id, Match.is_active.is_(True)
            ),
        ).subquery()

        conditions = [
            User.id != viewer.id,
            User.registration_completed_at.is_not(None),
            User.is_active.is_(True),
            User.is_banned.is_(False),
            User.profile_paused.is_(False),
            User.gender.is_not(None),
            User.interested_in.is_not(None),
            User.birth_date.is_not(None),
            User.birth_date <= oldest_birth_date,
            User.birth_date >= newest_birth_date,
            User.id.not_in(viewed),
            User.id.not_in(blocked_by_me),
            User.id.not_in(blocked_me),
            User.id.not_in(reported),
            User.id.not_in(sa.select(matched.c.id)),
        ]

        # Target gender: explicit filter > registration preference > auto opposite-sex.
        # When no preference is set (no filter), match the opposite sex
        # so men see women and women see men by default.
        target_gender: Gender | None = None
        if flt and flt.gender is not None:
            target_gender = flt.gender
        elif viewer.interested_in == Preference.MEN:
            target_gender = Gender.MAN
        elif viewer.interested_in == Preference.WOMEN or viewer.gender == Gender.MAN:
            target_gender = Gender.WOMAN
        elif viewer.gender == Gender.WOMAN:
            target_gender = Gender.MAN
        # NON_BINARY or unknown viewer gender: no automatic gender filter.
        # (Only Man and Woman are supported in this version.)

        if target_gender is not None:
            conditions.append(User.gender == target_gender)

        # Reciprocal preference: the candidate must also be open to the viewer.
        if viewer.gender == Gender.MAN:
            conditions.append(User.interested_in == Preference.MEN)
        elif viewer.gender == Gender.WOMAN:
            conditions.append(User.interested_in == Preference.WOMEN)

        if flt and flt.city:
            conditions.append(sa.func.lower(User.city) == flt.city.lower())
        if flt and flt.religion is not None:
            conditions.append(User.religion == flt.religion)
        if flt and flt.active_recently_only:
            conditions.append(User.last_active_at >= utcnow() - timedelta(days=7))

        query = (
            sa.select(User)
            .where(*conditions)
            .order_by(User.is_premium.desc(), sa.func.random())
            .limit(1)
        )
        return await session.scalar(query)

    @staticmethod
    async def record_shown(
        session: AsyncSession, viewer: User, target: User, settings: Settings
    ) -> bool:
        existing = await session.scalar(
            sa.select(ProfileView).where(
                ProfileView.viewer_id == viewer.id, ProfileView.viewed_id == target.id
            )
        )
        if existing:
            return False
        usage = await DiscoveryService._get_usage(session, viewer.id, settings.app_timezone)
        usage.discoveries += 1
        session.add(ProfileView(viewer_id=viewer.id, viewed_id=target.id))
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return False
        return True

    @staticmethod
    async def like(
        session: AsyncSession, viewer: User, target: User, tz_name: str = "Africa/Addis_Ababa"
    ) -> LikeResult:
        if viewer.id == target.id:
            raise TargetUnavailableError("You cannot like your own profile.")
        if target.is_banned or not target.is_registered:
            raise TargetUnavailableError()

        blocked = await session.scalar(
            sa.select(Block).where(
                sa.or_(
                    sa.and_(Block.blocker_id == viewer.id, Block.blocked_id == target.id),
                    sa.and_(Block.blocker_id == target.id, Block.blocked_id == viewer.id),
                )
            )
        )
        if blocked:
            raise TargetUnavailableError()

        existing = await session.scalar(
            sa.select(Like).where(Like.from_user_id == viewer.id, Like.to_user_id == target.id)
        )
        if existing:
            return LikeResult(matched=False, already_liked=True)

        created = False
        try:
            async with session.begin_nested():
                session.add(Like(from_user_id=viewer.id, to_user_id=target.id))
                await session.flush()
            created = True
        except IntegrityError:
            created = False

        if not created:
            return LikeResult(matched=False, already_liked=True)

        view = await session.scalar(
            sa.select(ProfileView).where(
                ProfileView.viewer_id == viewer.id, ProfileView.viewed_id == target.id
            )
        )
        if view is None:
            session.add(
                ProfileView(viewer_id=viewer.id, viewed_id=target.id, action=ViewAction.LIKE)
            )
        else:
            view.action = ViewAction.LIKE

        usage = await DiscoveryService._get_usage(session, viewer.id, tz_name)
        usage.likes += 1

        mutual = await session.scalar(
            sa.select(Like).where(
                Like.from_user_id == target.id, Like.to_user_id == viewer.id
            )
        )
        match = None
        matched = False
        if mutual:
            match, is_new = await MatchService.get_or_create(session, viewer.id, target.id)
            matched = is_new

        await session.commit()
        return LikeResult(matched=matched, match=match if matched else None)

    @staticmethod
    async def pass_profile(session: AsyncSession, viewer: User, target: User) -> None:
        view = await session.scalar(
            sa.select(ProfileView).where(
                ProfileView.viewer_id == viewer.id, ProfileView.viewed_id == target.id
            )
        )
        if view is None:
            session.add(
                ProfileView(viewer_id=viewer.id, viewed_id=target.id, action=ViewAction.PASS)
            )
        else:
            view.action = ViewAction.PASS
        await session.commit()

    @staticmethod
    async def likes_received(
        session: AsyncSession, viewer: User, offset: int = 0, limit: int = 10
    ) -> tuple[list[User], int]:
        blocked_by_me = sa.select(Block.blocked_id).where(Block.blocker_id == viewer.id)
        blocked_me = sa.select(Block.blocker_id).where(Block.blocked_id == viewer.id)
        matched = sa.union(
            sa.select(Match.user_b_id.label("id")).where(
                Match.user_a_id == viewer.id, Match.is_active.is_(True)
            ),
            sa.select(Match.user_a_id.label("id")).where(
                Match.user_b_id == viewer.id, Match.is_active.is_(True)
            ),
        ).subquery()

        base_conditions = [
            Like.to_user_id == viewer.id,
            User.registration_completed_at.is_not(None),
            User.is_banned.is_(False),
            User.id.not_in(blocked_by_me),
            User.id.not_in(blocked_me),
            User.id.not_in(sa.select(matched.c.id)),
        ]
        total = int(
            await session.scalar(
                sa.select(sa.func.count())
                .select_from(Like)
                .join(User, User.id == Like.from_user_id)
                .where(*base_conditions)
            )
            or 0
        )
        result = await session.scalars(
            sa.select(User)
            .join(Like, Like.from_user_id == User.id)
            .where(*base_conditions)
            .order_by(Like.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.unique()), total

    @staticmethod
    async def get_filter(session: AsyncSession, user: User) -> UserFilter:
        if user.filter:
            return user.filter
        flt = UserFilter(user_id=user.id, min_age=18, max_age=60)
        user.filter = flt
        session.add(flt)
        await session.commit()
        return flt

    @staticmethod
    async def update_filter(session: AsyncSession, user: User, **fields) -> UserFilter:
        flt = await DiscoveryService.get_filter(session, user)
        if "min_age" in fields or "max_age" in fields:
            min_age = int(fields.get("min_age", flt.min_age))
            max_age = int(fields.get("max_age", flt.max_age))
            if min_age < 18 or max_age > 99 or min_age > max_age:
                raise ValidationError("Choose a valid age range between 18 and 99.")
            flt.min_age = min_age
            flt.max_age = max_age
        if "gender" in fields:
            gender = fields["gender"]
            flt.gender = Gender(gender) if gender else None
        if "city" in fields:
            city = fields["city"]
            flt.city = validate_city(city) if city else None
        if "religion" in fields:
            religion = fields["religion"]
            flt.religion = Religion(religion) if religion else None
        if "active_recently_only" in fields:
            flt.active_recently_only = bool(fields["active_recently_only"])
        await session.commit()
        return flt

    @staticmethod
    async def reset_filter(session: AsyncSession, user: User) -> UserFilter:
        return await DiscoveryService.update_filter(
            session,
            user,
            min_age=18,
            max_age=60,
            gender=None,
            religion=None,
            city=None,
            active_recently_only=False,
        )
