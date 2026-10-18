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
from app.i18n import DEFAULT_LANGUAGE, day
from app.models import Chore, ExpenseCategory, Member, Setting
from app.services import activity, rota
from app.services import categories as categories_service
from app.services import members as members_service
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
def add_member(
    request: Request, name: str = Form(...), db: Session = Depends(get_db)
) -> RedirectResponse:
    name = name.strip()
    if name:
        position = members_service.next_position(db)
        default_language_setting = db.get(Setting, "default_language")
        member = members_service.create_member(
            db,
            name=name,
            color=position % 8,
            language=default_language_setting.value if default_language_setting else "de",
            position=position,
            joined_on=berlin_today(),
        )
        db.flush()
        _rebuild_next_week(db, request.state.member_id)
        activity.log(
            db,
            actor_member_id=request.state.member_id,
            action="create",
            entity="member",
            entity_id=member.id,
            summary_key="log.member.create",
            summary_params={"name": member.name},
        )
        db.commit()
    return RedirectResponse(f"{settings.base_path}/settings", status_code=303)


@router.post("/members/{member_id}/toggle-active", dependencies=[Depends(require_csrf)])
def toggle_member_active(
    member_id: int, request: Request, db: Session = Depends(get_db)
) -> RedirectResponse:
    member = db.get(Member, member_id)
    if member is not None:
        new_active = not member.active
        members_service.set_active(member, new_active, today=berlin_today())
        _rebuild_next_week(db, request.state.member_id)
        activity.log(
            db,
            actor_member_id=request.state.member_id,
            action="update",
            entity="member",
            entity_id=member.id,
            summary_key="log.member.reactivate" if new_active else "log.member.deactivate",
            summary_params={"name": member.name},
        )
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
        activity.log(
            db,
            actor_member_id=request.state.member_id,
            action="update",
            entity="chore",
            entity_id=chore.id,
            summary_key="log.chore.reactivate" if chore.active else "log.chore.deactivate",
            summary_params={"chore": chore.name_de},
        )
        db.commit()
    return RedirectResponse(f"{settings.base_path}/settings", status_code=303)


@router.post("/categories/new", dependencies=[Depends(require_csrf)])
def add_category(
    request: Request, name: str = Form(...), db: Session = Depends(get_db)
) -> RedirectResponse:
    name = name.strip()
    if name:
        key = members_service.slugify(name)
        category = categories_service.create_category(db, key=key, name_de=name, name_en=name)
        db.flush()
        activity.log(
            db,
            actor_member_id=request.state.member_id,
            action="create",
            entity="expense_category",
            entity_id=category.id,
            summary_key="log.category.create",
            summary_params={"name": category.name_de},
        )
        db.commit()
    return RedirectResponse(f"{settings.base_path}/settings", status_code=303)


@router.post("/categories/{category_id}/toggle-active", dependencies=[Depends(require_csrf)])
def toggle_category_active(
    category_id: int, request: Request, db: Session = Depends(get_db)
) -> RedirectResponse:
    category = db.get(ExpenseCategory, category_id)
    if category is not None:
        categories_service.set_active(category, not category.active)
        activity.log(
            db,
            actor_member_id=request.state.member_id,
            action="update",
            entity="expense_category",
            entity_id=category.id,
            summary_key="log.category.reactivate" if category.active else "log.category.deactivate",
            summary_params={"name": category.name_de},
        )
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
    activity.log(
        db,
        actor_member_id=request.state.member_id,
        action="update",
        entity="rota_config",
        summary_key="log.rota.rebuild",
        summary_params={"week": day(effective_from, DEFAULT_LANGUAGE)},
    )
    db.commit()
    return RedirectResponse(f"{settings.base_path}/settings", status_code=303)


@router.post("/rotate-link", dependencies=[Depends(require_csrf)])
def rotate_link(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    setting = db.get(Setting, "join_token")
    if setting is not None:
        setting.value = secrets.token_urlsafe(32)
        activity.log(
            db,
            actor_member_id=request.state.member_id,
            action="rotate_link",
            entity="access",
            summary_key="log.access.rotate_link",
        )
        db.commit()
    return RedirectResponse(f"{settings.base_path}/settings", status_code=303)


@router.post("/logout-all", dependencies=[Depends(require_csrf)])
def logout_all(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    setting = db.get(Setting, "cookie_version")
    if setting is not None:
        setting.value = str(int(setting.value) + 1)
        activity.log(
            db,
            actor_member_id=request.state.member_id,
            action="logout_all",
            entity="access",
            summary_key="log.access.logout_all",
        )
        db.commit()
    return RedirectResponse(f"{settings.base_path}/settings", status_code=303)


@router.get("/activity")
def activity_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    members = {m.id: m for m in db.scalars(select(Member))}
    context = base_context(request, db, active_nav=None)
    context.update({"entries": activity.recent(db), "members": members})
    return templates.TemplateResponse(request, "pages/activity.html", context)


@router.get("/trash")
def trash_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    context = base_context(request, db, active_nav=None)
    context.update({"items": activity.trash_items(db)})
    return templates.TemplateResponse(request, "pages/trash.html", context)


_RESTORE_SUMMARY_KEYS = {
    "expense": "log.expense.restore",
    "settlement": "log.settlement.restore",
    "note": "log.note.restore",
}


@router.post("/trash/{entity}/{entity_id}/restore", dependencies=[Depends(require_csrf)])
def restore_trash_item(
    entity: str, entity_id: int, request: Request, db: Session = Depends(get_db)
) -> RedirectResponse:
    row = activity.restore(db, entity=entity, entity_id=entity_id)
    if row is not None:
        summary_params = {"description": row.description} if entity == "expense" else None
        activity.log(
            db,
            actor_member_id=request.state.member_id,
            action="restore",
            entity=entity,
            entity_id=entity_id,
            summary_key=_RESTORE_SUMMARY_KEYS.get(entity, "log.restore"),
            summary_params=summary_params,
        )
        db.commit()
    return RedirectResponse(f"{settings.base_path}/settings/trash", status_code=303)
