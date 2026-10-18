from datetime import date

from fastapi.testclient import TestClient

from app import auth
from app.models import ActivityLog, Member, Setting


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


def test_add_item_appears_on_the_page(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    response = client.post(
        "/wg/shopping",
        data={"csrf": token, "name": "Klopapier", "quantity": "1 Paket"},
        headers={"origin": "http://127.0.0.1:8000"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    page = client.get("/wg/shopping").text
    assert "Klopapier" in page
    assert "1 Paket" in page
    assert "1 offen" in page


def test_duplicate_item_is_not_added_twice(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    client.post(
        "/wg/shopping",
        data={"csrf": token, "name": "Klopapier"},
        headers={"origin": "http://127.0.0.1:8000"},
    )
    response = client.post(
        "/wg/shopping",
        data={"csrf": token, "name": "klopapier"},
        headers={"origin": "http://127.0.0.1:8000"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "duplicate=klopapier" in response.headers["location"]

    page = client.get(response.headers["location"]).text
    assert "steht schon drauf" in page
    assert page.count("checkbox-row") == 1


def test_toggle_moves_item_between_sections(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)
    client.post(
        "/wg/shopping",
        data={"csrf": token, "name": "Seife"},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    client.post(
        "/wg/shopping/1/toggle",
        data={"csrf": token},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    page = client.get("/wg/shopping").text
    assert "Im Wagen" in page
    assert "checkbox-row checked" in page
    assert "1 Artikel als Ausgabe eintragen" in page


def test_toggle_via_htmx_returns_only_the_fragment(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)
    client.post(
        "/wg/shopping",
        data={"csrf": token, "name": "Seife"},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    response = client.post(
        "/wg/shopping/1/toggle",
        data={"csrf": token},
        headers={"origin": "http://127.0.0.1:8000", "hx-request": "true"},
    )
    assert response.status_code == 200
    assert "<html" not in response.text
    assert "checkbox-row checked" in response.text


def test_clear_checked_removes_only_checked_items(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)
    client.post(
        "/wg/shopping",
        data={"csrf": token, "name": "A"},
        headers={"origin": "http://127.0.0.1:8000"},
    )
    client.post(
        "/wg/shopping",
        data={"csrf": token, "name": "B"},
        headers={"origin": "http://127.0.0.1:8000"},
    )
    client.post(
        "/wg/shopping/2/toggle",
        data={"csrf": token},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    client.post(
        "/wg/shopping/clear-checked",
        data={"csrf": token},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    page = client.get("/wg/shopping").text
    assert "A" in page
    assert "B" not in page


def test_expenses_new_prefills_description_from_items(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)
    client.post(
        "/wg/shopping",
        data={"csrf": token, "name": "Eier"},
        headers={"origin": "http://127.0.0.1:8000"},
    )
    client.post(
        "/wg/shopping",
        data={"csrf": token, "name": "Milch"},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    page = client.get("/wg/expenses/new?items=1,2").text
    assert 'value="Eier, Milch"' in page
    assert 'name="items" value="1,2"' in page


def test_saving_expense_with_items_links_and_archives_shopping_items(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)
    client.post(
        "/wg/shopping",
        data={"csrf": token, "name": "Eier"},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    response = client.post(
        "/wg/expenses/new",
        data={
            "csrf": token,
            "description": "Eier",
            "amount": "3,50",
            "paid_by_id": jakob,
            "spent_on": "2026-10-18",
            "participants": [jakob],
            "items": "1",
        },
        headers={"origin": "http://127.0.0.1:8000"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    page = client.get("/wg/shopping").text
    assert "Eier" not in page


def test_add_toggle_and_clear_checked_each_write_an_activity_log_entry(
    client: TestClient,
) -> None:
    seeded = _seed(client)
    jakob = seeded["jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    origin = {"origin": "http://127.0.0.1:8000"}
    client.post("/wg/shopping", data={"csrf": token, "name": "Seife"}, headers=origin)
    client.post("/wg/shopping/1/toggle", data={"csrf": token}, headers=origin)
    client.post("/wg/shopping/1/toggle", data={"csrf": token}, headers=origin)
    client.post("/wg/shopping/clear-checked", data={"csrf": token}, headers=origin)

    with client.session_local() as db:
        keys = [
            e.summary_key for e in db.query(ActivityLog).filter_by(entity="shopping_item").all()
        ]
    assert keys == [
        "log.shopping.create",
        "log.shopping.check",
        "log.shopping.uncheck",
    ]
