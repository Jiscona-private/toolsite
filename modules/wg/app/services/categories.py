from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExpenseCategory


def create_category(db: Session, *, key: str, name_de: str, name_en: str) -> ExpenseCategory:
    positions = list(db.scalars(select(ExpenseCategory.position)))
    category = ExpenseCategory(
        key=key,
        name_de=name_de,
        name_en=name_en,
        position=max(positions, default=-1) + 1,
    )
    db.add(category)
    return category


def set_active(category: ExpenseCategory, active: bool) -> None:
    category.active = active
