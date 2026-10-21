from datetime import date

from fastapi.testclient import TestClient

from app import auth
from app.models import ActivityLog, Member, Setting


def _seed_settings(client: TestClient, *, join_token: str = "correct-token") -> None:
    with client.session_local() as db:
        db.add(Setting(key="join_token", value=join_token))
        db.add(Setting(key="cookie_version", value="1"))
        db.commit()


def _seed_member(client: TestClient, *, name: str = "Jakob", active: bool = True) -> int:
    with client.session_local() as db:
        member = Member(
            name=name,
            language="de",
            color=0,
            position=0,
            active=active,
            joined_on=date(2026, 10, 19),
            ntfy_topic=f"wg-aaaaaaaa-{name.lower()}",
            notify_prefs={},
        )
        db.add(member)
        db.commit()
        return member.id


def test_join_with_wrong_token_returns_404(client: TestClient) -> None:
    _seed_settings(client)
    response = client.get("/wg/join/wrong-token")
    assert response.status_code == 404
    assert response.text == "Not Found"
    assert "set-cookie" not in {k.lower() for k in response.headers}


def test_join_with_correct_token_sets_auth_cookie_and_redirects_to_welcome(
    client: TestClient,
) -> None:
    _seed_settings(client)
    response = client.get("/wg/join/correct-token", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/wg/welcome"
    set_cookie = response.headers["set-cookie"]
    assert auth.COOKIE_AUTH in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Path=/wg" in set_cookie

    with client.session_local() as db:
        assert db.query(ActivityLog).filter_by(action="join").count() == 1


def test_join_is_rate_limited_after_ten_failures(client: TestClient) -> None:
    auth._join_failures.clear()
    _seed_settings(client)
    for _ in range(10):
        assert client.get("/wg/join/wrong-token").status_code == 404

    # 11th attempt, even with the *correct* token, is still 404 (spec.md §10.3).
    response = client.get("/wg/join/correct-token", follow_redirects=False)
    assert response.status_code == 404
    assert "set-cookie" not in {k.lower() for k in response.headers}


def test_protected_page_without_auth_cookie_returns_404(client: TestClient) -> None:
    _seed_settings(client)
    response = client.get("/wg/welcome")
    assert response.status_code == 404


def test_welcome_lists_active_members_only(client: TestClient) -> None:
    _seed_settings(client)
    _seed_member(client, name="Jakob", active=True)
    _seed_member(client, name="Ausgezogen", active=False)
    client.cookies.set(auth.COOKIE_AUTH, auth.sign_auth_cookie(cookie_version=1))

    response = client.get("/wg/welcome")
    assert response.status_code == 200
    assert "Jakob" in response.text
    assert "Ausgezogen" not in response.text


def test_welcome_page_is_branded_with_an_icon_avatars_and_a_members_only_notice(
    client: TestClient,
) -> None:
    _seed_settings(client)
    _seed_member(client, name="Jakob", active=True)
    client.cookies.set(auth.COOKIE_AUTH, auth.sign_auth_cookie(cookie_version=1))

    page = client.get("/wg/welcome").text
    assert "icon-app" in page  # branded app icon, not a bare heading
    assert 'class="avatar color-0"' in page  # member choices show an avatar, not a plain name
    assert "Nur Mitglieder dieser WG" in page  # join-only notice, per CLAUDE.md §7.3


def test_welcome_post_sets_member_cookie_and_redirects_home(client: TestClient) -> None:
    _seed_settings(client)
    member_id = _seed_member(client)
    client.cookies.set(auth.COOKIE_AUTH, auth.sign_auth_cookie(cookie_version=1))

    response = client.post(
        "/wg/welcome",
        data={"member_id": member_id, "lang": "de"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/wg/"
    assert auth.COOKIE_MEMBER in response.headers["set-cookie"]


def test_welcome_post_with_inactive_member_shows_error(client: TestClient) -> None:
    _seed_settings(client)
    member_id = _seed_member(client, active=False)
    client.cookies.set(auth.COOKIE_AUTH, auth.sign_auth_cookie(cookie_version=1))

    response = client.post("/wg/welcome", data={"member_id": member_id, "lang": "de"})
    assert response.status_code == 400


def test_logout_all_invalidates_existing_auth_cookie(client: TestClient) -> None:
    _seed_settings(client)
    auth_cookie = auth.sign_auth_cookie(cookie_version=1)
    client.cookies.set(auth.COOKIE_AUTH, auth_cookie)
    assert client.get("/wg/welcome").status_code == 200

    with client.session_local() as db:
        setting = db.get(Setting, "cookie_version")
        setting.value = "2"
        db.commit()

    assert client.get("/wg/welcome").status_code == 404
