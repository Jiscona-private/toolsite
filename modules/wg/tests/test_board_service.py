from datetime import date, timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from app.models import InfoPage, Member
from app.services import board
from app.timezone import berlin_today


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


def test_active_notes_puts_pinned_first_then_newest(jakob_id, session_local) -> None:
    with session_local() as db:
        board.create_note(db, body="first", pinned=False, expires_on=None, created_by=jakob_id)
        board.create_note(db, body="second", pinned=False, expires_on=None, created_by=jakob_id)
        board.create_note(db, body="pinned", pinned=True, expires_on=None, created_by=jakob_id)
        db.commit()

        notes = board.active_notes(db)
        assert [n.body for n in notes] == ["pinned", "second", "first"]


def test_active_notes_excludes_expired(jakob_id, session_local) -> None:
    with session_local() as db:
        yesterday = berlin_today() - timedelta(days=1)
        tomorrow = berlin_today() + timedelta(days=1)
        board.create_note(
            db, body="expired", pinned=False, expires_on=yesterday, created_by=jakob_id
        )
        board.create_note(
            db, body="still valid", pinned=False, expires_on=tomorrow, created_by=jakob_id
        )
        db.commit()

        notes = board.active_notes(db)
        assert [n.body for n in notes] == ["still valid"]


def test_active_notes_excludes_deleted(jakob_id, session_local) -> None:
    with session_local() as db:
        note = board.create_note(
            db, body="gone", pinned=False, expires_on=None, created_by=jakob_id
        )
        db.commit()
        board.delete_note(note)
        db.commit()

        assert board.active_notes(db) == []


def test_update_info_page_sets_metadata(jakob_id, session_local) -> None:
    with session_local() as db:
        page = InfoPage(title="WLAN", body="old", position=0)
        db.add(page)
        db.commit()

        board.update_info_page(db, page, title="WLAN", body="new body", updated_by=jakob_id)
        db.commit()

        assert page.body == "new body"
        assert page.updated_by == jakob_id
        assert page.updated_at is not None


def test_list_info_pages_ordered_by_position(session_local) -> None:
    with session_local() as db:
        db.add(InfoPage(title="B", body="", position=1))
        db.add(InfoPage(title="A", body="", position=0))
        db.commit()

        pages = board.list_info_pages(db)
        assert [p.title for p in pages] == ["A", "B"]
