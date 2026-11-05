"""Admin statistics, premium entitlements, and daily limits."""

from __future__ import annotations

from datetime import timedelta

from app.services.admin import AdminService
from app.services.discovery import DiscoveryService
from app.services.premium import (
    PremiumService,
    daily_discovery_limit,
    has_premium,
    premium_until_text,
)
from app.utils.time import utcnow
from tests.conftest import make_user


async def test_admin_stats(session, settings) -> None:
    alice = await make_user(session, 4001, first_name="Alice")
    await make_user(session, 4002, first_name="Bob")
    await make_user(session, 4003, first_name="Unregistered", registered=False)
    banned = await make_user(session, 4004, first_name="Banned")
    banned.is_banned = True
    await session.commit()

    match, _ = await MatchService_get_or_create(session, alice.id, banned.id)
    await session.commit()

    stats = await AdminService.stats(session, settings)
    assert stats.total_users == 3
    assert stats.active_users == 3
    assert stats.daily_registrations == 3
    assert stats.monthly_registrations == 3
    assert stats.total_matches == 1
    assert stats.active_matches == 1
    assert stats.banned_users == 1
    assert stats.open_reports == 0


async def MatchService_get_or_create(session, first: int, second: int):
    from app.services.matches import MatchService

    return await MatchService.get_or_create(session, first, second)


async def test_admin_user_search(session) -> None:
    await make_user(session, 4010, first_name="Selam", city="Adama")
    await make_user(session, 4011, first_name="Dawit", city="Addis Ababa")

    users, total = await AdminService.list_users(session, query="selam")
    assert total == 1
    assert users[0].first_name == "Selam"

    users, total = await AdminService.list_users(session, query=str(4011))
    assert total == 1
    assert users[0].telegram_id == 4011

    users, total = await AdminService.list_users(session, query="%_DROP TABLE")
    assert total == 0


async def test_admin_log_action(session) -> None:
    await AdminService.log_action(session, 1, "test_action", None, "details")
    actions = await AdminService.recent_actions(session)
    assert len(actions) == 1
    assert actions[0].action == "test_action"


async def test_premium_launch_mode_unlocks_everything(session, settings) -> None:
    user = await make_user(session, 4020, is_premium=False)
    assert settings.premium_enabled is False
    assert has_premium(user, settings) is True
    assert daily_discovery_limit(user, settings) == settings.premium_daily_discoveries


async def test_premium_paywall_mode(session, premium_settings) -> None:
    free = await make_user(session, 4030, is_premium=False)
    premium = await make_user(session, 4031, is_premium=True)
    expired = await make_user(
        session,
        4032,
        is_premium=True,
        premium_until=utcnow() - timedelta(days=1),
    )

    assert has_premium(free, premium_settings) is False
    assert has_premium(premium, premium_settings) is True
    assert has_premium(expired, premium_settings) is False
    assert daily_discovery_limit(free, premium_settings) == premium_settings.free_daily_discoveries
    assert (
        daily_discovery_limit(premium, premium_settings)
        == premium_settings.premium_daily_discoveries
    )


async def test_grant_and_revoke_premium(session, premium_settings) -> None:
    user = await make_user(session, 4040, is_premium=False)
    await PremiumService.grant(session, user, days=30)
    assert user.is_premium is True
    assert user.premium_until is not None
    assert has_premium(user, premium_settings) is True
    assert premium_until_text(user) != "Lifetime / no expiry"

    await PremiumService.grant(session, user, days=30)
    assert has_premium(user, premium_settings) is True

    await PremiumService.revoke(session, user)
    assert user.is_premium is False
    assert user.premium_until is None
    assert has_premium(user, premium_settings) is False


async def test_premium_daily_limit(session, premium_settings) -> None:
    user = await make_user(session, 4050, is_premium=True)
    assert await DiscoveryService.remaining_discoveries(session, user, premium_settings) == (
        premium_settings.premium_daily_discoveries
    )
