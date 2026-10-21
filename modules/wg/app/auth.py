from __future__ import annotations

import hmac
import threading
import time
from datetime import UTC, datetime
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from itsdangerous import BadData, URLSafeSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import PlainTextResponse, RedirectResponse, Response

from app.config import settings
from app.csrf import csrf_token, csrf_token_matches
from app.db import SessionLocal, get_db
from app.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, t
from app.models import ActivityLog, Member, Setting
from app.templating import templates

__all__ = [  # re-exported for callers that used to import these from here
    "csrf_token",
    "csrf_token_matches",
]

COOKIE_AUTH = "wg_auth"
COOKIE_MEMBER = "wg_member"
COOKIE_LANG = "wg_lang"
COOKIE_MAX_AGE = 400 * 24 * 60 * 60  # 400 days, spec.md §6.1

NOT_FOUND = PlainTextResponse("Not Found", status_code=404)

RATE_LIMIT_WINDOW_SECONDS = 15 * 60
RATE_LIMIT_MAX_FAILURES = 10

_rate_limit_lock = threading.Lock()
_join_failures: dict[str, list[float]] = {}

router = APIRouter(prefix=settings.base_path)


# --- cookie signing -----------------------------------------------------
# Salted per cookie (spec.md §6.1), not timestamped: expiry is the cookie's
# own Max-Age: server-side revocation goes through settings.cookie_version.


def _serializer(salt: str) -> URLSafeSerializer:
    return URLSafeSerializer(settings.secret_key, salt=salt)


def sign_auth_cookie(cookie_version: int) -> str:
    return _serializer(COOKIE_AUTH).dumps({"v": cookie_version})


def read_auth_cookie(value: str) -> dict | None:
    try:
        return _serializer(COOKIE_AUTH).loads(value)
    except BadData:
        return None


def sign_member_cookie(member_id: int, cookie_version: int) -> str:
    return _serializer(COOKIE_MEMBER).dumps({"m": member_id, "v": cookie_version})


def read_member_cookie(value: str) -> dict | None:
    try:
        return _serializer(COOKIE_MEMBER).loads(value)
    except BadData:
        return None


def set_signed_cookie(response: Response, name: str, value: str) -> None:
    response.set_cookie(
        name,
        value,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.app_env != "dev",
        samesite="lax",
        # CLAUDE.md overrides spec.md's generic Path=/: this module's own
        # cookies are scoped to its own prefix, like everything else here.
        path=settings.base_path,
    )


# --- join rate limiting --------------------------------------------------


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def is_join_rate_limited(ip: str) -> bool:
    cutoff = time.time() - RATE_LIMIT_WINDOW_SECONDS
    with _rate_limit_lock:
        attempts = [moment for moment in _join_failures.get(ip, []) if moment >= cutoff]
        _join_failures[ip] = attempts
        return len(attempts) >= RATE_LIMIT_MAX_FAILURES


def record_join_failure(ip: str) -> None:
    with _rate_limit_lock:
        _join_failures.setdefault(ip, []).append(time.time())


def _origin_of(url: str) -> str:
    """scheme://host[:port], with no path - what an Origin header actually
    looks like (it never carries one), unlike settings.app_base_url."""
    split = urlsplit(url)
    return f"{split.scheme}://{split.netloc}"


def origin_is_trusted(request: Request) -> bool:
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin:
        return False
    return _origin_of(origin) == _origin_of(settings.app_base_url)


# --- the 404 gate (plus CSRF + security headers) -------------------------
# One middleware for all three concerns, per CLAUDE.md's planned app/auth.py.


def _is_exempt(path: str) -> bool:
    base = settings.base_path
    if path == f"{base}/healthz":
        return True
    if path.startswith(f"{base}/join/"):
        return True
    return bool(path.startswith(f"{base}/cal/") and path.endswith(".ics"))


def _security_headers(response: Response) -> Response:
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; font-src 'self'; manifest-src 'self'; worker-src 'self'; "
        "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    if response.media_type in (None, "text/html"):
        response.headers["Cache-Control"] = "no-store"
    return response


async def access_gate(request: Request, call_next):
    path = request.url.path

    if _is_exempt(path):
        return _security_headers(await call_next(request))

    with SessionLocal() as db:
        cookie_version_setting = db.get(Setting, "cookie_version")
        cookie_version = int(cookie_version_setting.value) if cookie_version_setting else -1

        auth_raw = request.cookies.get(COOKIE_AUTH)
        auth_payload = read_auth_cookie(auth_raw) if auth_raw else None
        if auth_payload is None or auth_payload.get("v") != cookie_version:
            return _security_headers(NOT_FOUND)

        # /welcome itself, and the static assets it needs (app.css, the
        # fonts it @font-face's) - someone on /welcome has the join-link
        # auth cookie but, by definition, no member cookie yet. Without
        # this, every asset request from that page fell through to the
        # "no member -> redirect to /welcome" branch below: the browser
        # got an HTML redirect back instead of CSS and silently dropped
        # it, so the page rendered as unstyled HTML. Static files carry
        # no personal data, so gating them on just the auth cookie (same
        # tier as /welcome, not full member login) is correct, not a
        # shortcut.
        if path == f"{settings.base_path}/welcome" or path.startswith(
            f"{settings.base_path}/static/"
        ):
            return _security_headers(await call_next(request))

        member = None
        member_raw = request.cookies.get(COOKIE_MEMBER)
        member_payload = read_member_cookie(member_raw) if member_raw else None
        if member_payload is not None and member_payload.get("v") == cookie_version:
            candidate = db.get(Member, member_payload["m"])
            if candidate is not None and candidate.active:
                member = candidate

        if member is None:
            return _security_headers(
                RedirectResponse(f"{settings.base_path}/welcome", status_code=303)
            )

        # CSRF itself is *not* checked here: reading the body (for the
        # no-JS hidden-field fallback) via request.form() in a
        # BaseHTTPMiddleware drains the one-shot ASGI receive channel, and
        # the real route then gets an empty body ("field required") when it
        # parses its own Form(...) params - a classic Starlette gotcha. See
        # require_csrf below, which every mutating route depends on instead,
        # where FastAPI's own (single) body parse makes this safe.
        request.state.member_id = member.id
        request.state.cookie_version = cookie_version

    return _security_headers(await call_next(request))


def require_csrf(request: Request, csrf: str | None = Form(None)) -> None:
    """Depends() on every POST/PUT/PATCH/DELETE route. Checks the
    X-CSRF-Token header (htmx, via hx-headers on <body>) or the hidden
    "csrf" form field (the no-JS fallback, rule 11) - spec.md §6.2."""
    if not origin_is_trusted(request):
        raise HTTPException(status_code=403, detail="Forbidden")
    token = request.headers.get("x-csrf-token") or csrf
    if not csrf_token_matches(token, request.state.cookie_version, request.state.member_id):
        raise HTTPException(status_code=403, detail="Forbidden")


# --- routes ---------------------------------------------------------


def _pick_language(request: Request, query_lang: str | None) -> str:
    if query_lang in SUPPORTED_LANGUAGES:
        return query_lang
    cookie_lang = request.cookies.get(COOKIE_LANG)
    if cookie_lang in SUPPORTED_LANGUAGES:
        return cookie_lang
    return DEFAULT_LANGUAGE


@router.get("/join/{token}")
def join(token: str, request: Request, db: Session = Depends(get_db)) -> Response:
    ip = client_ip(request)
    if is_join_rate_limited(ip):
        return NOT_FOUND

    join_token_setting = db.get(Setting, "join_token")
    if join_token_setting is None or not hmac.compare_digest(token, join_token_setting.value):
        record_join_failure(ip)
        return NOT_FOUND

    cookie_version = int(db.get(Setting, "cookie_version").value)
    db.add(
        ActivityLog(
            at=datetime.now(UTC),
            actor_member_id=None,
            action="join",
            entity="access",
            entity_id=None,
            summary_key="log.access.join",
            summary_params={},
        )
    )
    db.commit()

    member_raw = request.cookies.get(COOKIE_MEMBER)
    member_payload = read_member_cookie(member_raw) if member_raw else None
    target = "/" if member_payload and member_payload.get("v") == cookie_version else "/welcome"

    response = RedirectResponse(f"{settings.base_path}{target}", status_code=303)
    set_signed_cookie(response, COOKIE_AUTH, sign_auth_cookie(cookie_version))
    return response


def _render_welcome(
    request: Request, db: Session, language: str, *, error: bool = False, status_code: int = 200
) -> Response:
    members = db.scalars(
        select(Member).where(Member.active.is_(True)).order_by(Member.position)
    ).all()
    return templates.TemplateResponse(
        request,
        "pages/welcome.html",
        {
            "t": lambda key, **params: t(key, language=language, **params),
            "lang": language,
            "base_path": settings.base_path,
            "members": members,
            "error": error,
        },
        status_code=status_code,
    )


@router.get("/welcome")
def welcome_form(request: Request, lang: str | None = None, db: Session = Depends(get_db)):
    language = _pick_language(request, lang)
    response = _render_welcome(request, db, language)
    if lang in SUPPORTED_LANGUAGES:
        response.set_cookie(
            COOKIE_LANG,
            language,
            max_age=COOKIE_MAX_AGE,
            httponly=False,
            secure=settings.app_env != "dev",
            samesite="lax",
            path=settings.base_path,
        )
    return response


@router.post("/welcome")
def welcome_choose(
    request: Request,
    member_id: int = Form(...),
    lang: str = Form(DEFAULT_LANGUAGE),
    db: Session = Depends(get_db),
) -> Response:
    member = db.get(Member, member_id)
    if member is None or not member.active:
        language = _pick_language(request, lang)
        return _render_welcome(request, db, language, error=True, status_code=400)

    cookie_version_setting = db.get(Setting, "cookie_version")
    cookie_version = int(cookie_version_setting.value) if cookie_version_setting else 0

    response = RedirectResponse(f"{settings.base_path}/", status_code=303)
    set_signed_cookie(response, COOKIE_MEMBER, sign_member_cookie(member.id, cookie_version))
    return response
