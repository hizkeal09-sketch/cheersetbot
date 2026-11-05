"""Dispatcher factory shared by the runtime and test suite."""

from __future__ import annotations

from aiogram import Dispatcher
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.handlers import (
    admin,
    common,
    discovery,
    fallback,
    matches,
    messaging,
    premium,
    profile,
    registration,
    safety,
)
from app.handlers import (
    settings as settings_handlers,
)
from app.middlewares import (
    DatabaseSessionMiddleware,
    RegistrationGateMiddleware,
    ThrottlingMiddleware,
    UserMiddleware,
    error_handler,
)


def create_dispatcher(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    storage: BaseStorage | None = None,
) -> Dispatcher:
    if storage is None and settings.is_serverless:
        raise RuntimeError(
            "Serverless mode requires persistent FSM storage; pass a DatabaseStorage instance."
        )
    dp = Dispatcher(storage=storage or MemoryStorage())
    dp["settings"] = settings
    dp["session_factory"] = session_factory

    dp.update.outer_middleware(DatabaseSessionMiddleware(session_factory))
    for observer in (dp.message, dp.callback_query):
        observer.outer_middleware(UserMiddleware(settings))
        observer.outer_middleware(ThrottlingMiddleware(settings))
        observer.outer_middleware(RegistrationGateMiddleware(settings))

    # Admin access is enforced by AdminOnlyMiddleware on the admin router,
    # which sends a clear "administrators only" message instead of silently
    # dropping the update.

    dp.include_routers(
        admin.router,
        common.router,
        registration.router,
        profile.router,
        discovery.router,
        matches.router,
        safety.router,
        settings_handlers.router,
        premium.router,
        messaging.router,
        fallback.router,
    )
    dp.errors.register(error_handler)
    return dp
