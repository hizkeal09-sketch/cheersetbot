"""Shared pytest fixtures: in-memory SQLite + factory helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date

import pytest
import pytest_asyncio
import sqlalchemy as sa
from aiogram.types import User as TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.constants import Gender, Intention, Preference
from app.database.base import Base
from app.database.models import User
from app.database.session import create_engine, create_session_factory


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        bot_token="123456:TEST_TOKEN",
        database_url="sqlite+aiosqlite:///:memory:",
        admin_ids="1",
        environment="test",
        log_file=None,
        premium_enabled=False,
        free_daily_discoveries=30,
        premium_daily_discoveries=300,
    )


@pytest.fixture
def premium_settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"premium_enabled": True})


@pytest_asyncio.fixture
async def engine():
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


@pytest_asyncio.fixture
async def session(session_factory) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


async def make_user(
    session: AsyncSession,
    telegram_id: int,
    *,
    first_name: str = "Test",
    registered: bool = True,
    **kwargs,
) -> User:
    """Create a user row directly; defaults make them discoverable."""
    from datetime import UTC, datetime

    user = User(
        telegram_id=telegram_id,
        username=kwargs.pop("username", None),
        first_name=first_name,
        birth_date=kwargs.pop("birth_date", date(1995, 5, 20)),
        gender=kwargs.pop("gender", Gender.MAN),
        interested_in=kwargs.pop("interested_in", Preference.WOMEN),
        city=kwargs.pop("city", "Addis Ababa"),
        bio=kwargs.pop("bio", "A friendly test profile."),
        interests=kwargs.pop("interests", ["music"]),
        intention=kwargs.pop("intention", Intention.SERIOUS),
        registration_completed_at=(
            kwargs.pop("registration_completed_at", datetime.now(UTC)) if registered else None
        ),
        last_active_at=kwargs.pop("last_active_at", datetime.now(UTC)),
        **kwargs,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def tg_user(telegram_id: int, first_name: str = "Test") -> TelegramUser:
    return TelegramUser(id=telegram_id, is_bot=False, first_name=first_name)


async def count(session: AsyncSession, model) -> int:
    return int(await session.scalar(sa.select(sa.func.count()).select_from(model)) or 0)
