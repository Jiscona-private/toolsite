from datetime import date

import pytest
from sqlalchemy.orm import sessionmaker

from app.models import Chore, ChoreSwap, Member, RotaConfig
from app.services import rota
from app.timezone import week_start

CHORE_KEYS = ["floor", "kitchen", "big_bath", "small_bath"]
MEMBER_NAMES = ["Jakob", "Clara", "Daniel", "Bato"]  # position order, per seed.toml


@pytest.fixture
def seeded(session_local: sessionmaker) -> dict:
    """The exact seed configuration from spec.md §10.1's own test table."""
    with session_local() as db:
        members = {}
        for position, name in enumerate(MEMBER_NAMES):
            member = Member(
                name=name,
                language="de",
                color=position,
                position=position,
                active=True,
                joined_on=date(2026, 10, 19),
                ntfy_topic=f"wg-aaaaaaa{position}-{name.lower()}",
                notify_prefs={},
            )
            db.add(member)
            members[name] = member
        db.flush()

        chores = {}
        for position, key in enumerate(CHORE_KEYS):
            chore = Chore(key=key, name_de=key, name_en=key, position=position)
            db.add(chore)
            chores[key] = chore
        db.flush()

        # slots in rotation order (= chore_ids order): floor, kitchen, big_bath, small_bath
        db.add(
            RotaConfig(
                valid_from=date(2026, 10, 19),
                chore_ids=[chores[k].id for k in CHORE_KEYS],
                slots=[
                    members["Clara"].id,
                    members["Bato"].id,
                    members["Jakob"].id,
                    members["Daniel"].id,
                ],
                created_by=None,
            )
        )
        db.commit()

        return {
            "member_id": {name: m.id for name, m in members.items()},
            "chore_id": {key: c.id for key, c in chores.items()},
        }


def _names(assignment_map: dict[int, int | None], seeded: dict) -> dict[str, str | None]:
    id_to_name = {v: k for k, v in seeded["member_id"].items()}
    id_to_key = {v: k for k, v in seeded["chore_id"].items()}
    return {
        id_to_key[chore_id]: (id_to_name.get(member_id) if member_id else None)
        for chore_id, member_id in assignment_map.items()
    }


def _week(floor: str, kitchen: str, big_bath: str, small_bath: str) -> dict[str, str]:
    return {"floor": floor, "kitchen": kitchen, "big_bath": big_bath, "small_bath": small_bath}


ROTATION_TABLE = [
    (date(2026, 10, 19), _week("Clara", "Bato", "Jakob", "Daniel")),
    (date(2026, 10, 26), _week("Daniel", "Clara", "Bato", "Jakob")),
    (date(2026, 11, 2), _week("Jakob", "Daniel", "Clara", "Bato")),
    (date(2026, 11, 9), _week("Bato", "Jakob", "Daniel", "Clara")),
    (date(2026, 11, 16), _week("Clara", "Bato", "Jakob", "Daniel")),
]


@pytest.mark.parametrize("week,expected", ROTATION_TABLE)
def test_rotation_matches_spec_table(seeded, session_local, week, expected) -> None:
    with session_local() as db:
        result = rota.assignment(db, week)
    assert _names(result, seeded) == expected


def test_week_before_start_has_empty_assignment(seeded, session_local) -> None:
    with session_local() as db:
        result = rota.assignment(db, date(2026, 10, 12))
    assert result == {}


def test_skip_does_not_change_later_rotation(seeded, session_local) -> None:
    with session_local() as db:
        rota.mark_skipped(
            db,
            week=date(2026, 10, 19),
            chore_id=seeded["chore_id"]["big_bath"],
            assigned_member_id=seeded["member_id"]["Jakob"],
            done_by=seeded["member_id"]["Jakob"],
            reason="krank",
        )
        db.commit()

        next_week = rota.assignment(db, date(2026, 10, 26))
    assert _names(next_week, seeded)["small_bath"] == "Jakob"


def test_swap_trades_chores_for_one_week_only(seeded, session_local) -> None:
    with session_local() as db:
        db.add(
            ChoreSwap(
                week=date(2026, 10, 26),
                member_a_id=seeded["member_id"]["Jakob"],
                member_b_id=seeded["member_id"]["Clara"],
                created_by=seeded["member_id"]["Jakob"],
            )
        )
        db.commit()

        swapped_week = rota.assignment(db, date(2026, 10, 26))
        following_week = rota.assignment(db, date(2026, 11, 2))

    names = _names(swapped_week, seeded)
    assert names["kitchen"] == "Jakob"
    assert names["small_bath"] == "Clara"
    assert _names(following_week, seeded) == dict(ROTATION_TABLE[2][1])


def test_new_member_joins_free_slot_from_effective_week(seeded, session_local) -> None:
    with session_local() as db:
        eva = Member(
            name="Eva",
            language="de",
            color=4,
            position=4,
            active=True,
            joined_on=date(2026, 11, 2),
            ntfy_topic="wg-aaaaaaa4-eva",
            notify_prefs={},
        )
        db.add(eva)
        db.flush()

        member_order = [
            seeded["member_id"]["Clara"],
            seeded["member_id"]["Bato"],
            seeded["member_id"]["Jakob"],
            seeded["member_id"]["Daniel"],
            eva.id,
        ]
        chore_order = [seeded["chore_id"][k] for k in CHORE_KEYS]
        rota.rebuild_rota(
            db,
            effective_from=date(2026, 11, 2),
            member_ids_in_position_order=member_order,
            chore_ids_in_order=chore_order,
            created_by=seeded["member_id"]["Jakob"],
        )
        db.commit()

        week_45 = _names(
            rota.assignment(db, date(2026, 11, 2)),
            {**seeded, "member_id": {**seeded["member_id"], "Eva": eva.id}},
        )
        week_46 = _names(
            rota.assignment(db, date(2026, 11, 9)),
            {**seeded, "member_id": {**seeded["member_id"], "Eva": eva.id}},
        )

    assert week_45 == {
        "floor": "Jakob",
        "kitchen": "Daniel",
        "big_bath": "Clara",
        "small_bath": "Bato",
    }
    assert week_46 == {
        "floor": "Eva",
        "kitchen": "Jakob",
        "big_bath": "Daniel",
        "small_bath": "Clara",
    }


def test_member_moving_out_leaves_their_chore_unfilled(seeded, session_local) -> None:
    with session_local() as db:
        member_order = [
            seeded["member_id"]["Jakob"],
            seeded["member_id"]["Clara"],
            seeded["member_id"]["Bato"],
        ]
        chore_order = [seeded["chore_id"][k] for k in CHORE_KEYS]
        rota.rebuild_rota(
            db,
            effective_from=date(2026, 11, 2),
            member_ids_in_position_order=member_order,
            chore_ids_in_order=chore_order,
            created_by=seeded["member_id"]["Jakob"],
        )
        db.commit()

        week_45 = _names(rota.assignment(db, date(2026, 11, 2)), seeded)

    assert week_45 == {"floor": "Jakob", "kitchen": None, "big_bath": "Clara", "small_bath": "Bato"}


def test_week_start_is_monday_boundary() -> None:
    assert week_start(date(2026, 10, 25)) == date(2026, 10, 19)  # Sunday -> previous Monday
    assert week_start(date(2026, 10, 26)) == date(2026, 10, 26)  # Monday -> itself


def test_chore_status_entry_wins_over_computed_status(seeded, session_local) -> None:
    with session_local() as db:
        rota.mark_done(
            db,
            week=date(2026, 10, 19),
            chore_id=seeded["chore_id"]["floor"],
            assigned_member_id=seeded["member_id"]["Clara"],
            done_by=seeded["member_id"]["Daniel"],  # substitution
        )
        db.commit()

        status, entry = rota.chore_status(
            db,
            week=date(2026, 10, 19),
            chore_id=seeded["chore_id"]["floor"],
            assigned_member_id=seeded["member_id"]["Clara"],
            today=date(2026, 10, 19),
        )
    assert status == rota.STATUS_DONE
    assert entry is not None
    assert entry.done_by_member_id == seeded["member_id"]["Daniel"]


def test_chore_status_is_missed_for_past_week_without_entry(seeded, session_local) -> None:
    with session_local() as db:
        status, entry = rota.chore_status(
            db,
            week=date(2026, 10, 19),
            chore_id=seeded["chore_id"]["floor"],
            assigned_member_id=seeded["member_id"]["Clara"],
            today=date(2026, 11, 2),
        )
    assert status == rota.STATUS_MISSED
    assert entry is None


def test_chore_status_is_open_for_current_week_without_entry(seeded, session_local) -> None:
    with session_local() as db:
        status, entry = rota.chore_status(
            db,
            week=date(2026, 10, 19),
            chore_id=seeded["chore_id"]["floor"],
            assigned_member_id=seeded["member_id"]["Clara"],
            today=date(2026, 10, 20),
        )
    assert status == rota.STATUS_OPEN
    assert entry is None


def test_undo_removes_the_entry(seeded, session_local) -> None:
    with session_local() as db:
        rota.mark_done(
            db,
            week=date(2026, 10, 19),
            chore_id=seeded["chore_id"]["floor"],
            assigned_member_id=seeded["member_id"]["Clara"],
            done_by=seeded["member_id"]["Clara"],
        )
        db.commit()

        assert rota.undo(db, week=date(2026, 10, 19), chore_id=seeded["chore_id"]["floor"])
        db.commit()

        assert rota.get_chore_entry(db, date(2026, 10, 19), seeded["chore_id"]["floor"]) is None


def test_undo_on_missing_entry_returns_false(seeded, session_local) -> None:
    with session_local() as db:
        assert not rota.undo(db, week=date(2026, 10, 19), chore_id=seeded["chore_id"]["floor"])


def test_latest_rota_config_breaks_ties_on_the_newer_row(seeded, session_local) -> None:
    # Two configs can share a valid_from (e.g. a membership change rebuilt
    # "this week" twice before anyone looked at the preview) - the one
    # inserted later must win, not whichever the database happens to
    # return first for an unordered tie.
    with session_local() as db:
        rota.rebuild_rota(
            db,
            effective_from=date(2026, 10, 19),
            member_ids_in_position_order=[seeded["member_id"]["Clara"]],
            chore_ids_in_order=[seeded["chore_id"]["floor"]],
            created_by=None,
        )
        db.commit()

        config = rota.latest_rota_config(db, date(2026, 10, 19))
    assert config.slots == [seeded["member_id"]["Clara"]]
