from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, SoftDeleteMixin, TimestampMixin


class Note(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    body: Mapped[str] = mapped_column(Text)
    pinned: Mapped[bool] = mapped_column(default=False)
    expires_on: Mapped[date | None] = mapped_column(default=None)
    created_by: Mapped[int] = mapped_column(ForeignKey("members.id"))


class InfoPage(Base, TimestampMixin):
    __tablename__ = "info_pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(60))
    body: Mapped[str] = mapped_column(Text)
    position: Mapped[int]
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("members.id"), default=None)
    updated_at: Mapped[datetime | None] = mapped_column(default=None)
