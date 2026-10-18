from datetime import date

from fastapi.testclient import TestClient

from app import auth
from app.models import InfoPage, Member, Setting


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
        db.add(InfoPage(title="WLAN", body="Netz: x", position=0))
        db.commit()
        return {"jakob": member.id}


def _login_as(client: TestClient, member_id: int) -> None:
    client.cookies.set(auth.COOKIE_AUTH, auth.sign_auth_cookie(cookie_version=1))
    client.cookies.set(auth.COOKIE_MEMBER, auth.sign_member_cookie(member_id, cookie_version=1))


def _csrf_for(client: TestClient, member_id: int) -> str:
    with client.session_local() as db:
        cookie_version = int(db.get(Setting, "cookie_version").value)
    return auth.csrf_token(cookie_version, member_id)


def test_board_page_lists_info_pages(client: TestClient) -> None:
    seeded = _seed(client)
    _login_as(client, seeded["jakob"])

    page = client.get("/wg/board").text
    assert "WLAN" in page
    assert "Noch keine Notizen." in page


def test_create_note_appears_pinned_first(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    client.post(
        "/wg/board/notes/new",
        data={"csrf": token, "body": "Unpinned note"},
        headers={"origin": "http://127.0.0.1:8000"},
    )
    response = client.post(
        "/wg/board/notes/new",
        data={"csrf": token, "body": "Pinned note", "pinned": "true"},
        headers={"origin": "http://127.0.0.1:8000"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    page = client.get("/wg/board").text
    assert page.index("Pinned note") < page.index("Unpinned note")


def test_create_note_without_csrf_is_forbidden(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["jakob"]
    _login_as(client, jakob)

    response = client.post(
        "/wg/board/notes/new",
        data={"body": "x"},
        headers={"origin": "http://127.0.0.1:8000"},
    )
    assert response.status_code == 403


def test_delete_note_removes_it(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)
    client.post(
        "/wg/board/notes/new",
        data={"csrf": token, "body": "Temporary"},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    response = client.post(
        "/wg/board/notes/1/delete",
        data={"csrf": token},
        headers={"origin": "http://127.0.0.1:8000"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    page = client.get("/wg/board").text
    assert "Temporary" not in page


def test_edit_info_page_updates_title_and_body(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    response = client.post(
        "/wg/board/info/1/edit",
        data={"csrf": token, "title": "WLAN", "body": "Netz: WG-Netz\nPasswort: geheim"},
        headers={"origin": "http://127.0.0.1:8000"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    edit_page = client.get("/wg/board/info/1/edit").text
    assert "geheim" in edit_page
