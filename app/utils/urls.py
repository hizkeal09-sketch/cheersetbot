"""Database URL helpers.

Neon (and most managed PostgreSQL providers) hand out libpq-style URLs such as::

    postgresql://user:pass@host/db?sslmode=require&channel_binding=require

SQLAlchemy's asyncpg dialect needs ``postgresql+asyncpg://`` and asyncpg accepts
``ssl=require`` instead of the libpq ``sslmode`` parameter. ``channel_binding``
is negotiated by asyncpg automatically, so we drop it. Normalising here means
``.env`` values pasted straight from the Neon console work without edits.
"""

from __future__ import annotations

_POSTGRES_PREFIXES = ("postgresql://", "postgres://")


def normalize_database_url(url: str) -> str:
    """Return an asyncpg-compatible SQLAlchemy database URL."""
    url = (url or "").strip()
    if not url:
        return url

    for prefix in _POSTGRES_PREFIXES:
        if url.startswith(prefix):
            url = "postgresql+asyncpg://" + url[len(prefix) :]
            break

    base, separator, query = url.partition("?")
    if not separator:
        return url

    params: dict[str, str] = {}
    for chunk in query.split("&"):
        if not chunk:
            continue
        key, _, value = chunk.partition("=")
        if key == "channel_binding":
            # asyncpg negotiates SCRAM channel binding on its own.
            continue
        if key == "sslmode":
            key = "ssl"
        params[key] = value

    if not params:
        return base
    return base + "?" + "&".join(f"{key}={value}" for key, value in params.items())
