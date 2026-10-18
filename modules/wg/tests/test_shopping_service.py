from datetime import date

import pytest
from sqlalchemy.orm import sessionmaker

from app.models import Expense, Member
from app.services import shopping


@pytest.fixture
def jakob_id(session_local: sessionmaker) -> int:
    with session_local() as db:
        member = Member(
            name="Jakob",
            language="de",
            color=0,
            position=0,
            active=True,
            joined_on=date(2026, 10, 19),
            ntfy_topic="wg-aaaaaaaa-jakob",
            notify_prefs={},
        )
        db.add(member)
        db.commit()
        return member.id


def test_add_item_and_find_open_duplicate_case_insensitive(jakob_id, session_local) -> None:
    with session_local() as db:
        shopping.add_item(db, name="Klopapier", quantity="1 Paket", note=None, added_by=jakob_id)
        db.commit()

        duplicate = shopping.find_open_duplicate(db, "klopapier")
        assert duplicate is not None
        assert duplicate.name == "Klopapier"
        assert shopping.find_open_duplicate(db, "Spülmittel") is None


def test_toggle_checked_round_trips(jakob_id, session_local) -> None:
    with session_local() as db:
        item = shopping.add_item(db, name="Seife", quantity=None, note=None, added_by=jakob_id)
        db.commit()
        assert item.checked_at is None

        shopping.toggle_checked(item, jakob_id)
        db.commit()
        assert item.checked_at is not None
        assert item.checked_by == jakob_id

        shopping.toggle_checked(item, jakob_id)
        db.commit()
        assert item.checked_at is None
        assert item.checked_by is None


def test_archive_checked_only_touches_checked_open_items(jakob_id, session_local) -> None:
    with session_local() as db:
        unchecked = shopping.add_item(db, name="A", quantity=None, note=None, added_by=jakob_id)
        checked = shopping.add_item(db, name="B", quantity=None, note=None, added_by=jakob_id)
        db.commit()
        shopping.toggle_checked(checked, jakob_id)
        db.commit()

        archived_count = shopping.archive_checked(db)
        db.commit()

        assert archived_count == 1
        assert unchecked.archived_at is None
        assert checked.archived_at is not None


def test_archived_items_no_longer_count_as_open(jakob_id, session_local) -> None:
    with session_local() as db:
        item = shopping.add_item(db, name="Handtücher", quantity=None, note=None, added_by=jakob_id)
        db.commit()
        assert shopping.find_open_duplicate(db, "Handtücher") is not None

        shopping.toggle_checked(item, jakob_id)
        shopping.archive_checked(db)
        db.commit()

        assert shopping.find_open_duplicate(db, "Handtücher") is None
        assert item not in shopping.open_items(db)


def test_mark_as_expense_links_and_archives(jakob_id, session_local) -> None:
    with session_local() as db:
        item = shopping.add_item(db, name="Eier", quantity=None, note=None, added_by=jakob_id)
        expense = Expense(
            description="Eier",
            amount_cents=350,
            paid_by_id=jakob_id,
            category_id=None,
            spent_on=date(2026, 10, 18),
            created_by=jakob_id,
        )
        db.add(expense)
        db.commit()

        shopping.mark_as_expense(db, [item.id], expense_id=expense.id)
        db.commit()

        assert item.expense_id == expense.id
        assert item.archived_at is not None
