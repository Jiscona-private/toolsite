from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# CLAUDE.md rule 8: all business timestamps/dates are Europe/Berlin, with
# zoneinfo (not a fixed offset) so the 2026-10-25 DST change is handled
# correctly for free - a local calendar date simply ends at local midnight.
BERLIN = ZoneInfo("Europe/Berlin")


def berlin_now() -> datetime:
    return datetime.now(BERLIN)


def berlin_today() -> date:
    return berlin_now().date()


def week_start(value: date) -> date:
    """The Monday of the week `value` falls in."""
    return value - timedelta(days=value.weekday())
