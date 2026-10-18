from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth import require_csrf
from app.config import settings
from app.db import get_db
from app.i18n import SUPPORTED_LANGUAGES
from app.models import Member
from app.services import activity
from app.templating import base_context, templates

_LANGUAGE_LABEL_DE = {"de": "Deutsch", "en": "Englisch"}

router = APIRouter(prefix=f"{settings.base_path}/profile")


@router.get("")
def profile_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "pages/profile.html", base_context(request, db, active_nav=None)
    )


@router.post("/language", dependencies=[Depends(require_csrf)])
def set_language(
    request: Request, language: str = Form(...), db: Session = Depends(get_db)
) -> RedirectResponse:
    if language in SUPPORTED_LANGUAGES:
        member = db.get(Member, request.state.member_id)
        member.language = language
        activity.log(
            db,
            actor_member_id=member.id,
            action="update",
            entity="member",
            entity_id=member.id,
            summary_key="log.profile.language",
            summary_params={"language": _LANGUAGE_LABEL_DE.get(language, language)},
        )
        db.commit()
    return RedirectResponse(f"{settings.base_path}/profile", status_code=303)
