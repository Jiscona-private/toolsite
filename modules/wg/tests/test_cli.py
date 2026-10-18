from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app import cli
from app.models import Chore, ExpenseCategory, InfoPage, Member, RotaConfig, Setting

SEED_TOML = """
[wg]
name = "Test-WG"
timezone = "Europe/Berlin"
default_language = "de"

[[members]]
name = "Jakob"
color = 0
language = "de"

[[members]]
name = "Clara"
color = 1
language = "de"

[[chores]]
key = "floor"
name_de = "Boden"
name_en = "Floor"

[[chores]]
key = "kitchen"
name_de = "Kueche"
name_en = "Kitchen"

[rota]
start_week = "2026-10-19"

[rota.start]
floor = "Clara"
kitchen = "Jakob"

[[expense_categories]]
key = "groceries"
name_de = "Lebensmittel"
name_en = "Groceries"

[[info_pages]]
title = "WLAN"
body = "Netz: x"
"""


@pytest.fixture(autouse=True)
def _use_test_db(monkeypatch: pytest.MonkeyPatch, session_local: sessionmaker) -> None:
    monkeypatch.setattr(cli, "SessionLocal", session_local)


@pytest.fixture
def seed_path(tmp_path: Path) -> Path:
    path = tmp_path / "seed.toml"
    path.write_text(SEED_TOML)
    return path


def test_init_seeds_members_chores_categories_and_token(
    seed_path: Path, session_local: sessionmaker
) -> None:
    cli.cmd_init(seed_path)

    with session_local() as db:
        members = db.scalars(select(Member).order_by(Member.position)).all()
        assert [m.name for m in members] == ["Jakob", "Clara"]
        assert members[0].ntfy_topic.startswith("wg-")

        chores = db.scalars(select(Chore).order_by(Chore.position)).all()
        assert [c.key for c in chores] == ["floor", "kitchen"]

        rota = db.scalars(select(RotaConfig)).one()
        assert rota.valid_from == date(2026, 10, 19)
        jakob, clara = members
        floor_chore, kitchen_chore = chores
        assert rota.slots[rota.chore_ids.index(floor_chore.id)] == clara.id
        assert rota.slots[rota.chore_ids.index(kitchen_chore.id)] == jakob.id

        assert [c.key for c in db.scalars(select(ExpenseCategory))] == ["groceries"]
        assert [p.title for p in db.scalars(select(InfoPage))] == ["WLAN"]

        assert db.get(Setting, "wg_name").value == "Test-WG"
        assert db.get(Setting, "cookie_version").value == "1"
        assert len(db.get(Setting, "join_token").value) > 20


def test_init_refuses_non_empty_db(seed_path: Path, session_local: sessionmaker) -> None:
    with session_local() as db:
        db.add(Setting(key="wg_name", value="x"))
        db.commit()

    with pytest.raises(SystemExit):
        cli.cmd_init(seed_path)


def test_rotate_link_replaces_token(seed_path: Path, session_local: sessionmaker) -> None:
    cli.cmd_init(seed_path)
    with session_local() as db:
        old_token = db.get(Setting, "join_token").value

    cli.cmd_rotate_link()

    with session_local() as db:
        new_token = db.get(Setting, "join_token").value
    assert new_token != old_token


def test_logout_all_increments_cookie_version(seed_path: Path, session_local: sessionmaker) -> None:
    cli.cmd_init(seed_path)

    cli.cmd_logout_all()

    with session_local() as db:
        assert db.get(Setting, "cookie_version").value == "2"


def test_add_member_appends_next_position(seed_path: Path, session_local: sessionmaker) -> None:
    cli.cmd_init(seed_path)

    cli.cmd_add_member("Eva")

    with session_local() as db:
        members = db.scalars(select(Member).order_by(Member.position)).all()
        assert [m.name for m in members] == ["Jakob", "Clara", "Eva"]
        assert members[-1].position == 2
