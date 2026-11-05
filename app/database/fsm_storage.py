"""PostgreSQL/SQLite-backed aiogram FSM storage.

Vercel Functions are stateless between invocations and may handle updates for
the same chat on different instances. The default in-memory storage would lose
registration answers, chat drafts and admin flows, so the webhook entrypoint
uses this storage instead. It is also safe for local polling, which makes it
easy to test the exact production code path.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import sqlalchemy as sa
from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models import FsmState


def _encode_key(key: StorageKey) -> str:
    """Encode every StorageKey component without collisions.

    Telegram IDs are numeric, while thread and business connection identifiers
    are optional. ``""`` is used as the null marker because it cannot appear in
    a numeric ID or a Telegram business connection identifier.
    """
    return ":".join(
        (
            str(key.bot_id),
            str(key.chat_id),
            str(key.user_id),
            "" if key.thread_id is None else str(key.thread_id),
            key.business_connection_id or "",
            key.destiny,
        )
    )


class DatabaseStorage(BaseStorage):
    """Durable FSM storage using the application's async session factory."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory
        bind = session_factory.kw.get("bind")
        self.dialect = getattr(getattr(bind, "dialect", None), "name", "sqlite")

    async def close(self) -> None:
        # Connections are owned by the engine; nothing to close per storage.
        return None

    async def get_state(self, key: StorageKey) -> str | None:
        async with self.session_factory() as session:
            row = await session.get(FsmState, _encode_key(key))
            return row.state if row is not None else None

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        async with self.session_factory() as session:
            row = await session.get(FsmState, _encode_key(key))
            return dict(row.data or {}) if row is not None else {}

    async def set_state(self, key: StorageKey, state: Any = None) -> None:
        value = state.state if isinstance(state, State) else state
        await self._upsert(key, {"state": value})

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        if not isinstance(data, dict):
            msg = f"Data must be a dict or dict-like object, got {type(data).__name__}"
            raise TypeError(msg)
        await self._upsert(key, {"data": dict(data)})

    async def _upsert(self, key: StorageKey, values: dict[str, Any]) -> None:
        db_key = _encode_key(key)
        payload = {"key": db_key, **values, "updated_at": sa.func.now()}

        async with self.session_factory() as session:
            if self.dialect == "postgresql":
                from sqlalchemy.dialects.postgresql import insert as dialect_insert
            elif self.dialect == "sqlite":
                from sqlalchemy.dialects.sqlite import insert as dialect_insert
            else:  # pragma: no cover - only PostgreSQL and SQLite are supported
                await self._generic_upsert(session, db_key, values)
                return

            stmt = dialect_insert(FsmState).values(**payload)
            update = {
                column: getattr(stmt.excluded, column)
                for column in values
            }
            update["updated_at"] = sa.func.now()
            stmt = stmt.on_conflict_do_update(index_elements=[FsmState.key], set_=update)
            await session.execute(stmt)
            await session.commit()

    async def _generic_upsert(
        self, session: AsyncSession, db_key: str, values: dict[str, Any]
    ) -> None:  # pragma: no cover - fallback for exotic dialects
        row = await session.get(FsmState, db_key)
        if row is None:
            session.add(FsmState(key=db_key, **values))
        else:
            for column, value in values.items():
                setattr(row, column, value)
        await session.commit()
