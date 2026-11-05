"""Validators and safety filters."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.utils.time import calculate_age, shift_years
from app.utils.validators import (
    ValidationError,
    contains_contact_info,
    parse_birth_date,
    validate_bio,
    validate_city,
    validate_first_name,
    validate_interests,
    validate_message_text,
    validate_photo_count,
)


def test_parse_birth_date_accepts_common_formats() -> None:
    assert parse_birth_date("14/02/1996") == date(1996, 2, 14)
    assert parse_birth_date("14-02-1996") == date(1996, 2, 14)
    assert parse_birth_date("1996-02-14") == date(1996, 2, 14)


def test_parse_birth_date_rejects_underage() -> None:
    too_young = shift_years(date.today(), -17)
    with pytest.raises(ValidationError, match="18"):
        parse_birth_date(too_young.strftime("%d/%m/%Y"))


def test_parse_birth_date_rejects_future() -> None:
    tomorrow = date.today() + timedelta(days=1)
    with pytest.raises(ValidationError):
        parse_birth_date(tomorrow.strftime("%d/%m/%Y"))


def test_parse_birth_date_rejects_garbage() -> None:
    with pytest.raises(ValidationError):
        parse_birth_date("not a date")


def test_calculate_age_birthday_not_yet_reached() -> None:
    today = date(2026, 11, 5)
    assert calculate_age(date(1996, 11, 6), today) == 29
    assert calculate_age(date(1996, 11, 5), today) == 30


def test_first_name_validation() -> None:
    assert validate_first_name("  Abebe   Bekele ") == "Abebe Bekele"
    for bad in ("", "A", "Abebe http://x.com", "Abebe @username", "12345"):
        with pytest.raises(ValidationError):
            validate_first_name(bad)


def test_city_and_bio_validation() -> None:
    assert validate_city(" Addis Ababa ") == "Addis Ababa"
    with pytest.raises(ValidationError):
        validate_city("A")
    assert validate_bio("I love music and coffee.") == "I love music and coffee."
    with pytest.raises(ValidationError):
        validate_bio("short")
    with pytest.raises(ValidationError):
        validate_bio("x" * 501)


def test_interests_are_filtered_and_deduplicated() -> None:
    assert validate_interests(["music", "Music", "unknown", "travel"]) == ["music", "travel"]
    with pytest.raises(ValidationError):
        validate_interests([])
    with pytest.raises(ValidationError):
        validate_interests(["music"] * 1 + [k for k in ("coffee", "travel", "movies", "books", "fitness", "cooking", "nature", "football", "art")])


def test_validate_photo_count() -> None:
    validate_photo_count(1)
    validate_photo_count(3)
    with pytest.raises(ValidationError):
        validate_photo_count(0)
    with pytest.raises(ValidationError):
        validate_photo_count(4)


def test_message_validation() -> None:
    assert validate_message_text("  hello   there ") == "hello there"
    with pytest.raises(ValidationError):
        validate_message_text("   ")
    with pytest.raises(ValidationError):
        validate_message_text("x" * 2001)


@pytest.mark.parametrize(
    "value",
    [
        "call me on +251 911 123 456",
        "my email is abebe@example.com",
        "follow me @abebe_official",
        "visit https://example.com",
        "t.me/something",
    ],
)
def test_contact_info_is_blocked(value: str) -> None:
    assert contains_contact_info(value) is True


@pytest.mark.parametrize(
    "value",
    [
        "I love coffee and long walks.",
        "Let's meet at 6pm near the square.",
        "I am 25 years old.",
        "My favourite film is 12 Angry Men.",
    ],
)
def test_normal_text_is_allowed(value: str) -> None:
    assert contains_contact_info(value) is False
