from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_csrf
from app.config import settings
from app.db import get_db
from app.models import Chore, Member
from app.services import activity, rota
from app.templating import base_context, templates
from app.timezone import berlin_today, week_start

router = APIRouter(prefix=f"{settings.base_path}/chores")

MIN_SKIP_REASON_LENGTH = 3


def _redirect_to_week(week: date, *, error: str | None = None) -> RedirectResponse:
    url = f"{settings.base_path}/chores?week={week.isoformat()}"
    if error:
        url += f"&error={error}"
    return RedirectResponse(url, status_code=303)


def _parse_week(raw: str | None) -> date:
    if raw:
        try:
            return week_start(date.fromisoformat(raw))
        except ValueError:
            pass
    return week_start(berlin_today())


@router.get("")
def chores_page(
    request: Request,
    week: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    current_week = _parse_week(week)
    chores = rota.active_chores(db)
    members = {m.id: m for m in db.scalars(select(Member))}
    my_member_id = request.state.member_id

    upcoming = [
        {
            "week": current_week + timedelta(weeks=offset),
            "rows": rota.rows_in_chore_order(
                db, chores, current_week + timedelta(weeks=offset), members, my_member_id
            ),
        }
        for offset in (1, 2, 3)
    ]

    context = base_context(request, db, active_nav="chores")
    context.update(
        {
            "week": current_week,
            "today": berlin_today(),
            "prev_week": current_week - timedelta(weeks=1),
            "next_week": current_week + timedelta(weeks=1),
            "is_current_week": current_week == week_start(berlin_today()),
            "chores": chores,
            "rows": rota.rows_for_week(db, chores, current_week, members, my_member_id),
            "upcoming": upcoming,
            "error": error,
        }
    )
    return templates.TemplateResponse(request, "pages/chores.html", context)


@router.post("/{week}/{chore_id}/done", dependencies=[Depends(require_csrf)])
def chore_done(
    week: date, chore_id: int, request: Request, db: Session = Depends(get_db)
) -> RedirectResponse:
    assigned_id = rota.assignment(db, week).get(chore_id)
    rota.mark_done(
        db,
        week=week,
        chore_id=chore_id,
        assigned_member_id=assigned_id,
        done_by=request.state.member_id,
    )
    chore = db.get(Chore, chore_id)
    activity.log(
        db,
        actor_member_id=request.state.member_id,
        action="done",
        entity="chore",
        entity_id=chore_id,
        summary_key="log.chore.done",
        summary_params={"chore": chore.name_de if chore else ""},
    )
    db.commit()
    return _redirect_to_week(week)


@router.post("/{week}/{chore_id}/skip", dependencies=[Depends(require_csrf)])
def chore_skip(
    week: date,
    chore_id: int,
    request: Request,
    reason: str = Form(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    reason = reason.strip()
    if len(reason) < MIN_SKIP_REASON_LENGTH:
        return _redirect_to_week(week, error="reason_required")

    assigned_id = rota.assignment(db, week).get(chore_id)
    rota.mark_skipped(
        db,
        week=week,
        chore_id=chore_id,
        assigned_member_id=assigned_id,
        done_by=request.state.member_id,
        reason=reason,
    )
    chore = db.get(Chore, chore_id)
    activity.log(
        db,
        actor_member_id=request.state.member_id,
        action="skip",
        entity="chore",
        entity_id=chore_id,
        summary_key="log.chore.skip",
        summary_params={"chore": chore.name_de if chore else "", "reason": reason},
    )
    db.commit()
    return _redirect_to_week(week)


@router.post("/{week}/{chore_id}/undo", dependencies=[Depends(require_csrf)])
def chore_undo(
    week: date, chore_id: int, request: Request, db: Session = Depends(get_db)
) -> RedirectResponse:
    # spec.md §3.2: undo only works for the current and the previous week.
    current = week_start(berlin_today())
    if week not in (current, current - timedelta(weeks=1)):
        return _redirect_to_week(week, error="undo_not_allowed")

    if rota.undo(db, week=week, chore_id=chore_id):
        chore = db.get(Chore, chore_id)
        activity.log(
            db,
            actor_member_id=request.state.member_id,
            action="undo",
            entity="chore",
            entity_id=chore_id,
            summary_key="log.chore.undo",
            summary_params={"chore": chore.name_de if chore else ""},
        )
    db.commit()
    return _redirect_to_week(week)
