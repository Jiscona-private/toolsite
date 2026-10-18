from __future__ import annotations

import secrets
from datetime import timedelta

import segno
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_csrf
from app.config import settings
from app.db import get_db
from app.models import Chore, ExpenseCategory, Member, Setting
from app.services import categories as categories_service
from app.services import members as members_service
from app.services import rota
from app.templating import base_context, templates
from app.timezone import berlin_today, week_start

router = APIRouter(prefix=f"{settings.base_path}/settings")


def _rebuild_next_week(db: Session, created_by: int) -> None:
    next_week = week_start(berlin_today()) + timedelta(weeks=1)
    rota.rebuild_for_current_membership(db, effective_from=next_week, created_by=created_by)


@router.get("")
def settings_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    current_week = week_start(berlin_today())
    chores = rota.active_chores(db)
    members = {m.id: m for m in db.scalars(select(Member))}
    preview = [
        {
            "week": current_week + timedelta(weeks=offset),
            "rows": rota.rows_in_chore_order(
                db, chores, current_week + timedelta(weeks=offset), members, request.state.member_id
            ),
        }
        for offset in (0, 1, 2, 3)
    ]

    join_token_setting = db.get(Setting, "join_token")
    join_link = (
        f"{settings.app_base_url}/join/{join_token_setting.value}" if join_token_setting else ""
    )

    context = base_context(request, db, active_nav=None)
    context.update(
        {
            "all_members": list(members.values()),
            "all_chores": list(db.scalars(select(Chore).order_by(Chore.position))),
            "all_categories": list(
                db.scalars(select(ExpenseCategory).order_by(ExpenseCategory.position))
            ),
            "chores": chores,
            "preview": preview,
            "join_link": join_link,
            "qr_data_uri": segno.make(join_link).svg_data_uri(scale=4) if join_link else "",
        }
    )
    return templates.TemplateResponse(request, "pages/settings.html", context)


@router.post("/members/new", dependencies=[Depends(require_csrf)])
def add_member(name: str = Form(...), db: Session = Depends(get_db)) -> RedirectResponse:
    name = name.strip()
    if name:
        position = members_service.next_position(db)
        default_language_setting = db.get(Setting, "default_language")
        members_service.create_member(
            db,
            name=name,
            color=position % 8,
            language=default_language_setting.value if default_language_setting else "de",
            position=position,
            joined_on=berlin_today(),
        )
        db.flush()
        _rebuild_next_week(db, None)
        db.commit()
    return RedirectResponse(f"{settings.base_path}/settings", status_code=303)


@router.post("/members/{member_id}/toggle-active", dependencies=[Depends(require_csrf)])
def toggle_member_active(
    member_id: int, request: Request, db: Session = Depends(get_db)
) -> RedirectResponse:
    member = db.get(Member, member_id)
    if member is not None:
        members_service.set_active(member, not member.active, today=berlin_today())
        _rebuild_next_week(db, request.state.member_id)
        db.commit()
    return RedirectResponse(f"{settings.base_path}/settings", status_code=303)


@router.post("/chores/{chore_id}/toggle-active", dependencies=[Depends(require_csrf)])
def toggle_chore_active(
    chore_id: int, request: Request, db: Session = Depends(get_db)
) -> RedirectResponse:
    chore = db.get(Chore, chore_id)
    if chore is not None:
        chore.active = not chore.active
        _rebuild_next_week(db, request.state.member_id)
        db.commit()
    return RedirectResponse(f"{settings.base_path}/settings", status_code=303)


@router.post("/categories/new", dependencies=[Depends(require_csrf)])
def add_category(name: str = Form(...), db: Session = Depends(get_db)) -> RedirectResponse:
    name = name.strip()
    if name:
        key = members_service.slugify(name)
        categories_service.create_category(db, key=key, name_de=name, name_en=name)
        db.commit()
    return RedirectResponse(f"{settings.base_path}/settings", status_code=303)


@router.post("/categories/{category_id}/toggle-active", dependencies=[Depends(require_csrf)])
def toggle_category_active(category_id: int, db: Session = Depends(get_db)) -> RedirectResponse:
    category = db.get(ExpenseCategory, category_id)
    if category is not None:
        categories_service.set_active(category, not category.active)
        db.commit()
    return RedirectResponse(f"{settings.base_path}/settings", status_code=303)


@router.post("/rota/rebuild", dependencies=[Depends(require_csrf)])
def rebuild_rota_route(
    request: Request, when: str = Form("next"), db: Session = Depends(get_db)
) -> RedirectResponse:
    effective_from = week_start(berlin_today())
    if when == "next":
        effective_from += timedelta(weeks=1)
    rota.rebuild_for_current_membership(
        db, effective_from=effective_from, created_by=request.state.member_id
    )
    db.commit()
    return RedirectResponse(f"{settings.base_path}/settings", status_code=303)


@router.post("/rotate-link", dependencies=[Depends(require_csrf)])
def rotate_link(db: Session = Depends(get_db)) -> RedirectResponse:
    setting = db.get(Setting, "join_token")
    if setting is not None:
        setting.value = secrets.token_urlsafe(32)
        db.commit()
    return RedirectResponse(f"{settings.base_path}/settings", status_code=303)


@router.post("/logout-all", dependencies=[Depends(require_csrf)])
def logout_all(db: Session = Depends(get_db)) -> RedirectResponse:
    setting = db.get(Setting, "cookie_version")
    if setting is not None:
        setting.value = str(int(setting.value) + 1)
        db.commit()
    return RedirectResponse(f"{settings.base_path}/settings", status_code=303)
