import random
from datetime import date

import pytest
from sqlalchemy.orm import sessionmaker

from app.models import ExpenseShare, Member
from app.services import ledger

MEMBER_NAMES = ["Jakob", "Clara", "Daniel", "Bato"]  # position order, per seed.toml


@pytest.fixture
def seeded(session_local: sessionmaker) -> dict:
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
        db.commit()
        return {name: m.id for name, m in members.items()}


@pytest.mark.parametrize(
    "amount_cents,expense_id,expected",
    [
        (1000, 3, [334, 333, 333]),  # start = 3 % 3 = 0 -> first participant gets the extra cent
        (1000, 4, [333, 334, 333]),  # start = 4 % 3 = 1 -> second participant gets it
        (4860, 1, [1215, 1215, 1215, 1215]),
    ],
)
def test_split_matches_spec_rounding_rule(amount_cents, expense_id, expected) -> None:
    participants = [10, 20, 30] if len(expected) == 3 else [10, 20, 30, 40]
    shares = ledger.split(expense_id, amount_cents, participants)
    assert [shares[p] for p in participants] == expected
    assert sum(shares.values()) == amount_cents


def test_create_expense_matches_spec_preview_example(seeded, session_local) -> None:
    with session_local() as db:
        all_four = [seeded[n] for n in MEMBER_NAMES]

        ledger.create_expense(
            db,
            description="Großeinkauf",
            amount_cents=4860,
            paid_by_id=seeded["Clara"],
            category_id=None,
            spent_on=date(2026, 10, 18),
            participant_ids=all_four,
            created_by=seeded["Clara"],
        )
        db.flush()
        ledger.create_expense(
            db,
            description="Putzmittel & Müllbeutel",
            amount_cents=1580,
            paid_by_id=seeded["Daniel"],
            category_id=None,
            spent_on=date(2026, 10, 18),
            participant_ids=all_four,
            created_by=seeded["Daniel"],
        )
        ledger.create_expense(
            db,
            description="Klopapier & Spülmittel",
            amount_cents=1240,
            paid_by_id=seeded["Jakob"],
            category_id=None,
            spent_on=date(2026, 10, 18),
            participant_ids=all_four,
            created_by=seeded["Jakob"],
        )
        ledger.create_expense(
            db,
            description="Internet Oktober",
            amount_cents=4000,
            paid_by_id=seeded["Bato"],
            category_id=None,
            spent_on=date(2026, 10, 18),
            participant_ids=all_four,
            created_by=seeded["Bato"],
        )
        ledger.create_expense(
            db,
            description="Pizza WG-Abend",
            amount_cents=3600,
            paid_by_id=seeded["Clara"],
            category_id=None,
            spent_on=date(2026, 10, 18),
            participant_ids=[seeded["Jakob"], seeded["Clara"], seeded["Daniel"]],
            created_by=seeded["Clara"],
        )
        db.commit()

        result = ledger.balances(db)
        position_by_member = {seeded[n]: i for i, n in enumerate(MEMBER_NAMES)}

        assert result[seeded["Clara"]] == 4340
        assert result[seeded["Bato"]] == 1080
        assert result[seeded["Daniel"]] == -2540
        assert result[seeded["Jakob"]] == -2880
        assert sum(result.values()) == 0

        proposed = ledger.transfers(result, position_by_member)
        assert proposed == [
            (seeded["Jakob"], seeded["Clara"], 2880),
            (seeded["Daniel"], seeded["Clara"], 1460),
            (seeded["Daniel"], seeded["Bato"], 1080),
        ]

        ledger.create_settlement(
            db,
            from_member_id=seeded["Jakob"],
            to_member_id=seeded["Clara"],
            amount_cents=2880,
            paid_on=date(2026, 10, 18),
            note=None,
            created_by=seeded["Jakob"],
        )
        db.commit()

        after_settlement = ledger.balances(db)
        assert after_settlement[seeded["Jakob"]] == 0
        assert after_settlement[seeded["Clara"]] == 1460
        proposed_after = ledger.transfers(after_settlement, position_by_member)
        assert proposed_after == [
            (seeded["Daniel"], seeded["Clara"], 1460),
            (seeded["Daniel"], seeded["Bato"], 1080),
        ]


def test_deleted_expense_does_not_count_until_restored(seeded, session_local) -> None:
    with session_local() as db:
        all_four = [seeded[n] for n in MEMBER_NAMES]
        expense = ledger.create_expense(
            db,
            description="Test",
            amount_cents=4000,
            paid_by_id=seeded["Jakob"],
            category_id=None,
            spent_on=date(2026, 10, 18),
            participant_ids=all_four,
            created_by=seeded["Jakob"],
        )
        db.commit()
        assert ledger.balances(db)[seeded["Jakob"]] == 3000

        ledger.delete_expense(expense)
        db.commit()
        assert ledger.balances(db).get(seeded["Jakob"], 0) == 0

        ledger.restore_expense(expense)
        db.commit()
        assert ledger.balances(db)[seeded["Jakob"]] == 3000


def test_editing_an_expense_recomputes_shares(seeded, session_local) -> None:
    with session_local() as db:
        all_four = [seeded[n] for n in MEMBER_NAMES]
        expense = ledger.create_expense(
            db,
            description="Test",
            amount_cents=4000,
            paid_by_id=seeded["Jakob"],
            category_id=None,
            spent_on=date(2026, 10, 18),
            participant_ids=all_four,
            created_by=seeded["Jakob"],
        )
        db.commit()

        ledger.update_expense(
            db,
            expense,
            description="Test (bearbeitet)",
            amount_cents=3000,
            paid_by_id=seeded["Jakob"],
            category_id=None,
            spent_on=date(2026, 10, 18),
            participant_ids=[seeded["Jakob"], seeded["Clara"]],
            updated_by=seeded["Clara"],
        )
        db.commit()

        shares = db.query(ExpenseShare).filter_by(expense_id=expense.id).all()
        assert sum(s.share_cents for s in shares) == 3000
        assert {s.member_id for s in shares} == {seeded["Jakob"], seeded["Clara"]}


@pytest.mark.parametrize(
    "raw,expected_cents",
    [("6,40", 640), ("6.40", 640), ("6", 600), ("6,4", 640), ("10000", 1_000_000)],
)
def test_parse_amount_accepts_spec_examples(raw, expected_cents) -> None:
    assert ledger.parse_amount_to_cents(raw) == expected_cents


@pytest.mark.parametrize("raw", ["0", "-5", "10000.01", "abc", ""])
def test_parse_amount_rejects_invalid_input(raw) -> None:
    with pytest.raises(ledger.AmountError):
        ledger.parse_amount_to_cents(raw)


def test_ledger_properties_hold_for_randomized_cases(seeded, session_local) -> None:
    # spec.md §10.2's own "Eigenschaftstest": sum(shares) == amount,
    # sum(balances) == 0, at most n-1 transfers, and applying every
    # proposed transfer settles everyone to exactly zero.
    rng = random.Random(42)
    member_ids = list(seeded.values())
    position_by_member = dict.fromkeys(member_ids, 0)
    for i, member_id in enumerate(member_ids):
        position_by_member[member_id] = i

    with session_local() as db:
        for case in range(200):
            amount = rng.randint(1, ledger.MAX_AMOUNT_CENTS)
            participants = rng.sample(member_ids, k=rng.randint(1, len(member_ids)))
            paid_by = rng.choice(member_ids)
            expense = ledger.create_expense(
                db,
                description=f"case {case}",
                amount_cents=amount,
                paid_by_id=paid_by,
                category_id=None,
                spent_on=date(2026, 10, 18),
                participant_ids=participants,
                created_by=paid_by,
            )
            db.flush()

            shares = db.query(ExpenseShare).filter_by(expense_id=expense.id).all()
            assert sum(s.share_cents for s in shares) == amount

        db.commit()

        result = ledger.balances(db)
        assert sum(result.values()) == 0

        proposed = ledger.transfers(result, position_by_member)
        assert len(proposed) <= len(member_ids) - 1

        remaining = dict(result)
        for from_id, to_id, amount in proposed:
            remaining[from_id] += amount
            remaining[to_id] -= amount
        assert all(v == 0 for v in remaining.values())
