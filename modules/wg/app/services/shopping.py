from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ShoppingItem


def open_items(db: Session) -> list[ShoppingItem]:
    """Still on the list - checked or not, just not archived/deleted yet."""
    return list(
        db.scalars(
            select(ShoppingItem)
            .where(ShoppingItem.archived_at.is_(None), ShoppingItem.deleted_at.is_(None))
            .order_by(ShoppingItem.created_at)
        )
    )


def find_open_duplicate(db: Session, name: str) -> ShoppingItem | None:
    """spec.md §5.1: case-insensitive match against open entries."""
    return db.scalars(
        select(ShoppingItem).where(
            func.lower(ShoppingItem.name) == name.strip().lower(),
            ShoppingItem.archived_at.is_(None),
            ShoppingItem.deleted_at.is_(None),
        )
    ).first()


def add_item(
    db: Session,
    *,
    name: str,
    quantity: str | None,
    note: str | None,
    added_by: int,
) -> ShoppingItem:
    item = ShoppingItem(
        name=name.strip(),
        quantity=quantity.strip() if quantity else None,
        note=note.strip() if note else None,
        source="manual",
        added_by=added_by,
    )
    db.add(item)
    return item


def toggle_checked(item: ShoppingItem, by_member_id: int) -> ShoppingItem:
    if item.checked_at is None:
        item.checked_at = datetime.now(UTC)
        item.checked_by = by_member_id
    else:
        item.checked_at = None
        item.checked_by = None
    return item


def archive_checked(db: Session) -> int:
    """ "Erledigte entfernen": archives checked items that were never turned
    into an expense (those already got archived when that happened)."""
    items = db.scalars(
        select(ShoppingItem).where(
            ShoppingItem.checked_at.isnot(None),
            ShoppingItem.archived_at.is_(None),
            ShoppingItem.deleted_at.is_(None),
        )
    ).all()
    now = datetime.now(UTC)
    for item in items:
        item.archived_at = now
    return len(items)


def mark_as_expense(db: Session, item_ids: list[int], expense_id: int) -> None:
    now = datetime.now(UTC)
    items = db.scalars(select(ShoppingItem).where(ShoppingItem.id.in_(item_ids))).all()
    for item in items:
        item.expense_id = expense_id
        item.archived_at = now
