"""SQLAlchemy models for Cheers Dating.

Privacy notes:
- Telegram IDs live only in the database and are never shown to other users.
- All user-provided content is stored as-is and escaped at render time.
"""

from __future__ import annotations

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import (
    BroadcastStatus,
    Gender,
    Intention,
    MessageKind,
    Preference,
    Religion,
    ReportReason,
    ReportStatus,
    ViewAction,
)
from app.database.base import Base
from app.utils.time import calculate_age


def enum_type(enum_cls: type) -> sa.Enum:
    """Portable string enum (no native PostgreSQL enum types)."""
    return sa.Enum(
        enum_cls,
        native_enum=False,
        length=32,
        values_callable=lambda cls: [member.value for member in cls],
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(sa.BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(sa.String(64))
    language: Mapped[str] = mapped_column(sa.String(8), default="en", server_default="en")

    first_name: Mapped[str] = mapped_column(sa.String(64), default="", server_default="")
    birth_date: Mapped[date | None] = mapped_column(sa.Date, index=True)
    gender: Mapped[Gender | None] = mapped_column(enum_type(Gender))
    interested_in: Mapped[Preference | None] = mapped_column(enum_type(Preference))
    religion: Mapped[Religion | None] = mapped_column(enum_type(Religion))
    city: Mapped[str | None] = mapped_column(sa.String(64), index=True)
    latitude: Mapped[float | None] = mapped_column(sa.Float)
    longitude: Mapped[float | None] = mapped_column(sa.Float)

    bio: Mapped[str | None] = mapped_column(sa.Text)
    interests: Mapped[list[str]] = mapped_column(sa.JSON, default=list, nullable=False)
    intention: Mapped[Intention | None] = mapped_column(enum_type(Intention))

    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, default=True, server_default=sa.true(), nullable=False
    )
    profile_paused: Mapped[bool] = mapped_column(
        sa.Boolean, default=False, server_default=sa.false(), nullable=False
    )
    moderation_notes: Mapped[str | None] = mapped_column(sa.Text)
    is_banned: Mapped[bool] = mapped_column(
        sa.Boolean, default=False, server_default=sa.false(), nullable=False, index=True
    )
    ban_reason: Mapped[str | None] = mapped_column(sa.Text)

    is_premium: Mapped[bool] = mapped_column(
        sa.Boolean, default=False, server_default=sa.false(), nullable=False
    )
    premium_until: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    is_verified: Mapped[bool] = mapped_column(
        sa.Boolean, default=False, server_default=sa.false(), nullable=False
    )

    consent_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    registration_completed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), index=True
    )
    last_active_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), index=True
    )

    photos: Mapped[list[UserPhoto]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="UserPhoto.position",
        lazy="selectin",
    )
    filter: Mapped[UserFilter | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )

    @property
    def age(self) -> int | None:
        return calculate_age(self.birth_date) if self.birth_date else None

    @property
    def is_registered(self) -> bool:
        return self.registration_completed_at is not None

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<User id={self.id} telegram_id={self.telegram_id}>"


class UserPhoto(Base):
    __tablename__ = "user_photos"
    __table_args__ = (
        sa.UniqueConstraint("user_id", "position", name="uq_user_photos_user_position"),
        sa.CheckConstraint("position >= 0 AND position <= 2", name="ck_user_photos_position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    file_id: Mapped[str] = mapped_column(sa.Text, nullable=False)
    position: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)

    user: Mapped[User] = relationship(back_populates="photos")


class UserFilter(TimestampMixin, Base):
    __tablename__ = "user_filters"
    __table_args__ = (
        sa.CheckConstraint("min_age >= 18", name="ck_user_filters_min_age"),
        sa.CheckConstraint("max_age >= min_age", name="ck_user_filters_age_range"),
    )

    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    min_age: Mapped[int] = mapped_column(sa.Integer, default=18, server_default="18")
    max_age: Mapped[int] = mapped_column(sa.Integer, default=60, server_default="60")
    gender: Mapped[Gender | None] = mapped_column(enum_type(Gender))
    city: Mapped[str | None] = mapped_column(sa.String(64))
    religion: Mapped[Religion | None] = mapped_column(enum_type(Religion))
    active_recently_only: Mapped[bool] = mapped_column(
        sa.Boolean, default=False, server_default=sa.false(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="filter")


class Like(Base):
    __tablename__ = "likes"
    __table_args__ = (
        sa.UniqueConstraint("from_user_id", "to_user_id", name="uq_likes_from_to"),
        sa.CheckConstraint("from_user_id <> to_user_id", name="ck_likes_not_self"),
        sa.Index("ix_likes_to_user_id", "to_user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    from_user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    to_user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class ProfileView(Base):
    __tablename__ = "profile_views"
    __table_args__ = (
        sa.UniqueConstraint("viewer_id", "viewed_id", name="uq_profile_views_viewer_viewed"),
        sa.CheckConstraint("viewer_id <> viewed_id", name="ck_profile_views_not_self"),
        sa.Index("ix_profile_views_viewer_id", "viewer_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    viewer_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    viewed_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[ViewAction | None] = mapped_column(enum_type(ViewAction))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        sa.UniqueConstraint("user_a_id", "user_b_id", name="uq_matches_pair"),
        sa.CheckConstraint("user_a_id < user_b_id", name="ck_matches_ordered_pair"),
        sa.Index("ix_matches_user_a", "user_a_id"),
        sa.Index("ix_matches_user_b", "user_b_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_a_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    user_b_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, default=True, server_default=sa.true(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

    user_a: Mapped[User] = relationship(foreign_keys=[user_a_id], lazy="selectin")
    user_b: Mapped[User] = relationship(foreign_keys=[user_b_id], lazy="selectin")

    def other_user(self, user_id: int) -> User:
        return self.user_b if self.user_a_id == user_id else self.user_a

    def includes(self, user_id: int) -> bool:
        return user_id in (self.user_a_id, self.user_b_id)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (sa.Index("ix_messages_match_created", "match_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        sa.ForeignKey("matches.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sender_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[MessageKind] = mapped_column(
        enum_type(MessageKind), default=MessageKind.TEXT, nullable=False
    )
    text: Mapped[str | None] = mapped_column(sa.Text)
    photo_file_id: Mapped[str | None] = mapped_column(sa.Text)
    is_read: Mapped[bool] = mapped_column(
        sa.Boolean, default=False, server_default=sa.false(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    sender: Mapped[User] = relationship(lazy="selectin")


class Block(Base):
    __tablename__ = "blocks"
    __table_args__ = (
        sa.UniqueConstraint("blocker_id", "blocked_id", name="uq_blocks_pair"),
        sa.CheckConstraint("blocker_id <> blocked_id", name="ck_blocks_not_self"),
        sa.Index("ix_blocks_blocker_id", "blocker_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    blocker_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    blocked_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (sa.Index("ix_reports_status", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reporter_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    reported_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    reason: Mapped[ReportReason] = mapped_column(enum_type(ReportReason), nullable=False)
    details: Mapped[str | None] = mapped_column(sa.Text)
    status: Mapped[ReportStatus] = mapped_column(
        enum_type(ReportStatus),
        default=ReportStatus.OPEN,
        server_default=ReportStatus.OPEN.value,
        nullable=False,
    )
    reviewed_by: Mapped[int | None] = mapped_column(sa.BigInteger)
    reviewed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    admin_notes: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    reporter: Mapped[User] = relationship(foreign_keys=[reporter_id], lazy="selectin")
    reported: Mapped[User] = relationship(foreign_keys=[reported_id], lazy="selectin")


class AdminAction(Base):
    __tablename__ = "admin_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    admin_telegram_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    action: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    target_user_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    details: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


class DailyUsage(Base):
    __tablename__ = "daily_usage"
    __table_args__ = (
        sa.UniqueConstraint("user_id", "usage_date", name="uq_daily_usage_user_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    usage_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    discoveries: Mapped[int] = mapped_column(sa.Integer, default=0, server_default="0")
    likes: Mapped[int] = mapped_column(sa.Integer, default=0, server_default="0")
    messages: Mapped[int] = mapped_column(sa.Integer, default=0, server_default="0")


class FsmState(Base):
    """Persistent aiogram FSM state.

    Serverless functions are ephemeral and may run concurrently, so the default
    in-memory storage cannot be used on Vercel. Each row is keyed by the full
    :class:`aiogram.fsm.storage.base.StorageKey` (bot, chat, user, thread,
    business connection and destiny).
    """

    __tablename__ = "fsm_states"

    key: Mapped[str] = mapped_column(sa.String(255), primary_key=True)
    state: Mapped[str | None] = mapped_column(sa.String(255))
    data: Mapped[dict] = mapped_column(
        sa.JSON, default=dict, server_default=sa.text("'{}'"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
        index=True,
    )


class BroadcastJob(TimestampMixin, Base):
    """Durable admin broadcast with a resumable cursor.

    Vercel functions may be frozen or terminated after the HTTP response, so a
    fire-and-forget broadcast would silently lose recipients. Persisting the
    last processed user lets each invocation continue where the previous one
    stopped, whether triggered inline, by the admin, or by an external cron.
    """

    __tablename__ = "broadcast_jobs"
    __table_args__ = (sa.Index("ix_broadcast_jobs_status", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    admin_telegram_id: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(16),
        default=BroadcastStatus.PENDING.value,
        server_default=BroadcastStatus.PENDING.value,
        nullable=False,
    )
    last_user_id: Mapped[int] = mapped_column(
        sa.Integer, default=0, server_default="0", nullable=False
    )
    sent: Mapped[int] = mapped_column(sa.Integer, default=0, server_default="0", nullable=False)
    failed: Mapped[int] = mapped_column(
        sa.Integer, default=0, server_default="0", nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))

