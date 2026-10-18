from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActivityLog, Expense, ExpenseShare, Note, Settlement, ShoppingItem
from app.timezone import berlin_today

TRASH_RETENTION_DAYS = 30  # spec.md §2.6

# entity -> (model, restore field setter)
_TRASH_MODELS = (("expense", Expense), ("settlement", Settlement), ("note", Note))


def log(
    db: Session,
    *,
    actor_member_id: int | None,
    action: str,
    entity: str,
    summary_key: str,
    entity_id: int | None = None,
    summary_params: dict | None = None,
    before: dict | None = None,
    after: dict | None = None,
) -> ActivityLog:
    """One row in activity_log per spec.md §2.6 - every write ends up here.
    `summary_params` values are already plain text/numbers (not re-localized
    on display, see docs/spec.md's own `{"description": "..."}` example) -
    callers format money/dates with the household's default language."""
    entry = ActivityLog(
        at=datetime.now(UTC),
        actor_member_id=actor_member_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        summary_key=summary_key,
        summary_params=summary_params or {},
        before=before,
        after=after,
    )
    db.add(entry)
    return entry


def recent(db: Session, *, limit: int = 100) -> list[ActivityLog]:
    return list(
        db.scalars(
            select(ActivityLog).order_by(ActivityLog.at.desc(), ActivityLog.id.desc()).limit(limit)
        )
    )


def trash_items(db: Session) -> list[dict]:
    """Everything soft-deleted within the retention window, newest first -
    spec.md §2.6's Papierkorb. `label` is a short, already-rendered
    identifier for the item (its description/body), not i18n'd further."""
    items = []
    for entity, model in _TRASH_MODELS:
        for row in db.scalars(select(model).where(model.deleted_at.isnot(None))):
            items.append({"entity": entity, "id": row.id, "deleted_at": row.deleted_at, "row": row})
    items.sort(key=lambda i: i["deleted_at"], reverse=True)
    return items


def restore(db: Session, *, entity: str, entity_id: int) -> object | None:
    """Unsets `deleted_at`. Callers are responsible for the matching
    activity_log entry (they know the human-readable summary already)."""
    model = next((m for e, m in _TRASH_MODELS if e == entity), None)
    if model is None:
        return None
    row = db.get(model, entity_id)
    if row is None or row.deleted_at is None:
        return None
    row.deleted_at = None
    return row


def purge_expired_notes(db: Session, *, today: date | None = None) -> int:
    """Notes whose `expires_on` has passed disappear automatically
    (spec.md §4.5) - soft-deleted like any other removal, so they still
    sit in the trash for the usual 30 days."""
    today = today or berlin_today()
    notes = db.scalars(
        select(Note).where(
            Note.deleted_at.is_(None), Note.expires_on.isnot(None), Note.expires_on < today
        )
    ).all()
    for note in notes:
        note.deleted_at = datetime.now(UTC)
        log(
            db,
            actor_member_id=None,
            action="delete",
            entity="note",
            entity_id=note.id,
            summary_key="log.note.expired",
        )
    return len(notes)


def purge_old_trash(db: Session, *, now: datetime | None = None) -> int:
    """Hard-deletes anything that has been in the trash for more than
    `TRASH_RETENTION_DAYS` - gone for good, no activity_log entry (there is
    nothing left to point `entity_id` at)."""
    cutoff = (now or datetime.now(UTC)) - timedelta(days=TRASH_RETENTION_DAYS)
    count = 0
    for _entity, model in _TRASH_MODELS:
        rows = db.scalars(
            select(model).where(model.deleted_at.isnot(None), model.deleted_at < cutoff)
        ).all()
        for row in rows:
            if isinstance(row, Expense):
                db.query(ExpenseShare).filter(ExpenseShare.expense_id == row.id).delete()
                db.query(ShoppingItem).filter(ShoppingItem.expense_id == row.id).update(
                    {"expense_id": None}
                )
            db.delete(row)
            count += 1
    return count


def run_daily_purge(db: Session) -> dict[str, int]:
    """spec.md §8.3's daily 04:00 job: expire notes, then empty anything
    that has been in the trash for 30+ days."""
    expired_notes = purge_expired_notes(db)
    purged = purge_old_trash(db)
    return {"expired_notes": expired_notes, "purged": purged}
