from app import models  # noqa: F401  # registers every table with Base.metadata
from app.db import Base

PHASE_1_TABLES = {
    "members",
    "settings",
    "chores",
    "rota_configs",
    "chore_entries",
    "chore_swaps",
    "expense_categories",
    "expenses",
    "expense_shares",
    "settlements",
    "shopping_items",
    "notes",
    "info_pages",
    "activity_log",
}


def test_all_phase1_tables_are_registered() -> None:
    assert PHASE_1_TABLES <= set(Base.metadata.tables)
