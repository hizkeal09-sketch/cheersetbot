"""Discovery filters, daily limits, likes, and received likes."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
import sqlalchemy as sa

from app.constants import Gender, Preference, ReportReason, ViewAction
from app.database.models import DailyUsage, Match, ProfileView
from app.services.discovery import DiscoveryService
from app.services.errors import DailyLimitReached, ProfilePausedError
from app.services.moderation import ModerationService
from app.utils.time import local_today
from tests.conftest import make_user


async def test_candidate_respects_gender_and_reciprocal_preference(session, settings) -> None:
    viewer = await make_user(
        session, 2001, gender=Gender.MAN, interested_in=Preference.WOMEN
    )
    matching_woman = await make_user(
        session, 2002, first_name="Hanna", gender=Gender.WOMAN, interested_in=Preference.MEN
    )
    woman_not_interested = await make_user(
        session, 2003, first_name="Liya", gender=Gender.WOMAN, interested_in=Preference.WOMEN
    )
    await make_user(
        session, 2004, first_name="Dawit", gender=Gender.MAN, interested_in=Preference.WOMEN
    )

    candidate = await DiscoveryService.get_next_candidate(session, viewer, settings)
    assert candidate is not None
    assert candidate.id == matching_woman.id
    assert candidate.id != woman_not_interested.id


async def test_candidate_respects_age_range_and_city(session, settings) -> None:
    viewer = await make_user(session, 2010, city="Addis Ababa")
    too_young = await make_user(
        session, 2011, birth_date=date.today() - timedelta(days=365 * 19), city="Addis Ababa", gender=Gender.WOMAN, interested_in=Preference.MEN
    )
    too_old = await make_user(
        session, 2012, birth_date=date.today() - timedelta(days=365 * 55), city="Addis Ababa", gender=Gender.WOMAN, interested_in=Preference.MEN
    )
    other_city = await make_user(session, 2013, city="Hawassa", gender=Gender.WOMAN, interested_in=Preference.MEN)
    perfect = await make_user(
        session, 2014, birth_date=date.today() - timedelta(days=365 * 30), city="Addis Ababa", gender=Gender.WOMAN, interested_in=Preference.MEN
    )

    await DiscoveryService.update_filter(session, viewer, min_age=25, max_age=35, city="Addis Ababa")
    candidate = await DiscoveryService.get_next_candidate(session, viewer, settings)
    assert candidate is not None
    assert candidate.id == perfect.id
    assert candidate.id not in {too_young.id, too_old.id, other_city.id}


async def test_seen_profiles_are_not_repeated(session, settings) -> None:
    viewer = await make_user(session, 2020)
    target = await make_user(session, 2021, gender=Gender.WOMAN, interested_in=Preference.MEN)
    assert (await DiscoveryService.get_next_candidate(session, viewer, settings)).id == target.id

    recorded = await DiscoveryService.record_shown(session, viewer, target, settings)
    assert recorded is True
    assert await DiscoveryService.get_next_candidate(session, viewer, settings) is None


async def test_record_shown_twice_does_not_double_count(session, settings) -> None:
    viewer = await make_user(session, 2022)
    target = await make_user(session, 2023)

    assert await DiscoveryService.record_shown(session, viewer, target, settings) is True
    assert await DiscoveryService.record_shown(session, viewer, target, settings) is False

    usage = await session.scalar(
        sa.select(DailyUsage).where(
            DailyUsage.user_id == viewer.id,
            DailyUsage.usage_date == local_today(settings.app_timezone),
        )
    )
    assert usage is not None
    assert usage.discoveries == 1


async def test_daily_limit_is_enforced(session, premium_settings) -> None:
    settings = premium_settings
    viewer = await make_user(session, 2030)
    await make_user(session, 2031)
    session.add(
        DailyUsage(
            user_id=viewer.id,
            usage_date=local_today(settings.app_timezone),
            discoveries=settings.free_daily_discoveries,
        )
    )
    await session.commit()

    with pytest.raises(DailyLimitReached):
        await DiscoveryService.get_next_candidate(session, viewer, settings)

    remaining = await DiscoveryService.remaining_discoveries(session, viewer, settings)
    assert remaining == 0


async def test_paused_profile_cannot_discover(session, settings) -> None:
    viewer = await make_user(session, 2032, profile_paused=True)
    await make_user(session, 2033)
    with pytest.raises(ProfilePausedError):
        await DiscoveryService.get_next_candidate(session, viewer, settings)


async def test_blocked_and_reported_users_are_excluded(session, settings) -> None:
    viewer = await make_user(session, 2040)
    blocked = await make_user(session, 2041, gender=Gender.WOMAN, interested_in=Preference.MEN)
    reported = await make_user(session, 2042, gender=Gender.WOMAN, interested_in=Preference.MEN)
    allowed = await make_user(session, 2043, gender=Gender.WOMAN, interested_in=Preference.MEN)

    await ModerationService.block_user(session, viewer, blocked.id)
    await ModerationService.report_user(session, viewer, reported.id, ReportReason.SPAM)

    candidate = await DiscoveryService.get_next_candidate(session, viewer, settings)
    assert candidate is not None
    assert candidate.id == allowed.id


async def test_like_is_idempotent_and_creates_match_on_mutual_like(session, settings) -> None:
    alice = await make_user(session, 2050, first_name="Alice")
    bob = await make_user(session, 2051, first_name="Bob")

    first = await DiscoveryService.like(session, alice, bob, settings.app_timezone)
    assert first.matched is False
    assert first.already_liked is False

    duplicate = await DiscoveryService.like(session, alice, bob, settings.app_timezone)
    assert duplicate.already_liked is True
    assert duplicate.matched is False

    reverse = await DiscoveryService.like(session, bob, alice, settings.app_timezone)
    assert reverse.matched is True
    assert reverse.match is not None

    match = await session.scalar(sa.select(Match))
    assert match is not None
    assert match.is_active is True
    assert {match.user_a_id, match.user_b_id} == {alice.id, bob.id}

    # A mutual match leaves the likes inbox.
    people, total = await DiscoveryService.likes_received(session, alice)
    assert total == 0
    assert people == []


async def test_pass_marks_profile_seen(session, settings) -> None:
    viewer = await make_user(session, 2060)
    target = await make_user(session, 2061)
    await DiscoveryService.pass_profile(session, viewer, target)

    view = await session.scalar(
        sa.select(ProfileView).where(
            ProfileView.viewer_id == viewer.id, ProfileView.viewed_id == target.id
        )
    )
    assert view is not None
    assert view.action == ViewAction.PASS
    assert await DiscoveryService.get_next_candidate(session, viewer, settings) is None


async def test_likes_received_excludes_blocked_people(session, settings) -> None:
    viewer = await make_user(session, 2070)
    admirer = await make_user(session, 2071)
    blocked_admirer = await make_user(session, 2072)

    await DiscoveryService.like(session, admirer, viewer, settings.app_timezone)
    await DiscoveryService.like(session, blocked_admirer, viewer, settings.app_timezone)
    await ModerationService.block_user(session, viewer, blocked_admirer.id)

    people, total = await DiscoveryService.likes_received(session, viewer)
    assert total == 1
    assert [person.id for person in people] == [admirer.id]


async def test_auto_opposite_sex_man_sees_women(session, settings) -> None:
    """Man looking for women sees women by default."""
    viewer = await make_user(
        session, 2101, gender=Gender.MAN, interested_in=Preference.WOMEN
    )
    woman = await make_user(
        session, 2102, first_name="Hanna", gender=Gender.WOMAN, interested_in=Preference.MEN
    )
    man = await make_user(
        session, 2103, first_name="Dawit", gender=Gender.MAN, interested_in=Preference.WOMEN
    )

    candidate = await DiscoveryService.get_next_candidate(session, viewer, settings)
    assert candidate is not None
    assert candidate.id == woman.id
    assert candidate.id != man.id


async def test_auto_opposite_sex_woman_sees_men(session, settings) -> None:
    """Woman looking for men sees men by default."""
    viewer = await make_user(
        session, 2111, gender=Gender.WOMAN, interested_in=Preference.MEN
    )
    man = await make_user(
        session, 2112, first_name="Dawit", gender=Gender.MAN, interested_in=Preference.WOMEN
    )
    woman = await make_user(
        session, 2113, first_name="Hanna", gender=Gender.WOMAN, interested_in=Preference.MEN
    )

    candidate = await DiscoveryService.get_next_candidate(session, viewer, settings)
    assert candidate is not None
    assert candidate.id == man.id
    assert candidate.id != woman.id


async def test_auto_opposite_sex_respects_explicit_preference(session, settings) -> None:
    """Explicit interested_in overrides auto opposite-sex."""
    viewer = await make_user(
        session, 2121, gender=Gender.MAN, interested_in=Preference.MEN
    )
    man = await make_user(
        session, 2122, first_name="Dawit", gender=Gender.MAN, interested_in=Preference.MEN
    )
    woman = await make_user(
        session, 2123, first_name="Hanna", gender=Gender.WOMAN, interested_in=Preference.WOMEN
    )

    candidate = await DiscoveryService.get_next_candidate(session, viewer, settings)
    assert candidate is not None
    assert candidate.id == man.id
    assert candidate.id != woman.id
