"""Domain exceptions with user-safe messages."""

from __future__ import annotations


class CheersError(Exception):
    """Base class for expected, user-facing errors."""

    user_message = "Something went wrong. Please try again."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.user_message)
        self.user_message = message or self.user_message


class NotRegisteredError(CheersError):
    user_message = "Please finish your profile first with /start."


class ProfilePausedError(CheersError):
    user_message = "Your profile is paused. Resume it from /settings to keep discovering people."


class AccountBannedError(CheersError):
    user_message = "Your account is suspended. Please contact support."


class DailyLimitReached(CheersError):
    def __init__(self, limit: int) -> None:
        super().__init__(
            f"You have reached today's limit of {limit} profile discoveries. "
            "Come back tomorrow or unlock Premium for more."
        )
        self.limit = limit


class TargetUnavailableError(CheersError):
    user_message = "This profile is no longer available."


class AlreadyLikedError(CheersError):
    user_message = "You already liked this person."


class NotMatchedError(CheersError):
    user_message = "You can only message people you have matched with."


class ContactInfoBlockedError(CheersError):
    user_message = (
        "For your safety, phone numbers, usernames, emails and links can't be shared "
        "in chat. Keep getting to know each other here first."
    )


class ReportAlreadyOpenError(CheersError):
    user_message = "You already have an open report for this person. Our team is reviewing it."


class InvalidTargetError(CheersError):
    user_message = "That user could not be found."
