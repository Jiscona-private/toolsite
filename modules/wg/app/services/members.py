from __future__ import annotations

import re
import secrets
import unicodedata
from datetime import date

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
