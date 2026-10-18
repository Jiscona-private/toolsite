import json
from datetime import date

from fastapi.testclient import TestClient

from app import auth
from app.models import Member, Setting


def _seed(client: TestClient) -> dict:
    with client.session_local() as db:
        db.add(Setting(key="cookie_version", value="1"))
        db.add(Setting(key="wg_name", value="WG Testweg"))
        member = Member(
            name="Jakob",
            language="de",
            color=0,
            position=0,
            active=True,
            joined_on=date(2026, 10, 19),
            ntfy_topic="wg-aaaaaaaa-jakob",
            notify_prefs={},
        )
        db.add(member)
        db.commit()
        return {"jakob": member.id}


def _login_as(client: TestClient, member_id: int) -> None:
    client.cookies.set(auth.COOKIE_AUTH, auth.sign_auth_cookie(cookie_version=1))
    client.cookies.set(auth.COOKIE_MEMBER, auth.sign_member_cookie(member_id, cookie_version=1))


def test_manifest_uses_wg_name_and_scopes_to_base_path(client: TestClient) -> None:
    _seed(client)
    _login_as(client, 1)

    response = client.get("/wg/manifest.webmanifest")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/manifest+json")

    data = json.loads(response.text)
    assert data["name"] == "WG Testweg"
    assert data["start_url"] == "/wg/"
    assert data["scope"] == "/wg/"
    assert data["display"] == "standalone"
    assert {icon["sizes"] for icon in data["icons"]} == {"192x192", "512x512"}


def test_service_worker_is_scoped_to_base_path_and_never_cached(client: TestClient) -> None:
    _seed(client)
    _login_as(client, 1)

    response = client.get("/wg/sw.js")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/javascript")
    assert response.headers["cache-control"] == "no-store"  # never cached, see app/auth.py
    assert '"/wg/offline"' in response.text
    assert 'request.method !== "GET"' in response.text


def test_offline_page_renders(client: TestClient) -> None:
    _seed(client)
    _login_as(client, 1)

    response = client.get("/wg/offline")
    assert response.status_code == 200
    assert "Keine Verbindung" in response.text


def test_pwa_routes_are_gated_without_a_cookie(client: TestClient) -> None:
    _seed(client)

    assert client.get("/wg/manifest.webmanifest").status_code == 404
    assert client.get("/wg/sw.js").status_code == 404
    assert client.get("/wg/offline").status_code == 404
