"""Input validation and safety helpers."""

from __future__ import annotations

import re
from datetime import date

from app.constants import (
    INTERESTS,
    MAX_BIO_LENGTH,
    MAX_MESSAGE_LENGTH,
    MAX_PHOTOS,
    MAX_REPORT_DETAILS,
)
from app.utils.time import calculate_age

CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
URL_RE = re.compile(r"(https?://|www\.|t\.me/|telegram\.me/)", re.IGNORECASE)
USERNAME_RE = re.compile(r"(?<![\w@])@[A-Za-z][A-Za-z0-9_]{3,}", re.UNICODE)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]{2,}", re.UNICODE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)", re.UNICODE)
DIGITS_ONLY_RE = re.compile(r"\D+")

DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y")


class ValidationError(ValueError):
    """Raised when user-supplied input fails validation."""


def clean_text(value: str) -> str:
    value = CONTROL_CHARS_RE.sub("", value or "")
    return " ".join(value.split()).strip()


def validate_first_name(value: str) -> str:
    value = clean_text(value)
    if not 2 <= len(value) <= 32:
        raise ValidationError("First name must be between 2 and 32 characters.")
    if URL_RE.search(value) or USERNAME_RE.search(value):
        raise ValidationError("Please enter a plain first name without links or usernames.")
    if not any(char.isalpha() for char in value):
        raise ValidationError("Please enter a valid first name.")
    return value


def parse_birth_date(value: str) -> date:
    value = clean_text(value)
    parsed: date | None = None
    for fmt in DATE_FORMATS:
        try:
            parsed = date.fromisoformat(value) if fmt == "%Y-%m-%d" else None
            if parsed is None:
                from datetime import datetime

                parsed = datetime.strptime(value, fmt).date()
            break
        except ValueError:
            continue
    if parsed is None:
        raise ValidationError("Please use DD/MM/YYYY, for example 14/02/1996.")
    today = date.today()
    if parsed > today:
        raise ValidationError("Date of birth cannot be in the future.")
    age = calculate_age(parsed, today)
    if age < 18:
        raise ValidationError("Cheers Dating is strictly for adults aged 18 and over.")
    if age > 99:
        raise ValidationError("Please enter a valid date of birth.")
    return parsed


def validate_city(value: str) -> str:
    value = clean_text(value)
    if not 2 <= len(value) <= 64:
        raise ValidationError("City must be between 2 and 64 characters.")
    if URL_RE.search(value) or USERNAME_RE.search(value):
        raise ValidationError("Please enter a city name only.")
    return value


def validate_bio(value: str) -> str:
    value = clean_text(value)
    if len(value) < 10:
        raise ValidationError("Your bio should be at least 10 characters. Tell people a little about you.")
    if len(value) > MAX_BIO_LENGTH:
        raise ValidationError(f"Your bio must be at most {MAX_BIO_LENGTH} characters.")
    return value


def validate_interests(values: list[str]) -> list[str]:
    unique: list[str] = []
    for item in values:
        key = item.strip().lower()
        if key in INTERESTS and key not in unique:
            unique.append(key)
    if not unique:
        raise ValidationError("Choose at least one interest.")
    if len(unique) > 8:
        raise ValidationError("Choose up to 8 interests.")
    return unique


def validate_photo_count(count: int) -> None:
    if count < 1:
        raise ValidationError("Add at least one photo.")
    if count > MAX_PHOTOS:
        raise ValidationError(f"You can add up to {MAX_PHOTOS} photos.")


def validate_message_text(value: str) -> str:
    value = clean_text(value)
    if not value:
        raise ValidationError("Your message is empty.")
    if len(value) > MAX_MESSAGE_LENGTH:
        raise ValidationError(f"Messages must be at most {MAX_MESSAGE_LENGTH} characters.")
    return value


def validate_report_details(value: str) -> str:
    value = clean_text(value)
    if len(value) > MAX_REPORT_DETAILS:
        raise ValidationError(f"Details must be at most {MAX_REPORT_DETAILS} characters.")
    return value


def normalize_digits(value: str) -> str:
    return DIGITS_ONLY_RE.sub("", value)


def contains_contact_info(value: str) -> bool:
    """Detect attempts to share private contact details inside chat.

    Blocks phone numbers, emails, @usernames, and links. This protects users
    from moving conversations off-platform before trust is established.
    """
    if EMAIL_RE.search(value) or USERNAME_RE.search(value) or URL_RE.search(value):
        return True
    for match in PHONE_RE.finditer(value):
        candidate = match.group(0)
        if len(normalize_digits(candidate)) >= 9:
            return True
    return False
