"""Time and date helpers (all timestamps are stored in UTC)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime | None) -> datetime | None:
    """Normalize datetimes coming back from SQLite (which drops tzinfo)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def local_today(tz_name: str = "Africa/Addis_Ababa") -> date:
    try:
        return datetime.now(ZoneInfo(tz_name)).date()
    except Exception:  # pragma: no cover - bad timezone configuration fallback
        return datetime.now(UTC).date()


def calculate_age(birth_date: date, today: date | None = None) -> int:
    today = today or date.today()
    return (
        today.year
        - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day))
    )


def shift_years(value: date, years: int) -> date:
    """Shift a date by N years, clamping 29 February to 28 February."""
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, month=2, day=28)


def birth_date_bounds(min_age: int, max_age: int) -> tuple[date, date]:
    """Return inclusive birth-date bounds for an age range.

    ``min_age=18`` means the person must already have turned 18 today.
    ``max_age=35`` includes people who turn 36 tomorrow.
    """
    today = date.today()
    if min_age < 0 or max_age < min_age:
        raise ValueError("Invalid age range")
    newest_allowed_birth_date = shift_years(today, -max_age - 1) + timedelta(days=1)
    oldest_allowed_birth_date = shift_years(today, -min_age)
    return oldest_allowed_birth_date, newest_allowed_birth_date
