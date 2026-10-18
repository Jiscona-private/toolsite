from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_csrf
from app.config import settings
from app.db import get_db
from app.models import Expense, ExpenseCategory, ExpenseShare, Member, Settlement, ShoppingItem
from app.services import ledger, shopping
from app.templating import base_context, templates
from app.timezone import berlin_today

router = APIRouter(prefix=f"{settings.base_path}/expenses")
settlements_router = APIRouter(prefix=f"{settings.base_path}/settlements")

MAX_FUTURE_DAYS = 365


def _active_members(db: Session) -> list[Member]:
    return list(db.scalars(select(Member).where(Member.active.is_(True)).order_by(Member.position)))


def _active_categories(db: Session) -> list[ExpenseCategory]:
    return list(
        db.scalars(
            select(ExpenseCategory)
            .where(ExpenseCategory.active.is_(True))
            .order_by(ExpenseCategory.position)
        )
    )


def _participant_ids(db: Session, expense_id: int) -> set[int]:
    return set(
        db.scalars(select(ExpenseShare.member_id).where(ExpenseShare.expense_id == expense_id))
    )


def _participants_label(db, expense_id: int, active_members: list[Member], t) -> str:
    participant_ids = _participant_ids(db, expense_id)
    active_ids = {m.id for m in active_members}
    if active_ids and active_ids <= participant_ids:
        return t("expenses.participants_all", count=len(participant_ids))
    missing = [m.name for m in active_members if m.id not in participant_ids]
    if missing:
        return t("expenses.participants_without", names=", ".join(missing))
    return t("expenses.participants_all", count=len(participant_ids))


def _expense_view(db: Session, expense: Expense, active_members: list[Member], t) -> dict:
    return {
        "expense": expense,
        "participants_label": _participants_label(db, expense.id, active_members, t),
    }


def _transfer_label(t, from_member: Member, to_member: Member, my_id: int) -> str:
    if from_member.id == my_id:
        return t("expenses.you_to", name=to_member.name)
    if to_member.id == my_id:
        return t("expenses.name_to_you", name=from_member.name)
    return t("expenses.name_to_name", from_name=from_member.name, to_name=to_member.name)


@router.get("")
def expenses_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    my_id = request.state.member_id
    members = {m.id: m for m in db.scalars(select(Member))}
    active_members = _active_members(db)

    context = base_context(request, db, active_nav="expenses")
    t = context["t"]

    balances_by_member = ledger.balances(db)
    position_by_member = {m.id: m.position for m in members.values()}
    proposed = ledger.transfers(balances_by_member, position_by_member)
    transfer_rows = [
        {
            "from_member": members[from_id],
            "to_member": members[to_id],
            "amount_cents": amount,
            "label": _transfer_label(t, members[from_id], members[to_id], my_id),
        }
        for from_id, to_id, amount in proposed
    ]
    # my own transfer(s) first, per design.md §5.5
    transfer_rows.sort(
        key=lambda row: not (row["from_member"].id == my_id or row["to_member"].id == my_id)
    )

    recent = list(
        db.scalars(
            select(Expense)
            .where(Expense.deleted_at.is_(None))
            .order_by(Expense.spent_on.desc(), Expense.id.desc())
            .limit(3)
        )
    )
    total_count = db.scalar(
        select(func.count()).select_from(Expense).where(Expense.deleted_at.is_(None))
    )

    context.update(
        {
            "my_paid": ledger.total_paid(db, my_id),
            "my_share": ledger.total_share(db, my_id),
            "my_balance": balances_by_member.get(my_id, 0),
            "other_balances": [
                (m, balances_by_member.get(m.id, 0)) for m in active_members if m.id != my_id
            ],
            "transfer_rows": transfer_rows,
            "recent": [_expense_view(db, e, active_members, t) for e in recent],
            "recent_total_count": total_count,
        }
    )
    return templates.TemplateResponse(request, "pages/expenses.html", context)


@router.get("/all")
def expenses_all_page(
    request: Request, month: str | None = None, db: Session = Depends(get_db)
) -> HTMLResponse:
    active_members = _active_members(db)
    query = select(Expense).where(Expense.deleted_at.is_(None)).order_by(Expense.spent_on.desc())
    expenses = list(db.scalars(query))
    if month:
        expenses = [e for e in expenses if e.spent_on.strftime("%Y-%m") == month]

    context = base_context(request, db, active_nav="expenses")
    context.update(
        {
            "items": [_expense_view(db, e, active_members, context["t"]) for e in expenses],
            "month": month,
        }
    )
    return templates.TemplateResponse(request, "pages/expenses_all.html", context)


def _form_context(
    request: Request,
    db: Session,
    *,
    expense: Expense | None,
    error: str | None,
) -> dict:
    context = base_context(request, db, active_nav="expenses")
    selected_participants = (
        _participant_ids(db, expense.id) if expense else {m.id for m in _active_members(db)}
    )
    context.update(
        {
            "expense": expense,
            "members": _active_members(db),
            "categories": _active_categories(db),
            "selected_participants": selected_participants,
            "error": error,
            "today": berlin_today(),
        }
    )
    return context


@router.get("/new")
def new_expense_form(
    request: Request, items: str | None = None, db: Session = Depends(get_db)
) -> HTMLResponse:
    context = _form_context(request, db, expense=None, error=None)
    if items:
        item_ids = [int(i) for i in items.split(",") if i.strip().isdigit()]
        names = [
            i.name for i in db.scalars(select(ShoppingItem).where(ShoppingItem.id.in_(item_ids)))
        ]
        context["prefill_description"] = ", ".join(names)
        context["items_raw"] = items
    return templates.TemplateResponse(request, "pages/expense_form.html", context)


def _parse_expense_form(
    db: Session,
    *,
    description: str,
    amount: str,
    paid_by_id: int,
    category_id: int | None,
    spent_on_raw: str,
    participant_ids: list[int],
) -> tuple[int, date, list[int]] | str:
    """Returns (amount_cents, spent_on, participant_ids) or an error key."""
    try:
        amount_cents = ledger.parse_amount_to_cents(amount)
    except ledger.AmountError:
        return "amount"

    if not participant_ids:
        return "participants"

    try:
        spent_on = date.fromisoformat(spent_on_raw)
    except ValueError:
        return "date"
    if spent_on > berlin_today() + timedelta(days=MAX_FUTURE_DAYS):
        return "date"

    return amount_cents, spent_on, participant_ids


@router.post("/new", dependencies=[Depends(require_csrf)])
def create_expense(
    request: Request,
    description: str = Form(...),
    amount: str = Form(...),
    paid_by_id: int = Form(...),
    category_id: int | None = Form(None),
    spent_on: str = Form(...),
    participants: list[int] = Form(default_factory=list),
    items: str | None = Form(None),
    db: Session = Depends(get_db),
) -> Response:
    parsed = _parse_expense_form(
        db,
        description=description,
        amount=amount,
        paid_by_id=paid_by_id,
        category_id=category_id,
        spent_on_raw=spent_on,
        participant_ids=participants,
    )
    if isinstance(parsed, str):
        return templates.TemplateResponse(
            request,
            "pages/expense_form.html",
            _form_context(request, db, expense=None, error=parsed),
            status_code=400,
        )
    amount_cents, spent_on_date, participant_ids = parsed

    expense = ledger.create_expense(
        db,
        description=description.strip(),
        amount_cents=amount_cents,
        paid_by_id=paid_by_id,
        category_id=category_id,
        spent_on=spent_on_date,
        participant_ids=participant_ids,
        created_by=request.state.member_id,
    )
    if items:
        item_ids = [int(i) for i in items.split(",") if i.strip().isdigit()]
        db.flush()
        shopping.mark_as_expense(db, item_ids, expense.id)
    db.commit()
    return RedirectResponse(f"{settings.base_path}/expenses", status_code=303)


@router.get("/{expense_id}/edit")
def edit_expense_form(
    expense_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    expense = db.get(Expense, expense_id)
    return templates.TemplateResponse(
        request, "pages/expense_form.html", _form_context(request, db, expense=expense, error=None)
    )


@router.post("/{expense_id}/edit", dependencies=[Depends(require_csrf)])
def update_expense(
    expense_id: int,
    request: Request,
    description: str = Form(...),
    amount: str = Form(...),
    paid_by_id: int = Form(...),
    category_id: int | None = Form(None),
    spent_on: str = Form(...),
    participants: list[int] = Form(default_factory=list),
    db: Session = Depends(get_db),
) -> Response:
    expense = db.get(Expense, expense_id)
    parsed = _parse_expense_form(
        db,
        description=description,
        amount=amount,
        paid_by_id=paid_by_id,
        category_id=category_id,
        spent_on_raw=spent_on,
        participant_ids=participants,
    )
    if isinstance(parsed, str):
        return templates.TemplateResponse(
            request,
            "pages/expense_form.html",
            _form_context(request, db, expense=expense, error=parsed),
            status_code=400,
        )
    amount_cents, spent_on_date, participant_ids = parsed

    ledger.update_expense(
        db,
        expense,
        description=description.strip(),
        amount_cents=amount_cents,
        paid_by_id=paid_by_id,
        category_id=category_id,
        spent_on=spent_on_date,
        participant_ids=participant_ids,
        updated_by=request.state.member_id,
    )
    db.commit()
    return RedirectResponse(f"{settings.base_path}/expenses", status_code=303)


@router.post("/{expense_id}/delete", dependencies=[Depends(require_csrf)])
def delete_expense_route(expense_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    expense = db.get(Expense, expense_id)
    if expense is not None:
        ledger.delete_expense(expense)
        db.commit()
    return RedirectResponse(f"{settings.base_path}/expenses", status_code=303)


@settlements_router.post("", dependencies=[Depends(require_csrf)])
def create_settlement(
    request: Request,
    to_member_id: int = Form(...),
    amount: str = Form(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        amount_cents = ledger.parse_amount_to_cents(amount)
    except ledger.AmountError:
        return RedirectResponse(f"{settings.base_path}/expenses?error=amount", status_code=303)

    ledger.create_settlement(
        db,
        from_member_id=request.state.member_id,
        to_member_id=to_member_id,
        amount_cents=amount_cents,
        paid_on=berlin_today(),
        note=None,
        created_by=request.state.member_id,
    )
    db.commit()
    return RedirectResponse(f"{settings.base_path}/expenses", status_code=303)


@settlements_router.post("/{settlement_id}/delete", dependencies=[Depends(require_csrf)])
def delete_settlement_route(settlement_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    settlement = db.get(Settlement, settlement_id)
    if settlement is not None:
        ledger.delete_settlement(settlement)
        db.commit()
    return RedirectResponse(f"{settings.base_path}/expenses", status_code=303)
