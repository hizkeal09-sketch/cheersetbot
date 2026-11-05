"""Durable, resumable admin broadcasts.

A fire-and-forget broadcast is unreliable on Vercel: the function may be frozen
or terminated right after the HTTP response is sent, silently dropping
recipients. Instead every broadcast is stored as a :class:`BroadcastJob` with a
cursor, so an invocation can send a slice of recipients, persist its progress
and continue later (inline, from the admin panel, or from an external cron).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from time import monotonic
from typing import NamedTuple

import sqlalchemy as sa
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.constants import BroadcastStatus
from app.database.models import AdminAction, BroadcastJob, User
from app.utils.time import as_utc, utcnow

logger = logging.getLogger(__name__)

BATCH_SIZE = 100
SEND_INTERVAL_SECONDS = 0.05
STALE_RUNNING_AFTER = timedelta(minutes=5)


class BroadcastProgress(NamedTuple):
    """Outcome of one broadcast slice."""

    job_id: int
    sent: int
    failed: int
    finished: bool
    status: str


async def create_broadcast_job(
    session: AsyncSession,
    text: str,
    admin_telegram_id: int,
) -> BroadcastJob:
    """Persist a new broadcast job and return it."""
    job = BroadcastJob(
        text=text,
        admin_telegram_id=admin_telegram_id,
        status=BroadcastStatus.PENDING.value,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def _claim_job(
    session: AsyncSession, job_id: int
) -> BroadcastJob | None:
    """Mark a job as running so two workers never send the same message twice.

    A job left in ``running`` state by a crashed function is reclaimable once it
    becomes stale.
    """
    job = await session.get(BroadcastJob, job_id)
    if job is None:
        return None

    status = job.status
    if status in (BroadcastStatus.COMPLETED.value, BroadcastStatus.FAILED.value):
        return job

    if status == BroadcastStatus.RUNNING.value:
        updated_at = as_utc(job.updated_at)
        if updated_at is not None and utcnow() - updated_at <= STALE_RUNNING_AFTER:
            return job  # another worker owns it right now

    job.status = BroadcastStatus.RUNNING.value
    await session.commit()
    await session.refresh(job)
    return job


async def _save_progress(
    session: AsyncSession,
    job_id: int,
    *,
    sent: int,
    failed: int,
    last_user_id: int,
    status: str,
    finished: bool = False,
) -> None:
    job = await session.get(BroadcastJob, job_id)
    if job is None:
        return
    job.sent = sent
    job.failed = failed
    job.last_user_id = last_user_id
    job.status = status
    if finished:
        job.finished_at = utcnow()
    await session.commit()


async def _notify(bot: Bot, admin_telegram_id: int, text: str) -> None:
    try:
        await bot.send_message(admin_telegram_id, text)
    except TelegramAPIError:
        logger.warning("Could not notify admin %s about a broadcast", admin_telegram_id)


async def process_broadcast_job(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    job_id: int,
    *,
    max_seconds: float = 20.0,
    notify: bool = True,
) -> BroadcastProgress | None:
    """Send as many pending messages as fit into ``max_seconds``.

    The job is completed when every registered, non-banned user has been
    processed. When the time budget runs out first the job is paused and can be
    resumed later without sending duplicates.
    """
    deadline = monotonic() + max_seconds

    async with session_factory() as session:
        job = await _claim_job(session, job_id)
        if job is None:
            return None
        if job.status in (BroadcastStatus.COMPLETED.value, BroadcastStatus.FAILED.value):
            return BroadcastProgress(
                job_id=job.id,
                sent=job.sent,
                failed=job.failed,
                finished=True,
                status=job.status,
            )
        if job.status == BroadcastStatus.RUNNING.value and job.updated_at is not None:
            updated_at = as_utc(job.updated_at)
            if updated_at is not None and utcnow() - updated_at <= STALE_RUNNING_AFTER:
                logger.info("Broadcast job %s is already running", job_id)
                return BroadcastProgress(
                    job_id=job.id,
                    sent=job.sent,
                    failed=job.failed,
                    finished=False,
                    status=job.status,
                )
        admin_telegram_id = job.admin_telegram_id
        text = job.text
        sent = job.sent
        failed = job.failed
        cursor = job.last_user_id

    while True:
        if monotonic() >= deadline:
            async with session_factory() as session:
                await _save_progress(
                    session,
                    job_id,
                    sent=sent,
                    failed=failed,
                    last_user_id=cursor,
                    status=BroadcastStatus.PAUSED.value,
                )
            logger.info("Broadcast job %s paused (sent=%s failed=%s)", job_id, sent, failed)
            return BroadcastProgress(
                job_id=job_id,
                sent=sent,
                failed=failed,
                finished=False,
                status=BroadcastStatus.PAUSED.value,
            )

        async with session_factory() as session:
            rows = (
                await session.execute(
                    sa.select(User.id, User.telegram_id)
                    .where(
                        User.id > cursor,
                        User.registration_completed_at.is_not(None),
                        User.is_banned.is_(False),
                    )
                    .order_by(User.id)
                    .limit(BATCH_SIZE)
                )
            ).all()

        if not rows:
            async with session_factory() as session:
                await _save_progress(
                    session,
                    job_id,
                    sent=sent,
                    failed=failed,
                    last_user_id=cursor,
                    status=BroadcastStatus.COMPLETED.value,
                    finished=True,
                )
                session.add(
                    AdminAction(
                        admin_telegram_id=admin_telegram_id,
                        action="broadcast",
                        details=f"job={job_id} sent={sent} failed={failed}",
                    )
                )
                await session.commit()
            logger.info("Broadcast job %s completed (sent=%s failed=%s)", job_id, sent, failed)
            if notify:
                await _notify(
                    bot,
                    admin_telegram_id,
                    f"📢 <b>Broadcast complete</b>\n\n✅ Sent: {sent}\n❌ Failed: {failed}",
                )
            return BroadcastProgress(
                job_id=job_id,
                sent=sent,
                failed=failed,
                finished=True,
                status=BroadcastStatus.COMPLETED.value,
            )

        for user_id, chat_id in rows:
            try:
                await bot.send_message(chat_id, text, parse_mode=None)
                sent += 1
            except TelegramAPIError:
                failed += 1
            cursor = user_id
            await asyncio.sleep(SEND_INTERVAL_SECONDS)

        async with session_factory() as session:
            await _save_progress(
                session,
                job_id,
                sent=sent,
                failed=failed,
                last_user_id=cursor,
                status=BroadcastStatus.RUNNING.value,
            )


async def process_pending_broadcasts(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    max_seconds: float = 50.0,
) -> list[BroadcastProgress]:
    """Continue every paused or pending job within a shared time budget."""
    deadline = monotonic() + max_seconds
    results: list[BroadcastProgress] = []

    async with session_factory() as session:
        job_ids = list(
            (
                await session.scalars(
                    sa.select(BroadcastJob.id)
                    .where(BroadcastJob.status.in_(("pending", "paused")))
                    .order_by(BroadcastJob.id)
                    .limit(10)
                )
            ).all()
        )

    for job_id in job_ids:
        remaining = deadline - monotonic()
        if remaining <= 1:
            break
        progress = await process_broadcast_job(
            bot,
            session_factory,
            job_id,
            max_seconds=remaining,
            notify=True,
        )
        if progress is not None:
            results.append(progress)

    return results
