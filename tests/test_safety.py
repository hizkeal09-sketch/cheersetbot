"""Matched-only messaging, moderation, and safety rules."""

from __future__ import annotations

import pytest

from app.constants import MessageKind, ReportReason, ReportStatus
from app.database.models import AdminAction, Block
from app.services.errors import (
    ContactInfoBlockedError,
    InvalidTargetError,
    NotMatchedError,
    ReportAlreadyOpenError,
)
from app.services.matches import MatchService
from app.services.messages import MessageService
from app.services.moderation import ModerationService
from tests.conftest import count, make_user


async def matched_pair(session):
    alice = await make_user(session, 3001, first_name="Alice")
    bob = await make_user(session, 3002, first_name="Bob")
    match, _ = await MatchService.get_or_create(session, alice.id, bob.id)
    await session.commit()
    return alice, bob, match


async def test_text_message_is_stored_and_relayed(session, settings) -> None:
    alice, bob, match = await matched_pair(session)
    message, recipient, stored_match = await MessageService.store_message(
        session,
        alice,
        match.id,
        kind=MessageKind.TEXT,
        text="  Hello Bob!  ",
        settings=settings,
    )
    await session.commit()

    assert message.text == "Hello Bob!"
    assert message.kind == MessageKind.TEXT
    assert recipient.id == bob.id
    assert stored_match.id == match.id

    updated = await MessageService.mark_read(session, bob, match.id)
    assert updated == 1  # Alice's message became read for Bob
    assert await MessageService.mark_read(session, bob, match.id) == 0


async def test_contact_info_is_blocked_in_chat(session, settings) -> None:
    alice, _bob, match = await matched_pair(session)
    with pytest.raises(ContactInfoBlockedError):
        await MessageService.store_message(
            session,
            alice,
            match.id,
            kind=MessageKind.TEXT,
            text="Call me on +251 911 123 456",
            settings=settings,
        )


async def test_contact_info_allowed_when_setting_enabled(session, settings) -> None:
    alice, _bob, match = await matched_pair(session)
    permissive = settings.model_copy(update={"allow_contact_sharing": True})
    message, _recipient, _match = await MessageService.store_message(
        session,
        alice,
        match.id,
        kind=MessageKind.TEXT,
        text="My email is alice@example.com",
        settings=permissive,
    )
    assert message.text == "My email is alice@example.com"


async def test_non_matched_users_cannot_message(session, settings) -> None:
    alice = await make_user(session, 3010)
    bob = await make_user(session, 3011)
    match, _ = await MatchService.get_or_create(session, alice.id, bob.id)
    await session.commit()
    await MatchService.unmatch(session, alice.id, match.id)

    with pytest.raises(NotMatchedError):
        await MessageService.store_message(
            session,
            alice,
            match.id,
            kind=MessageKind.TEXT,
            text="Hello?",
            settings=settings,
        )


async def test_blocked_users_cannot_message(session, settings) -> None:
    alice, bob, match = await matched_pair(session)
    await ModerationService.block_user(session, bob, alice.id)

    with pytest.raises(NotMatchedError):
        await MessageService.store_message(
            session,
            alice,
            match.id,
            kind=MessageKind.TEXT,
            text="Hello?",
            settings=settings,
        )


async def test_blocking_ends_match_and_is_idempotent(session) -> None:
    alice, bob, match = await matched_pair(session)
    assert await ModerationService.block_user(session, alice, bob.id) is True
    assert await ModerationService.block_user(session, alice, bob.id) is False

    await session.refresh(match)
    assert match.is_active is False
    assert match.ended_at is not None
    assert await count(session, Block) == 1


async def test_unblock(session) -> None:
    alice, bob, _match = await matched_pair(session)
    await ModerationService.block_user(session, alice, bob.id)
    blocked = await ModerationService.blocked_users(session, alice)
    assert [user.id for user in blocked] == [bob.id]

    assert await ModerationService.unblock_user(session, alice, bob.id) is True
    assert await ModerationService.unblock_user(session, alice, bob.id) is False
    assert await ModerationService.blocked_users(session, alice) == []


async def test_reporting_rules(session) -> None:
    alice, bob, _match = await matched_pair(session)
    report = await ModerationService.report_user(
        session, alice, bob.id, ReportReason.HARASSMENT, "Mean messages"
    )
    assert report.status == ReportStatus.OPEN
    assert await ModerationService.count_open_reports(session) == 1

    with pytest.raises(ReportAlreadyOpenError):
        await ModerationService.report_user(session, alice, bob.id, ReportReason.SPAM)

    with pytest.raises(InvalidTargetError):
        await ModerationService.report_user(session, alice, alice.id, ReportReason.SPAM)

    await ModerationService.set_report_status(
        session, report.id, ReportStatus.RESOLVED, admin_telegram_id=1
    )
    assert await ModerationService.count_open_reports(session) == 0
    assert await count(session, AdminAction) == 1


async def test_ban_and_unban(session, settings) -> None:
    alice, bob, match = await matched_pair(session)
    await ModerationService.ban_user(session, 1, bob, "Harassment")

    assert bob.is_banned is True
    assert bob.profile_paused is True
    assert bob.is_active is False
    await session.refresh(match)
    assert match.is_active is False

    with pytest.raises(NotMatchedError):
        await MessageService.store_message(
            session,
            alice,
            match.id,
            kind=MessageKind.TEXT,
            text="Hello?",
            settings=settings,
        )

    await ModerationService.unban_user(session, 1, bob)
    assert bob.is_banned is False
    assert bob.is_active is True
