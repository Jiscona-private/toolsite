from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Member
from app.services import board, ledger, rota, shopping
from app.templating import base_context, templates
from app.timezone import berlin_today, week_start

router = APIRouter(prefix=settings.base_path)


def _hero(db: Session, week, my_member_id: int, chores: list, members: dict[int, Member]) -> dict:
    assignment_map = rota.assignment(db, week)
    my_chore = next((c for c in chores if assignment_map.get(c.id) == my_member_id), None)
    if my_chore is None:
        return {"state": "free", "chore": None, "reason": None}

    status, entry = rota.chore_status(db, week, my_chore.id, my_member_id, today=berlin_today())
    return {
        "state": status,
        "chore": my_chore,
        "reason": entry.reason if entry else None,
        "due_on": week + timedelta(days=6),
    }


def _balance_hint(db: Session, my_member_id: int, members: dict[int, Member]) -> dict:
    balances_by_member = ledger.balances(db)
    my_balance = balances_by_member.get(my_member_id, 0)
    if my_balance == 0:
        return {"balance": 0, "other": None}

    position_by_member = {m.id: m.position for m in members.values()}
    proposed = ledger.transfers(balances_by_member, position_by_member)
    mine = next((t for t in proposed if my_member_id in (t[0], t[1])), None)
    other_member = None
    if mine is not None:
        from_id, to_id, _amount = mine
        other_id = to_id if from_id == my_member_id else from_id
        other_member = members.get(other_id)
    return {"balance": my_balance, "other": other_member}


@router.get("/")
def home_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    my_member_id = request.state.member_id
    members = {m.id: m for m in db.scalars(select(Member))}
    chores = rota.active_chores(db)
    current_week = week_start(berlin_today())

    context = base_context(request, db, active_nav="home")
    context.update(
        {
            "own_avatar_header": True,
            "week": current_week,
            "hero": _hero(db, current_week, my_member_id, chores, members),
            "chore_rows": rota.rows_for_week(db, chores, current_week, members, my_member_id),
            "balance_hint": _balance_hint(db, my_member_id, members),
            "shopping_open": shopping.open_items(db),
            "notes_preview": board.active_notes(db)[:2],
        }
    )
    return templates.TemplateResponse(request, "pages/home.html", context)
