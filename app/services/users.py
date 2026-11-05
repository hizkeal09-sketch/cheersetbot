"""User registration, profile updates, and account lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

import sqlalchemy as sa
from aiogram.types import User as TelegramUser
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import Gender, Intention, Preference
from app.database.models import Block, User, UserFilter, UserPhoto
from app.services.errors import InvalidTargetError, NotRegisteredError
from app.utils.time import as_utc, calculate_age, utcnow
from app.utils.validators import (
    ValidationError,
    validate_bio,
    validate_city,
    validate_first_name,
    validate_interests,
    validate_photo_count,
)


@dataclass
class RegistrationData:
    first_name: str
    birth_date: date
    gender: Gender
    interested_in: Preference
    city: str
    intention: Intention
    interests: list[str] = field(default_factory=list)
    bio: str | None = None
    photos: list[str] = field(default_factory=list)
    latitude: float | None = None
    longitude: float | None = None
    consent_at: datetime | None = None


class UserService:
    @staticmethod
    async def get_or_create(session: AsyncSession, tg_user: TelegramUser) -> User:
        user = await session.scalar(sa.select(User).where(User.telegram_id == tg_user.id))
        if user:
            username = (tg_user.username or "")[:64] or None
            if user.username != username:
                user.username = username
            return user

        display_name = (tg_user.first_name or "Friend").strip()[:64] or "Friend"
        user = User(
            telegram_id=tg_user.id,
            username=(tg_user.username or "")[:64] or None,
            first_name=display_name,
            last_active_at=utcnow(),
        )
        session.add(user)
        try:
            await session.commit()
        except IntegrityError:
            # Concurrent /start from two devices: the unique constraint wins.
            await session.rollback()
            user = await session.scalar(sa.select(User).where(User.telegram_id == tg_user.id))
            if user is None:
                raise
        return user

    @staticmethod
    async def get_by_id(session: AsyncSession, user_id: int) -> User:
        user = await session.get(User, user_id)
        if user is None:
            raise InvalidTargetError()
        return user

    @staticmethod
    async def touch(session: AsyncSession, user: User, *, force: bool = False) -> None:
        now = utcnow()
        last = as_utc(user.last_active_at)
        if force or last is None or (now - last).total_seconds() > 300:
            user.last_active_at = now

    @staticmethod
    async def complete_registration(
        session: AsyncSession, user: User, data: RegistrationData
    ) -> User:
        # Relationships may be unloaded (for example right after get_or_create).
        # Refresh them explicitly so no lazy IO happens outside the async context.
        await session.refresh(user, ["photos", "filter"])

        # Re-validate in the service so handlers cannot bypass the rules.
        first_name = validate_first_name(data.first_name)
        city = validate_city(data.city)
        interests = validate_interests(data.interests)
        bio = validate_bio(data.bio) if data.bio else None
        validate_photo_count(len(data.photos))
        if data.birth_date > date.today():
            raise ValidationError("Date of birth cannot be in the future.")

        user.first_name = first_name
        user.birth_date = data.birth_date
        user.gender = data.gender
        user.interested_in = data.interested_in
        user.city = city
        user.latitude = data.latitude
        user.longitude = data.longitude
        user.bio = bio
        user.interests = interests
        user.intention = data.intention
        user.consent_at = data.consent_at or user.consent_at or utcnow()
        user.registration_completed_at = user.registration_completed_at or utcnow()
        user.is_active = True
        user.profile_paused = False

        await UserService._set_photos(session, user, data.photos)

        if user.filter is None:
            user.filter = UserFilter(min_age=18, max_age=60)
        user.filter.min_age = 18
        user.filter.max_age = 60

        await session.commit()
        return user

    @staticmethod
    async def update_profile(session: AsyncSession, user: User, **fields) -> User:
        if "first_name" in fields:
            user.first_name = validate_first_name(fields["first_name"])
        if "birth_date" in fields:
            birth_date = fields["birth_date"]
            if not isinstance(birth_date, date):
                raise ValidationError("Invalid date of birth.")
            if birth_date > date.today() or calculate_age(birth_date) < 18:
                raise ValidationError("You must be at least 18 years old to use Cheers Dating.")
            user.birth_date = birth_date
        if "gender" in fields and fields["gender"] is not None:
            user.gender = Gender(fields["gender"])
        if "interested_in" in fields and fields["interested_in"] is not None:
            user.interested_in = Preference(fields["interested_in"])
        if "city" in fields:
            user.city = validate_city(fields["city"])
        if "bio" in fields:
            user.bio = validate_bio(fields["bio"]) if fields["bio"] else None
        if "interests" in fields:
            user.interests = validate_interests(list(fields["interests"]))
        if "intention" in fields and fields["intention"] is not None:
            user.intention = Intention(fields["intention"])
        if "latitude" in fields:
            user.latitude = fields["latitude"]
        if "longitude" in fields:
            user.longitude = fields["longitude"]
        if "language" in fields:
            user.language = fields["language"]
        await session.commit()
        return user

    @staticmethod
    async def _set_photos(session: AsyncSession, user: User, file_ids: list[str]) -> None:
        """Replace photos safely.

        Old rows are flushed before the new rows are inserted, otherwise the
        unique constraint on (user_id, position) can fire depending on the
        unit-of-work ordering.
        """
        if user.photos:
            user.photos.clear()
            await session.flush()
        for index, file_id in enumerate(file_ids[:3]):
            user.photos.append(UserPhoto(file_id=file_id, position=index))

    @staticmethod
    async def replace_photos(session: AsyncSession, user: User, file_ids: list[str]) -> User:
        validate_photo_count(len(file_ids))
        await session.refresh(user, ["photos"])
        await UserService._set_photos(session, user, file_ids)
        await session.commit()
        return user

    @staticmethod
    async def set_paused(session: AsyncSession, user: User, paused: bool) -> User:
        user.profile_paused = paused
        await session.commit()
        return user

    @staticmethod
    async def delete_account(session: AsyncSession, user: User) -> None:
        # Remove blocks first so both directions release immediately even on
        # databases where FK cascades are unavailable.
        await session.execute(
            sa.delete(Block).where((Block.blocker_id == user.id) | (Block.blocked_id == user.id))
        )
        await session.delete(user)
        await session.commit()

    @staticmethod
    def ensure_registered(user: User) -> None:
        if not user.is_registered:
            raise NotRegisteredError()

    @staticmethod
    async def count_registered(session: AsyncSession) -> int:
        return int(
            await session.scalar(
                sa.select(sa.func.count())
                .select_from(User)
                .where(User.registration_completed_at.is_not(None))
            )
            or 0
        )
