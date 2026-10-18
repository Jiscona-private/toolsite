from __future__ import annotations

from datetime import date

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class Member(Base, TimestampMixin):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)
    language: Mapped[str] = mapped_column(String(2), default="de")
    color: Mapped[int] = mapped_column(default=0)
    position: Mapped[int]
    active: Mapped[bool] = mapped_column(default=True)
    joined_on: Mapped[date]
    left_on: Mapped[date | None] = mapped_column(default=None)
    ntfy_topic: Mapped[str] = mapped_column(String(64), unique=True)
    notify_prefs: Mapped[dict] = mapped_column(JSON, default=dict)


class Setting(Base):
    """Key-value settings (wg_name, join_token, cookie_version, ...). No
    lifecycle of its own, so - unlike the other tables - no created_at."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]
