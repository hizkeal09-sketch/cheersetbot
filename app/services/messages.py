"""Private matched-user messaging."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.constants import MessageKind
from app.database.models import Block, DailyUsage, Match, User
from app.database.models import Message as MessageModel
from app.services.errors import ContactInfoBlockedError, NotMatchedError
from app.services.matches import MatchService
from app.utils.time import local_today
from app.utils.validators import contains_contact_info, validate_message_text


class MessageService:
    @staticmethod
    async def _is_blocked(session: AsyncSession, first_id: int, second_id: int) -> bool:
        block = await session.scalar(
            sa.select(Block).where(
                sa.or_(
                    sa.and_(Block.blocker_id == first_id, Block.blocked_id == second_id),
                    sa.and_(Block.blocker_id == second_id, Block.blocked_id == first_id),
                )
            )
        )
        return block is not None

    @staticmethod
    async def store_message(
        session: AsyncSession,
        sender: User,
        match_id: int,
        *,
        kind: MessageKind,
        text: str | None = None,
        photo_file_id: str | None = None,
        settings: Settings,
    ) -> tuple[MessageModel, User, Match]:
        match = await MatchService.get_active_for_user(session, sender.id, match_id)
        recipient = match.other_user(sender.id)

        if recipient.is_banned or not recipient.is_registered:
            raise NotMatchedError("This person is no longer available.")
        if await MessageService._is_blocked(session, sender.id, recipient.id):
            raise NotMatchedError("You can't message this person.")

        if kind == MessageKind.TEXT:
            text = validate_message_text(text or "")
            photo_file_id = None
        elif kind == MessageKind.PHOTO:
            if not photo_file_id:
                raise NotMatchedError("The photo could not be sent. Please try again.")
            text = validate_message_text(text) if text else None
        else:
            raise NotMatchedError("Only text and photo messages are supported.")

        if text and not settings.allow_contact_sharing and contains_contact_info(text):
            raise ContactInfoBlockedError()

        message = MessageModel(
            match_id=match.id,
            sender_id=sender.id,
            kind=kind,
            text=text,
            photo_file_id=photo_file_id,
        )
        session.add(message)

        usage = await session.scalar(
            sa.select(DailyUsage).where(
                DailyUsage.user_id == sender.id,
                DailyUsage.usage_date == local_today(settings.app_timezone),
            )
        )
        if usage:
            usage.messages += 1

        await session.flush()
        return message, recipient, match

    @staticmethod
    async def mark_read(session: AsyncSession, user: User, match_id: int) -> int:
        result = await session.execute(
            sa.update(MessageModel)
            .where(
                MessageModel.match_id == match_id,
                MessageModel.sender_id != user.id,
                MessageModel.is_read.is_(False),
            )
            .values(is_read=True)
        )
        await session.commit()
        return int(result.rowcount or 0)
