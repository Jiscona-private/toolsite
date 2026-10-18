from datetime import date

import pytest
from sqlalchemy.orm import sessionmaker
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app import auth
from app.config import settings
from app.models import Member, Setting

# Business routes (chores, expenses, ...) don't exist yet in this step, so
# the gate is exercised against a throwaway mini app with one dummy
# protected route instead of a real one. See docs/roadmap.md step 4.


async def _protected(request: Request) -> PlainTextResponse:
    return PlainTextResponse(f"ok:{request.state.member_id}")


def _build_mini_app() -> Starlette:
    return Starlette(
        routes=[
            Route(f"{settings.base_path}/protected", _protected, methods=["GET", "POST"]),
        ],
        middleware=[Middleware(BaseHTTPMiddleware, dispatch=auth.access_gate)],
    )


@pytest.fixture
def gate_client(monkeypatch: pytest.MonkeyPatch, session_local: sessionmaker) -> TestClient:
    monkeypatch.setattr(auth, "SessionLocal", session_local)
    with session_local() as db:
        db.add(Setting(key="cookie_version", value="1"))
        db.add(
            Member(
                name="Jakob",
                language="de",
                color=0,
                position=0,
                active=True,
                joined_on=date(2026, 10, 19),
                ntfy_topic="wg-aaaaaaaa-jakob",
                notify_prefs={},
            )
        )
        db.add(
            Member(
                name="Inactive",
                language="de",
                color=1,
                position=1,
                active=False,
                joined_on=date(2026, 10, 19),
                ntfy_topic="wg-bbbbbbbb-inactive",
                notify_prefs={},
            )
        )
        db.commit()
    return TestClient(_build_mini_app())


def test_missing_auth_cookie_returns_404(gate_client: TestClient) -> None:
    response = gate_client.get(f"{settings.base_path}/protected")
    assert response.status_code == 404
    assert response.text == "Not Found"


def test_wrong_cookie_version_returns_404(gate_client: TestClient) -> None:
    gate_client.cookies.set(auth.COOKIE_AUTH, auth.sign_auth_cookie(cookie_version=99))
    response = gate_client.get(f"{settings.base_path}/protected")
    assert response.status_code == 404


def test_tampered_auth_cookie_returns_404(gate_client: TestClient) -> None:
    gate_client.cookies.set(auth.COOKIE_AUTH, "garbage")
    response = gate_client.get(f"{settings.base_path}/protected")
    assert response.status_code == 404


def test_valid_auth_without_member_redirects_to_welcome(gate_client: TestClient) -> None:
    gate_client.cookies.set(auth.COOKIE_AUTH, auth.sign_auth_cookie(cookie_version=1))
    response = gate_client.get(f"{settings.base_path}/protected", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"{settings.base_path}/welcome"


def test_inactive_member_redirects_to_welcome(gate_client: TestClient, session_local) -> None:
    with session_local() as db:
        inactive = db.query(Member).filter_by(name="Inactive").one()
        member_id = inactive.id

    gate_client.cookies.set(auth.COOKIE_AUTH, auth.sign_auth_cookie(cookie_version=1))
    gate_client.cookies.set(
        auth.COOKIE_MEMBER, auth.sign_member_cookie(member_id, cookie_version=1)
    )
    response = gate_client.get(f"{settings.base_path}/protected", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"{settings.base_path}/welcome"


def test_valid_member_can_get_protected_route(gate_client: TestClient, session_local) -> None:
    with session_local() as db:
        member_id = db.query(Member).filter_by(name="Jakob").one().id

    gate_client.cookies.set(auth.COOKIE_AUTH, auth.sign_auth_cookie(cookie_version=1))
    gate_client.cookies.set(
        auth.COOKIE_MEMBER, auth.sign_member_cookie(member_id, cookie_version=1)
    )
    response = gate_client.get(f"{settings.base_path}/protected")
    assert response.status_code == 200
    assert response.text == f"ok:{member_id}"


def test_post_without_csrf_token_is_forbidden(gate_client: TestClient, session_local) -> None:
    with session_local() as db:
        member_id = db.query(Member).filter_by(name="Jakob").one().id

    gate_client.cookies.set(auth.COOKIE_AUTH, auth.sign_auth_cookie(cookie_version=1))
    gate_client.cookies.set(
        auth.COOKIE_MEMBER, auth.sign_member_cookie(member_id, cookie_version=1)
    )
    response = gate_client.post(
        f"{settings.base_path}/protected",
        headers={"origin": settings.app_base_url},
    )
    assert response.status_code == 403


def test_post_with_untrusted_origin_is_forbidden(gate_client: TestClient, session_local) -> None:
    with session_local() as db:
        member_id = db.query(Member).filter_by(name="Jakob").one().id

    gate_client.cookies.set(auth.COOKIE_AUTH, auth.sign_auth_cookie(cookie_version=1))
    gate_client.cookies.set(
        auth.COOKIE_MEMBER, auth.sign_member_cookie(member_id, cookie_version=1)
    )
    token = auth.csrf_token(cookie_version=1, member_id=member_id)
    response = gate_client.post(
        f"{settings.base_path}/protected",
        headers={"origin": "https://evil.example", "x-csrf-token": token},
    )
    assert response.status_code == 403


def test_post_with_valid_origin_and_csrf_token_succeeds(
    gate_client: TestClient, session_local
) -> None:
    with session_local() as db:
        member_id = db.query(Member).filter_by(name="Jakob").one().id

    gate_client.cookies.set(auth.COOKIE_AUTH, auth.sign_auth_cookie(cookie_version=1))
    gate_client.cookies.set(
        auth.COOKIE_MEMBER, auth.sign_member_cookie(member_id, cookie_version=1)
    )
    token = auth.csrf_token(cookie_version=1, member_id=member_id)
    response = gate_client.post(
        f"{settings.base_path}/protected",
        headers={"origin": settings.app_base_url, "x-csrf-token": token},
    )
    assert response.status_code == 200


def test_security_headers_are_set(gate_client: TestClient) -> None:
    response = gate_client.get(f"{settings.base_path}/protected")
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
