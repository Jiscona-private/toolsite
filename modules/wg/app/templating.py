from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.i18n import DEFAULT_LANGUAGE, t
from app.models import Member, Setting

# A standalone module (rather than living in main.py) so both main.py and
# app/auth.py can import it without a circular import between them.
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def base_context(request: Request, db: Session, *, active_nav: str | None = None) -> dict:
    """The variables every template extending base.html needs. The
    access_gate middleware (app/auth.py) sets request.state.member_id once
    a member is chosen; pages before that point (e.g. /welcome) never call
    this, since they don't extend base.html's nav/avatar."""
    member = None
    member_id = getattr(request.state, "member_id", None)
    if member_id is not None:
        member = db.get(Member, member_id)

    language = member.language if member else DEFAULT_LANGUAGE
    wg_name_setting = db.get(Setting, "wg_name")
    wg_name = wg_name_setting.value if wg_name_setting else "WG-App"

    return {
        "t": lambda key, **params: t(key, language=language, **params),
        "lang": language,
        "base_path": settings.base_path,
        "wg_name": wg_name,
        "member": member,
        "active_nav": active_nav,
    }
