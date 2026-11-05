"""Domain constants and human-readable labels."""

from __future__ import annotations

from enum import StrEnum


class Gender(StrEnum):
    MAN = "man"
    WOMAN = "woman"
    NON_BINARY = "non_binary"


class Preference(StrEnum):
    MEN = "men"
    WOMEN = "women"
    EVERYONE = "everyone"


class Intention(StrEnum):
    SERIOUS = "serious"
    LONG_TERM = "long_term"
    FRIENDSHIP = "friendship"
    CASUAL = "casual"
    MARRIAGE = "marriage"
    NOT_SURE = "not_sure"


class ViewAction(StrEnum):
    LIKE = "like"
    PASS = "pass"


class MessageKind(StrEnum):
    TEXT = "text"
    PHOTO = "photo"


class ReportReason(StrEnum):
    SPAM = "spam"
    HARASSMENT = "harassment"
    FAKE = "fake_profile"
    INAPPROPRIATE = "inappropriate"
    UNDERAGE = "underage"
    SCAM = "scam"
    OTHER = "other"


class ReportStatus(StrEnum):
    OPEN = "open"
    REVIEWING = "reviewing"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class BroadcastStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


GENDER_LABELS: dict[Gender, str] = {
    Gender.MAN: "👨 Man",
    Gender.WOMAN: "👩 Woman",
    Gender.NON_BINARY: "🌈 Non-binary",
}

GENDER_LABELS_SHORT: dict[Gender, str] = {
    Gender.MAN: "Man",
    Gender.WOMAN: "Woman",
    Gender.NON_BINARY: "Non-binary",
}

PREFERENCE_LABELS: dict[Preference, str] = {
    Preference.MEN: "👨 Men",
    Preference.WOMEN: "👩 Women",
    Preference.EVERYONE: "🌈 Everyone",
}

PREFERENCE_LABELS_SHORT: dict[Preference, str] = {
    Preference.MEN: "Men",
    Preference.WOMEN: "Women",
    Preference.EVERYONE: "Everyone",
}

INTENTION_LABELS: dict[Intention, str] = {
    Intention.SERIOUS: "💍 Serious relationship",
    Intention.LONG_TERM: "❤️ Long-term partner",
    Intention.FRIENDSHIP: "🤝 New friendships",
    Intention.CASUAL: "☕ Casual dating",
    Intention.MARRIAGE: "👰 Marriage-minded",
    Intention.NOT_SURE: "🤔 Still figuring it out",
}

REPORT_REASON_LABELS: dict[ReportReason, str] = {
    ReportReason.SPAM: "📢 Spam or advertising",
    ReportReason.HARASSMENT: "😠 Harassment or threats",
    ReportReason.FAKE: "🎭 Fake profile / catfishing",
    ReportReason.INAPPROPRIATE: "🔞 Inappropriate content",
    ReportReason.UNDERAGE: "🚨 User appears under 18",
    ReportReason.SCAM: "💸 Scam or financial fraud",
    ReportReason.OTHER: "❓ Something else",
}

REPORT_STATUS_LABELS: dict[ReportStatus, str] = {
    ReportStatus.OPEN: "🟡 Open",
    ReportStatus.REVIEWING: "🔵 Reviewing",
    ReportStatus.RESOLVED: "🟢 Resolved",
    ReportStatus.DISMISSED: "⚪ Dismissed",
}

# key -> label. Keys are stored in the database.
INTERESTS: dict[str, str] = {
    "coffee": "☕ Coffee",
    "music": "🎵 Music",
    "travel": "✈️ Travel",
    "movies": "🎬 Movies",
    "books": "📚 Books",
    "fitness": "🏋️ Fitness",
    "cooking": "🍲 Cooking",
    "nature": "🌿 Nature",
    "football": "⚽ Football",
    "art": "🎨 Art",
    "tech": "💻 Tech",
    "dancing": "💃 Dancing",
}

CITIES: tuple[str, ...] = (
    "Addis Ababa",
    "Adama",
    "Bahir Dar",
    "Hawassa",
    "Gondar",
    "Mekelle",
    "Dire Dawa",
    "Jimma",
    "Bishoftu",
    "Jijiga",
    "Shashamane",
    "Arba Minch",
    "Harar",
    "Dessie",
    "Nekemte",
)

AGE_PRESETS: tuple[tuple[int, int, str], ...] = (
    (18, 25, "18–25"),
    (18, 35, "18–35"),
    (25, 35, "25–35"),
    (25, 45, "25–45"),
    (35, 50, "35–50"),
    (40, 65, "40–65"),
)

MAX_PHOTOS = 3
MAX_BIO_LENGTH = 500
MAX_MESSAGE_LENGTH = 2_000
MAX_REPORT_DETAILS = 500
