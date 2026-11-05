"""Async database engine and session management."""

from __future__ import annotations

import logging

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, StaticPool

from app.database.base import Base
from app.utils.urls import normalize_database_url

logger = logging.getLogger(__name__)


def create_engine(
    database_url: str, *, echo: bool = False, serverless: bool = False
) -> AsyncEngine:
    database_url = normalize_database_url(database_url)
    kwargs: dict = {"echo": echo, "pool_pre_ping": True, "future": True}

    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"timeout": 30}
        if ":memory:" in database_url:
            kwargs["poolclass"] = StaticPool
        engine = create_async_engine(database_url, **kwargs)

        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record):  # pragma: no cover
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        return engine

    if serverless:
        # Vercel Functions are short-lived and may scale horizontally. Holding
        # pooled connections would exhaust Neon's connection limit, so check out
        # a connection per request. Neon's pooled endpoint sits in front of
        # PgBouncer, which requires server-side prepared statements to be
        # disabled.
        kwargs["poolclass"] = NullPool
        kwargs["connect_args"] = {
            "prepared_statement_cache_size": 0,
            "statement_cache_size": 0,
        }

    return create_async_engine(database_url, **kwargs)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def init_models(engine: AsyncEngine) -> None:
    """Create tables directly. Used by tests and optional AUTO_CREATE_TABLES."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def verify_schema(engine: AsyncEngine) -> bool:
    async with engine.connect() as conn:
        return bool(await conn.run_sync(lambda sync_conn: sa.inspect(sync_conn).has_table("users")))
