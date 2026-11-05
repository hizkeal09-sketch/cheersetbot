"""Registration, profile updates, and account lifecycle."""

from __future__ import annotations

from datetime import date

import pytest

from app.constants import Gender, Intention, Preference, Religion
from app.database.models import Block, Match, User, UserFilter, UserPhoto
from app.services.users import RegistrationData, UserService
from app.utils.validators import ValidationError
from tests.conftest import count, make_user, tg_user


def registration_data(**overrides) -> RegistrationData:
    values = dict(
        first_name="Selam",
        birth_date=date(1997, 3, 12),
        gender=Gender.WOMAN,
        religion=Religion.ORTHODOX,
        interested_in=Preference.MEN,
        city="Addis Ababa",
        intention=Intention.SERIOUS,
        interests=["music", "coffee"],
        bio="I enjoy live music and good coffee.",
        photos=["photo-1", "photo-2"],
    )
    values.update(overrides)
    return RegistrationData(**values)


async def test_get_or_create_is_idempotent(session) -> None:
    first = await UserService.get_or_create(session, tg_user(1001, "Selam"))
    second = await UserService.get_or_create(session, tg_user(1001, "Selam Updated"))
    assert first.id == second.id
    assert await count(session, User) == 1
    assert second.first_name == "Selam"


async def test_complete_registration_creates_profile_and_filter(session) -> None:
    user = await UserService.get_or_create(session, tg_user(1002))
    user = await UserService.complete_registration(session, user, registration_data())

    assert user.is_registered is True
    assert user.first_name == "Selam"
    assert user.gender == Gender.WOMAN
    assert user.interested_in == Preference.MEN
    assert user.intention == Intention.SERIOUS
    assert user.is_active is True
    assert user.profile_paused is False
    assert [p.file_id for p in user.photos] == ["photo-1", "photo-2"]
    assert user.filter is not None
    assert user.filter.min_age == 18
    assert user.filter.max_age == 60


async def test_complete_registration_rejects_invalid_payload(session) -> None:
    user = await UserService.get_or_create(session, tg_user(1003))
    with pytest.raises(ValidationError):
        await UserService.complete_registration(
            session, user, registration_data(photos=[])
        )
    assert user.is_registered is False


async def test_replace_photos_keeps_positions_unique(session) -> None:
    user = await UserService.get_or_create(session, tg_user(1004))
    user = await UserService.complete_registration(session, user, registration_data())
    user = await UserService.replace_photos(session, user, ["new-a", "new-b", "new-c"])
    assert [p.file_id for p in user.photos] == ["new-a", "new-b", "new-c"]
    assert [p.position for p in user.photos] == [0, 1, 2]
    assert await count(session, UserPhoto) == 3


async def test_update_profile_validates_and_persists(session) -> None:
    user = await UserService.get_or_create(session, tg_user(1005))
    user = await UserService.complete_registration(session, user, registration_data())

    user = await UserService.update_profile(
        session, user, first_name="Marta", city="Hawassa", bio="New bio for testing."
    )
    assert user.first_name == "Marta"
    assert user.city == "Hawassa"
    assert user.bio == "New bio for testing."

    with pytest.raises(ValidationError):
        await UserService.update_profile(session, user, first_name="X")


async def test_update_profile_rejects_underage_birth_date(session) -> None:
    user = await UserService.get_or_create(session, tg_user(1009))
    user = await UserService.complete_registration(session, user, registration_data())

    underage = date.today().replace(year=date.today().year - 17)
    with pytest.raises(ValidationError):
        await UserService.update_profile(session, user, birth_date=underage)

    with pytest.raises(ValidationError):
        await UserService.update_profile(session, user, birth_date=date(2099, 1, 1))


async def test_delete_account_removes_data(session) -> None:
    alice = await UserService.get_or_create(session, tg_user(1006))
    alice = await UserService.complete_registration(session, alice, registration_data())
    bob = await make_user(session, 1007, city="Addis Ababa")

    session.add(Block(blocker_id=alice.id, blocked_id=bob.id))
    session.add(
        Match(
            user_a_id=min(alice.id, bob.id),
            user_b_id=max(alice.id, bob.id),
        )
    )
    await session.commit()

    await UserService.delete_account(session, alice)

    assert await count(session, User) == 1
    assert await count(session, UserPhoto) == 0
    assert await count(session, UserFilter) == 0
    assert await count(session, Block) == 0
    assert await count(session, Match) == 0


async def test_pause_and_resume(session) -> None:
    user = await make_user(session, 1008)
    await UserService.set_paused(session, user, True)
    assert user.profile_paused is True
    await UserService.set_paused(session, user, False)
    assert user.profile_paused is False
