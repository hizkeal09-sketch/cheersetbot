"""Dispatcher factory shared by the runtime and test suite."""

from __future__ import annotations

from aiogram import Dispatcher
from aiogram.filters import BaseFilter
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject
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


class AdminRouteFilter(BaseFilter):
    def __init__(self, admin_ids: set[int]) -> None:
        self.admin_ids = admin_ids

    async def __call__(self, event: TelegramObject) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user and user.id in self.admin_ids)


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

    # Admin routers are isolated by ID filters (defence-in-depth also exists in
    # the router middleware). aiogram stores router-level filters on the
    # observer's root handler, so clear them to keep repeated factory calls safe
    # and to avoid stale admin IDs between test runs.
    for observer in (admin.router.message, admin.router.callback_query):
        observer._handler.filters.clear()
        observer.filter(AdminRouteFilter(settings.admin_id_list))

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
