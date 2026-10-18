from datetime import date

from fastapi.testclient import TestClient

from app import auth
from app.models import Member, Setting


def _seed(client: TestClient) -> dict:
    with client.session_local() as db:
        db.add(Setting(key="cookie_version", value="1"))
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


def _csrf_for(client: TestClient, member_id: int) -> str:
    with client.session_local() as db:
        cookie_version = int(db.get(Setting, "cookie_version").value)
    return auth.csrf_token(cookie_version, member_id)


def test_profile_page_shows_name_and_language(client: TestClient) -> None:
    seeded = _seed(client)
    _login_as(client, seeded["jakob"])

    page = client.get("/wg/profile").text
    assert "Jakob" in page
    assert 'aria-pressed="true"' in page  # Deutsch active by default


def test_switch_link_points_to_welcome(client: TestClient) -> None:
    seeded = _seed(client)
    _login_as(client, seeded["jakob"])

    page = client.get("/wg/profile").text
    assert 'href="/wg/welcome"' in page


def test_set_language_updates_member(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    response = client.post(
        "/wg/profile/language",
        data={"csrf": token, "language": "en"},
        headers={"origin": "http://127.0.0.1:8000"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    with client.session_local() as db:
        assert db.get(Member, jakob).language == "en"

    page = client.get("/wg/profile").text
    assert "My profile" in page


def test_settings_link_present(client: TestClient) -> None:
    seeded = _seed(client)
    _login_as(client, seeded["jakob"])

    page = client.get("/wg/profile").text
    assert 'href="/wg/settings"' in page
