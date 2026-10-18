from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import sessionmaker

from app.models import Expense, ExpenseShare, Member, Note, ShoppingItem
from app.services import activity

MEMBER_KWARGS = dict(language="de", color=0, position=0, active=True, joined_on=date(2026, 10, 19))


def _member(db, name: str) -> Member:
    member = Member(name=name, ntfy_topic=f"wg-x-{name.lower()}", notify_prefs={}, **MEMBER_KWARGS)
    db.add(member)
    db.flush()
    return member


def test_log_creates_an_entry(session_local: sessionmaker) -> None:
    with session_local() as db:
        member = _member(db, "Jakob")
        entry = activity.log(
            db,
            actor_member_id=member.id,
            action="create",
            entity="note",
            entity_id=1,
            summary_key="log.note.create",
        )
        db.commit()
        assert entry.id is not None
        assert activity.recent(db)[0].id == entry.id


def test_recent_orders_newest_first(session_local: sessionmaker) -> None:
    with session_local() as db:
        member = _member(db, "Jakob")
        for _ in range(3):
            activity.log(
                db,
                actor_member_id=member.id,
                action="create",
                entity="note",
                summary_key="log.note.create",
            )
        db.commit()
        entries = activity.recent(db)
        assert [e.id for e in entries] == sorted((e.id for e in entries), reverse=True)


def test_trash_items_lists_soft_deleted_rows_newest_first(session_local: sessionmaker) -> None:
    with session_local() as db:
        member = _member(db, "Jakob")
        older = Note(body="older", pinned=False, expires_on=None, created_by=member.id)
        newer = Note(body="newer", pinned=False, expires_on=None, created_by=member.id)
        db.add_all([older, newer])
        db.flush()
        older.deleted_at = datetime.now(UTC) - timedelta(days=1)
        newer.deleted_at = datetime.now(UTC)
        db.commit()

        items = activity.trash_items(db)
        assert [i["row"].body for i in items] == ["newer", "older"]
        assert {i["entity"] for i in items} == {"note"}


def test_restore_unsets_deleted_at(session_local: sessionmaker) -> None:
    with session_local() as db:
        member = _member(db, "Jakob")
        note = Note(body="x", pinned=False, expires_on=None, created_by=member.id)
        db.add(note)
        db.flush()
        note.deleted_at = datetime.now(UTC)
        db.commit()

        restored = activity.restore(db, entity="note", entity_id=note.id)
        assert restored is not None
        assert restored.deleted_at is None


def test_restore_returns_none_for_unknown_entity_or_not_deleted(
    session_local: sessionmaker,
) -> None:
    with session_local() as db:
        member = _member(db, "Jakob")
        note = Note(body="x", pinned=False, expires_on=None, created_by=member.id)
        db.add(note)
        db.flush()
        db.commit()

        assert activity.restore(db, entity="note", entity_id=note.id) is None  # not deleted
        assert activity.restore(db, entity="unknown", entity_id=1) is None
        assert activity.restore(db, entity="note", entity_id=999999) is None


def test_purge_expired_notes_soft_deletes_and_logs(session_local: sessionmaker) -> None:
    with session_local() as db:
        member = _member(db, "Jakob")
        expired = Note(
            body="gone", pinned=False, expires_on=date(2026, 10, 1), created_by=member.id
        )
        still_valid = Note(
            body="stays", pinned=False, expires_on=date(2099, 1, 1), created_by=member.id
        )
        no_expiry = Note(body="forever", pinned=False, expires_on=None, created_by=member.id)
        db.add_all([expired, still_valid, no_expiry])
        db.commit()

        count = activity.purge_expired_notes(db, today=date(2026, 10, 18))
        db.commit()

        assert count == 1
        assert db.get(Note, expired.id).deleted_at is not None
        assert db.get(Note, still_valid.id).deleted_at is None
        assert db.get(Note, no_expiry.id).deleted_at is None
        log_entry = activity.recent(db)[0]
        assert log_entry.summary_key == "log.note.expired"
        assert log_entry.actor_member_id is None


def test_purge_old_trash_hard_deletes_after_retention_window(session_local: sessionmaker) -> None:
    with session_local() as db:
        member = _member(db, "Jakob")
        old_note = Note(body="old", pinned=False, expires_on=None, created_by=member.id)
        recent_note = Note(body="recent", pinned=False, expires_on=None, created_by=member.id)
        db.add_all([old_note, recent_note])
        db.flush()
        old_note.deleted_at = datetime.now(UTC) - timedelta(days=31)
        recent_note.deleted_at = datetime.now(UTC) - timedelta(days=5)
        db.commit()

        count = activity.purge_old_trash(db)
        db.commit()

        assert count == 1
        assert db.get(Note, old_note.id) is None
        assert db.get(Note, recent_note.id) is not None


def test_purge_old_trash_clears_expense_shares_and_shopping_links(
    session_local: sessionmaker,
) -> None:
    """Hard-deleting an old, trashed expense must not violate the FK from
    expense_shares or shopping_items.expense_id (SQLite runs with
    foreign_keys=ON, see app/db.py)."""
    with session_local() as db:
        member = _member(db, "Jakob")
        expense = Expense(
            description="Großeinkauf",
            amount_cents=1000,
            paid_by_id=member.id,
            spent_on=date(2026, 10, 1),
            created_by=member.id,
        )
        db.add(expense)
        db.flush()
        db.add(ExpenseShare(expense_id=expense.id, member_id=member.id, share_cents=1000))
        item = ShoppingItem(
            name="Milch", source="manual", added_by=member.id, expense_id=expense.id
        )
        db.add(item)
        db.flush()
        expense.deleted_at = datetime.now(UTC) - timedelta(days=31)
        db.commit()

        count = activity.purge_old_trash(db)
        db.commit()

        assert count == 1
        assert db.get(Expense, expense.id) is None
        assert db.get(ShoppingItem, item.id).expense_id is None


def test_run_daily_purge_combines_both_jobs(session_local: sessionmaker) -> None:
    with session_local() as db:
        member = _member(db, "Jakob")
        expired_note = Note(
            body="gone", pinned=False, expires_on=date(2020, 1, 1), created_by=member.id
        )
        old_trashed = Note(body="old", pinned=False, expires_on=None, created_by=member.id)
        db.add_all([expired_note, old_trashed])
        db.flush()
        old_trashed.deleted_at = datetime.now(UTC) - timedelta(days=31)
        db.commit()

        result = activity.run_daily_purge(db)
        db.commit()

        assert result == {"expired_notes": 1, "purged": 1}
