from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, SoftDeleteMixin, TimestampMixin


class ShoppingItem(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "shopping_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    quantity: Mapped[str | None] = mapped_column(String(30), default=None)
    note: Mapped[str | None] = mapped_column(String(120), default=None)
    source: Mapped[str] = mapped_column(String(16), default="manual")
    # supplies lands in Phase 2; no FK constraint until that table exists.
    supply_id: Mapped[int | None] = mapped_column(default=None)
    added_by: Mapped[int] = mapped_column(ForeignKey("members.id"))
    checked_at: Mapped[datetime | None] = mapped_column(default=None)
    checked_by: Mapped[int | None] = mapped_column(ForeignKey("members.id"), default=None)
    expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id"), default=None)
    archived_at: Mapped[datetime | None] = mapped_column(default=None)
