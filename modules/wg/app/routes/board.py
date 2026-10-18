from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_csrf
from app.config import settings
from app.db import get_db
from app.models import InfoPage, Member, Note
from app.services import activity, board
from app.templating import base_context, templates

router = APIRouter(prefix=f"{settings.base_path}/board")


@router.get("")
def board_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    context = base_context(request, db, active_nav=None)
    context.update(
        {
            "notes": board.active_notes(db),
            "info_pages": board.list_info_pages(db),
            "members": {m.id: m for m in db.scalars(select(Member))},
        }
    )
    return templates.TemplateResponse(request, "pages/board.html", context)


@router.get("/notes/new")
def new_note_form(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "pages/note_form.html", base_context(request, db, active_nav=None)
    )


@router.post("/notes/new", dependencies=[Depends(require_csrf)])
def create_note(
    request: Request,
    body: str = Form(...),
    pinned: bool = Form(False),
    expires_on: str | None = Form(None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    body = body.strip()
    if body:
        note = board.create_note(
            db,
            body=body,
            pinned=pinned,
            expires_on=date.fromisoformat(expires_on) if expires_on else None,
            created_by=request.state.member_id,
        )
        db.flush()
        activity.log(
            db,
            actor_member_id=request.state.member_id,
            action="create",
            entity="note",
            entity_id=note.id,
            summary_key="log.note.create",
        )
        db.commit()
    return RedirectResponse(f"{settings.base_path}/board", status_code=303)


@router.post("/notes/{note_id}/delete", dependencies=[Depends(require_csrf)])
def delete_note_route(
    note_id: int, request: Request, db: Session = Depends(get_db)
) -> RedirectResponse:
    note = db.get(Note, note_id)
    if note is not None:
        board.delete_note(note)
        activity.log(
            db,
            actor_member_id=request.state.member_id,
            action="delete",
            entity="note",
            entity_id=note.id,
            summary_key="log.note.delete",
        )
        db.commit()
    return RedirectResponse(f"{settings.base_path}/board", status_code=303)


@router.get("/info/{page_id}/edit")
def edit_info_form(page_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    page = db.get(InfoPage, page_id)
    context = base_context(request, db, active_nav=None)
    context["page"] = page
    return templates.TemplateResponse(request, "pages/info_form.html", context)


@router.post("/info/{page_id}/edit", dependencies=[Depends(require_csrf)])
def update_info(
    page_id: int,
    request: Request,
    title: str = Form(...),
    body: str = Form(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    page = db.get(InfoPage, page_id)
    if page is not None:
        board.update_info_page(db, page, title=title, body=body, updated_by=request.state.member_id)
        activity.log(
            db,
            actor_member_id=request.state.member_id,
            action="update",
            entity="info_page",
            entity_id=page.id,
            summary_key="log.info.update",
            summary_params={"title": page.title},
        )
        db.commit()
    return RedirectResponse(f"{settings.base_path}/board", status_code=303)
