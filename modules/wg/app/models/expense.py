from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, SoftDeleteMixin, TimestampMixin


class ExpenseCategory(Base, TimestampMixin):
    __tablename__ = "expense_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(32), unique=True)
    name_de: Mapped[str] = mapped_column(String(60))
    name_en: Mapped[str] = mapped_column(String(60))
    position: Mapped[int]
    active: Mapped[bool] = mapped_column(default=True)


class Expense(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    description: Mapped[str] = mapped_column(String(120))
    amount_cents: Mapped[int]
    paid_by_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("expense_categories.id"), default=None
    )
    spent_on: Mapped[date]
    # recurring_expenses lands in Phase 2; no FK constraint until that table exists.
    recurring_id: Mapped[int | None] = mapped_column(default=None)
    created_by: Mapped[int] = mapped_column(ForeignKey("members.id"))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("members.id"), default=None)
    updated_at: Mapped[datetime | None] = mapped_column(default=None)


class ExpenseShare(Base):
    __tablename__ = "expense_shares"

    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id"), primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), primary_key=True)
    share_cents: Mapped[int]


class Settlement(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "settlements"

    id: Mapped[int] = mapped_column(primary_key=True)
    from_member_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    to_member_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    amount_cents: Mapped[int]
    paid_on: Mapped[date]
    note: Mapped[str | None] = mapped_column(String(120), default=None)
    confirmed_at: Mapped[datetime | None] = mapped_column(default=None)
    created_by: Mapped[int] = mapped_column(ForeignKey("members.id"))
