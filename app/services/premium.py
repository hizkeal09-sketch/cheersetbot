"""Premium entitlement and plan limits."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database.models import User
from app.utils.time import as_utc, utcnow


def has_premium(user: User, settings: Settings) -> bool:
    """Launch mode unlocks premium features when monetization is disabled."""
    if not settings.premium_enabled:
        return True
    if not user.is_premium:
        return False
    if user.premium_until is None:
        return True
    return as_utc(user.premium_until) > utcnow()


def daily_discovery_limit(user: User, settings: Settings) -> int:
    if has_premium(user, settings):
        return settings.premium_daily_discoveries
    return settings.free_daily_discoveries


def premium_until_text(user: User) -> str:
    until = as_utc(user.premium_until)
    if user.is_premium and until:
        return until.strftime("%d %b %Y")
    return "Lifetime / no expiry"


class PremiumService:
    @staticmethod
    async def grant(session: AsyncSession, user: User, days: int = 30) -> User:
        base = as_utc(user.premium_until)
        now = utcnow()
        base = base if base and base > now else now
        user.is_premium = True
        user.premium_until = base + timedelta(days=days)
        await session.commit()
        return user

    @staticmethod
    async def revoke(session: AsyncSession, user: User) -> User:
        user.is_premium = False
        user.premium_until = None
        await session.commit()
        return user
