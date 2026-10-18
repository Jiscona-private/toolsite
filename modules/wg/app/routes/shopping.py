from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_csrf
from app.config import settings
from app.db import get_db
from app.models import Member, ShoppingItem
from app.services import activity, shopping
from app.templating import base_context, templates


def _members_by_id(db: Session) -> dict[int, Member]:
    return {m.id: m for m in db.scalars(select(Member))}


router = APIRouter(prefix=f"{settings.base_path}/shopping")


@router.get("")
def shopping_page(
    request: Request,
    focus: int | None = None,
    duplicate: str | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    items = shopping.open_items(db)
    context = base_context(request, db, active_nav="shopping")
    context.update(
        {
            "open_items": [i for i in items if i.checked_at is None],
            "checked_items": [i for i in items if i.checked_at is not None],
            "focus": bool(focus),
            "duplicate_name": duplicate,
            "members": _members_by_id(db),
        }
    )
    return templates.TemplateResponse(request, "pages/shopping.html", context)


@router.post("", dependencies=[Depends(require_csrf)])
def add_shopping_item(
    request: Request,
    name: str = Form(...),
    quantity: str | None = Form(None),
    note: str | None = Form(None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    name = name.strip()
    if not name:
        return RedirectResponse(f"{settings.base_path}/shopping", status_code=303)

    if shopping.find_open_duplicate(db, name) is not None:
        return RedirectResponse(
            f"{settings.base_path}/shopping?duplicate={quote(name)}", status_code=303
        )

    item = shopping.add_item(
        db, name=name, quantity=quantity, note=note, added_by=request.state.member_id
    )
    db.flush()
    activity.log(
        db,
        actor_member_id=request.state.member_id,
        action="create",
        entity="shopping_item",
        entity_id=item.id,
        summary_key="log.shopping.create",
        summary_params={"name": item.name},
    )
    db.commit()
    return RedirectResponse(f"{settings.base_path}/shopping", status_code=303)


@router.post("/{item_id}/toggle", dependencies=[Depends(require_csrf)])
def toggle_item(item_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    item = db.get(ShoppingItem, item_id)
    if item is not None:
        now_checked = item.checked_at is None
        shopping.toggle_checked(item, request.state.member_id)
        activity.log(
            db,
            actor_member_id=request.state.member_id,
            action="check" if now_checked else "uncheck",
            entity="shopping_item",
            entity_id=item.id,
            summary_key="log.shopping.check" if now_checked else "log.shopping.uncheck",
            summary_params={"name": item.name},
        )
        db.commit()

    if request.headers.get("hx-request") == "true":
        context = base_context(request, db)
        context["item"] = item
        context["members"] = _members_by_id(db)
        return templates.TemplateResponse(request, "partials/shopping_item.html", context)
    return RedirectResponse(f"{settings.base_path}/shopping", status_code=303)


@router.post("/clear-checked", dependencies=[Depends(require_csrf)])
def clear_checked(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    count = shopping.archive_checked(db)
    if count:
        activity.log(
            db,
            actor_member_id=request.state.member_id,
            action="update",
            entity="shopping_item",
            summary_key="log.shopping.clear_checked",
            summary_params={"count": count},
        )
    db.commit()
    return RedirectResponse(f"{settings.base_path}/shopping", status_code=303)
