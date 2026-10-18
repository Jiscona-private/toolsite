from __future__ import annotations

import re
import secrets
import unicodedata
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Member

# Defaults from spec.md §8.1.
DEFAULT_NOTIFY_PREFS = {
    "chore_next_week": True,
    "chore_open": True,
    "settlement_received": True,
    "expense_new": False,
    "supply_shopping": False,
    "event_tomorrow": False,
}


def slugify(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")
    return slug or "member"


def create_member(
    db: Session,
    *,
    name: str,
    color: int,
    language: str,
    position: int,
    joined_on: date,
) -> Member:
    member = Member(
        name=name,
        color=color,
        language=language,
        position=position,
        joined_on=joined_on,
        ntfy_topic=f"wg-{secrets.token_hex(4)}-{slugify(name)}",
        notify_prefs=dict(DEFAULT_NOTIFY_PREFS),
    )
    db.add(member)
    return member


def next_position(db: Session) -> int:
    positions = list(db.scalars(select(Member.position)))
    return max(positions, default=-1) + 1


def set_active(member: Member, active: bool, *, today: date) -> None:
    """spec.md members.active/left_on. Changing this is one of the §3.3
    triggers for rebuilding the rota - callers do that separately."""
    member.active = active
    member.left_on = None if active else today
