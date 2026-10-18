from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Expense, ExpenseShare, Member, Settlement

MAX_AMOUNT_CENTS = 1_000_000  # spec.md §2.3: 10,000 EUR plausibility cap


class AmountError(ValueError):
    pass


def parse_amount_to_cents(raw: str) -> int:
    """Accepts "6,40", "6.40", "6" or "6,4" - spec.md §4.4."""
    try:
        value = Decimal(raw.strip().replace(",", "."))
    except InvalidOperation as exc:
        raise AmountError("invalid") from exc
    cents = int((value * 100).to_integral_value())
    if cents <= 0 or cents > MAX_AMOUNT_CENTS:
        raise AmountError("out_of_range")
    return cents


def split(expense_id: int, amount_cents: int, participants: list[int]) -> dict[int, int]:
    """`participants` already sorted by members.position - spec.md §4.1."""
    n = len(participants)
    base, remainder = divmod(amount_cents, n)
    start = expense_id % n
    shares = dict.fromkeys(participants, base)
    for i in range(remainder):
        shares[participants[(start + i) % n]] += 1
    return shares


def sorted_by_position(db: Session, member_ids: list[int]) -> list[int]:
    rows = db.scalars(select(Member).where(Member.id.in_(member_ids)).order_by(Member.position))
    return [m.id for m in rows]


def _write_shares(db: Session, expense: Expense, participant_ids: list[int]) -> None:
    db.query(ExpenseShare).filter(ExpenseShare.expense_id == expense.id).delete()
    ordered = sorted_by_position(db, participant_ids)
    for member_id, share_cents in split(expense.id, expense.amount_cents, ordered).items():
        db.add(ExpenseShare(expense_id=expense.id, member_id=member_id, share_cents=share_cents))


def create_expense(
    db: Session,
    *,
    description: str,
    amount_cents: int,
    paid_by_id: int,
    category_id: int | None,
    spent_on: date,
    participant_ids: list[int],
    created_by: int,
) -> Expense:
    expense = Expense(
        description=description,
        amount_cents=amount_cents,
        paid_by_id=paid_by_id,
        category_id=category_id,
        spent_on=spent_on,
        created_by=created_by,
    )
    db.add(expense)
    db.flush()  # need expense.id, both as the ExpenseShare FK and split()'s rotating start index
    _write_shares(db, expense, participant_ids)
    return expense


def update_expense(
    db: Session,
    expense: Expense,
    *,
    description: str,
    amount_cents: int,
    paid_by_id: int,
    category_id: int | None,
    spent_on: date,
    participant_ids: list[int],
    updated_by: int,
) -> Expense:
    expense.description = description
    expense.amount_cents = amount_cents
    expense.paid_by_id = paid_by_id
    expense.category_id = category_id
    expense.spent_on = spent_on
    expense.updated_by = updated_by
    expense.updated_at = datetime.now(UTC)
    _write_shares(db, expense, participant_ids)
    return expense


def delete_expense(expense: Expense) -> None:
    expense.deleted_at = datetime.now(UTC)


def restore_expense(expense: Expense) -> None:
    expense.deleted_at = None


def create_settlement(
    db: Session,
    *,
    from_member_id: int,
    to_member_id: int,
    amount_cents: int,
    paid_on: date,
    note: str | None,
    created_by: int,
) -> Settlement:
    settlement = Settlement(
        from_member_id=from_member_id,
        to_member_id=to_member_id,
        amount_cents=amount_cents,
        paid_on=paid_on,
        note=note,
        created_by=created_by,
    )
    db.add(settlement)
    return settlement


def delete_settlement(settlement: Settlement) -> None:
    settlement.deleted_at = datetime.now(UTC)


def restore_settlement(settlement: Settlement) -> None:
    settlement.deleted_at = None


def total_paid(db: Session, member_id: int) -> int:
    return db.scalar(
        select(func.coalesce(func.sum(Expense.amount_cents), 0)).where(
            Expense.paid_by_id == member_id, Expense.deleted_at.is_(None)
        )
    )


def total_share(db: Session, member_id: int) -> int:
    return db.scalar(
        select(func.coalesce(func.sum(ExpenseShare.share_cents), 0))
        .join(Expense, Expense.id == ExpenseShare.expense_id)
        .where(ExpenseShare.member_id == member_id, Expense.deleted_at.is_(None))
    )


def balances(db: Session) -> dict[int, int]:
    """spec.md §4.2. Only members with at least one (non-deleted) expense,
    share or settlement appear - moved-out members keep showing up here
    until their balance is actually settled to zero, same as everyone
    else. Callers wanting every member (including untouched ones at 0)
    merge this against the member list themselves."""
    result: dict[int, int] = defaultdict(int)

    paid = db.execute(
        select(Expense.paid_by_id, func.sum(Expense.amount_cents))
        .where(Expense.deleted_at.is_(None))
        .group_by(Expense.paid_by_id)
    ).all()
    for member_id, total in paid:
        result[member_id] += total

    owed = db.execute(
        select(ExpenseShare.member_id, func.sum(ExpenseShare.share_cents))
        .join(Expense, Expense.id == ExpenseShare.expense_id)
        .where(Expense.deleted_at.is_(None))
        .group_by(ExpenseShare.member_id)
    ).all()
    for member_id, total in owed:
        result[member_id] -= total

    sent = db.execute(
        select(Settlement.from_member_id, func.sum(Settlement.amount_cents))
        .where(Settlement.deleted_at.is_(None))
        .group_by(Settlement.from_member_id)
    ).all()
    for member_id, total in sent:
        result[member_id] += total

    received = db.execute(
        select(Settlement.to_member_id, func.sum(Settlement.amount_cents))
        .where(Settlement.deleted_at.is_(None))
        .group_by(Settlement.to_member_id)
    ).all()
    for member_id, total in received:
        result[member_id] -= total

    return dict(result)


def transfers(
    balances_by_member: dict[int, int], position_by_member: dict[int, int]
) -> list[tuple[int, int, int]]:
    """Greedy largest-debtor-to-largest-creditor, per spec.md §4.3.
    Returns (from_member_id, to_member_id, amount_cents) triples, at most
    len(balances_by_member) - 1 of them."""
    debtors = [
        (-amount, member_id) for member_id, amount in balances_by_member.items() if amount < 0
    ]
    creditors = [
        (amount, member_id) for member_id, amount in balances_by_member.items() if amount > 0
    ]

    result: list[tuple[int, int, int]] = []
    while debtors and creditors:
        debtors.sort(key=lambda d: (-d[0], position_by_member.get(d[1], 0)))
        creditors.sort(key=lambda c: (-c[0], position_by_member.get(c[1], 0)))
        debt_amount, debtor_id = debtors[0]
        credit_amount, creditor_id = creditors[0]
        amount = min(debt_amount, credit_amount)
        result.append((debtor_id, creditor_id, amount))

        remaining_debt = debt_amount - amount
        remaining_credit = credit_amount - amount
        debtors[0] = (remaining_debt, debtor_id)
        creditors[0] = (remaining_credit, creditor_id)
        if remaining_debt == 0:
            debtors.pop(0)
        if remaining_credit == 0:
            creditors.pop(0)
    return result
