from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class Chore(Base, TimestampMixin):
    __tablename__ = "chores"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(32), unique=True)
    name_de: Mapped[str] = mapped_column(String(60))
    name_en: Mapped[str] = mapped_column(String(60))
    position: Mapped[int]
    active: Mapped[bool] = mapped_column(default=True)


class RotaConfig(Base, TimestampMixin):
    __tablename__ = "rota_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    valid_from: Mapped[date]
    chore_ids: Mapped[list[int]] = mapped_column(JSON)
    slots: Mapped[list[int | None]] = mapped_column(JSON)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("members.id"), default=None)


class ChoreEntry(Base):
    """No created_at: acted_at already records when this happened."""

    __tablename__ = "chore_entries"
    __table_args__ = (UniqueConstraint("week", "chore_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    week: Mapped[date]
    chore_id: Mapped[int] = mapped_column(ForeignKey("chores.id"))
    assigned_member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"), default=None)
    status: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str | None] = mapped_column(String(200), default=None)
    done_by_member_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    acted_at: Mapped[datetime]


class ChoreSwap(Base, TimestampMixin):
    __tablename__ = "chore_swaps"
    __table_args__ = (
        UniqueConstraint("week", "member_a_id"),
        UniqueConstraint("week", "member_b_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    week: Mapped[date]
    member_a_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    member_b_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("members.id"))
