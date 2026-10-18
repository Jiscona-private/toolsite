from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InfoPage, Note
from app.timezone import berlin_today


def active_notes(db: Session) -> list[Note]:
    """Pinned first, then newest - spec.md §5.4. Expired notes (job-pruned
    in Phase 2) are already excluded from view here."""
    today = berlin_today()
    notes = db.scalars(
        select(Note)
        .where(Note.deleted_at.is_(None))
        .order_by(Note.pinned.desc(), Note.created_at.desc())
    )
    return [n for n in notes if n.expires_on is None or n.expires_on >= today]


def create_note(
    db: Session, *, body: str, pinned: bool, expires_on: date | None, created_by: int
) -> Note:
    note = Note(body=body.strip(), pinned=pinned, expires_on=expires_on, created_by=created_by)
    db.add(note)
    return note


def delete_note(note: Note) -> None:
    note.deleted_at = datetime.now(UTC)


def restore_note(note: Note) -> None:
    note.deleted_at = None


def list_info_pages(db: Session) -> list[InfoPage]:
    return list(db.scalars(select(InfoPage).order_by(InfoPage.position)))


def update_info_page(
    db: Session, page: InfoPage, *, title: str, body: str, updated_by: int
) -> InfoPage:
    page.title = title.strip()
    page.body = body.strip()
    page.updated_by = updated_by
    page.updated_at = datetime.now(UTC)
    return page
