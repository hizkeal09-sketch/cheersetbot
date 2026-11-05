"""Matching rules and match lifecycle."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Match, User
from app.services.errors import NotMatchedError
from app.utils.time import utcnow


def _ordered_pair(first: int, second: int) -> tuple[int, int]:
    return (first, second) if first < second else (second, first)


class MatchService:
    @staticmethod
    async def get_or_create(session: AsyncSession, first_id: int, second_id: int) -> tuple[Match, bool]:
        if first_id == second_id:
            raise ValueError("A user cannot match with themselves")
        a_id, b_id = _ordered_pair(first_id, second_id)

        existing = await session.scalar(
            sa.select(Match).where(Match.user_a_id == a_id, Match.user_b_id == b_id)
        )
        if existing:
            return existing, False

        match = Match(user_a_id=a_id, user_b_id=b_id)
        try:
            async with session.begin_nested():
                session.add(match)
                await session.flush()
            return match, True
        except IntegrityError:
            existing = await session.scalar(
                sa.select(Match).where(Match.user_a_id == a_id, Match.user_b_id == b_id)
            )
            if existing is None:
                raise
            return existing, False

    @staticmethod
    async def list_active(session: AsyncSession, user_id: int) -> list[Match]:
        result = await session.scalars(
            sa.select(Match)
            .where(
                Match.is_active.is_(True),
                (Match.user_a_id == user_id) | (Match.user_b_id == user_id),
            )
            .order_by(Match.created_at.desc())
        )
        return list(result.unique())

    @staticmethod
    async def get_for_user(session: AsyncSession, user_id: int, match_id: int) -> Match:
        match = await session.get(Match, match_id)
        if match is None or not match.includes(user_id):
            raise NotMatchedError()
        return match

    @staticmethod
    async def get_active_for_user(session: AsyncSession, user_id: int, match_id: int) -> Match:
        match = await MatchService.get_for_user(session, user_id, match_id)
        if not match.is_active:
            raise NotMatchedError("This match has ended.")
        return match

    @staticmethod
    async def unmatch(session: AsyncSession, user_id: int, match_id: int) -> Match:
        match = await MatchService.get_active_for_user(session, user_id, match_id)
        match.is_active = False
        match.ended_at = utcnow()
        await session.commit()
        return match

    @staticmethod
    async def deactivate_between(session: AsyncSession, first_id: int, second_id: int) -> None:
        a_id, b_id = _ordered_pair(first_id, second_id)
        match = await session.scalar(
            sa.select(Match).where(
                Match.user_a_id == a_id, Match.user_b_id == b_id, Match.is_active.is_(True)
            )
        )
        if match:
            match.is_active = False
            match.ended_at = utcnow()

    @staticmethod
    async def count_total(session: AsyncSession) -> int:
        return int(await session.scalar(sa.select(sa.func.count()).select_from(Match)) or 0)

    @staticmethod
    def partner(match: Match, user: User) -> User:
        return match.other_user(user.id)
