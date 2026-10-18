from datetime import date

from fastapi.testclient import TestClient

from app import auth
from app.models import ExpenseCategory, Member, Setting

MEMBER_NAMES = ["Jakob", "Clara", "Daniel", "Bato"]


def _seed(client: TestClient) -> dict:
    with client.session_local() as db:
        db.add(Setting(key="cookie_version", value="1"))
        members = {}
        for position, name in enumerate(MEMBER_NAMES):
            member = Member(
                name=name,
                language="de",
                color=position,
                position=position,
                active=True,
                joined_on=date(2026, 10, 19),
                ntfy_topic=f"wg-aaaaaaa{position}-{name.lower()}",
                notify_prefs={},
            )
            db.add(member)
            members[name] = member
        db.add(
            ExpenseCategory(
                key="groceries", name_de="Lebensmittel", name_en="Groceries", position=0
            )
        )
        db.commit()
        return {"member_id": {name: m.id for name, m in members.items()}}


def _login_as(client: TestClient, member_id: int) -> None:
    client.cookies.set(auth.COOKIE_AUTH, auth.sign_auth_cookie(cookie_version=1))
    client.cookies.set(auth.COOKIE_MEMBER, auth.sign_member_cookie(member_id, cookie_version=1))


def _csrf_for(client: TestClient, member_id: int) -> str:
    with client.session_local() as db:
        cookie_version = int(db.get(Setting, "cookie_version").value)
    return auth.csrf_token(cookie_version, member_id)


def _create_expense(client: TestClient, seeded: dict, token: str, **overrides) -> None:
    data = {
        "csrf": token,
        "description": "Großeinkauf",
        "amount": "48,60",
        "paid_by_id": seeded["member_id"]["Clara"],
        "spent_on": "2026-10-18",
        "participants": [seeded["member_id"][n] for n in MEMBER_NAMES],
    }
    data.update(overrides)
    return client.post(
        "/wg/expenses/new",
        data=data,
        headers={"origin": "http://127.0.0.1:8000"},
        follow_redirects=False,
    )


def test_expenses_page_shows_balance_and_recent_expense(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    response = _create_expense(client, seeded, token)
    assert response.status_code == 303

    page = client.get("/wg/expenses").text
    assert "Großeinkauf" in page
    assert "−12,15" in page  # Jakob's share-only balance, real minus sign
    assert "alle 4" in page


def test_create_expense_without_participants_shows_error(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    response = client.post(
        "/wg/expenses/new",
        data={
            "csrf": token,
            "description": "Test",
            "amount": "10",
            "paid_by_id": jakob,
            "spent_on": "2026-10-18",
        },
        headers={"origin": "http://127.0.0.1:8000"},
    )
    assert response.status_code == 400
    assert "mindestens einen Teilnehmer" in response.text


def test_create_expense_with_invalid_amount_shows_error(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    response = _create_expense(client, seeded, token, amount="0")
    assert response.status_code == 400
    assert "gültigen Betrag" in response.text


def test_create_expense_with_date_too_far_in_future_shows_error(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    response = _create_expense(client, seeded, token, spent_on="2099-01-01")
    assert response.status_code == 400
    assert "ein Jahr in der Zukunft" in response.text


def test_create_expense_without_csrf_is_forbidden(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)

    response = client.post(
        "/wg/expenses/new",
        data={
            "description": "Test",
            "amount": "10",
            "paid_by_id": jakob,
            "spent_on": "2026-10-18",
            "participants": [jakob],
        },
        headers={"origin": "http://127.0.0.1:8000"},
    )
    assert response.status_code == 403


def test_edit_expense_recomputes_shares_and_balance(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    clara = seeded["member_id"]["Clara"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)
    _create_expense(client, seeded, token)

    response = client.post(
        "/wg/expenses/1/edit",
        data={
            "csrf": token,
            "description": "Großeinkauf (bearbeitet)",
            "amount": "40,00",
            "paid_by_id": clara,
            "spent_on": "2026-10-18",
            "participants": [jakob, clara],
        },
        headers={"origin": "http://127.0.0.1:8000"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    page = client.get("/wg/expenses").text
    assert "Großeinkauf (bearbeitet)" in page
    assert "−20,00" in page  # Jakob now owes half of 40,00


def test_delete_expense_restores_balance_to_zero(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)
    _create_expense(client, seeded, token, paid_by_id=jakob)

    client.post(
        "/wg/expenses/1/delete",
        data={"csrf": token},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    page = client.get("/wg/expenses").text
    assert "0,00" in page.split("Dein Saldo")[1][:200]


def test_settlement_updates_balance_and_can_be_undone(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    clara = seeded["member_id"]["Clara"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)
    _create_expense(client, seeded, token)  # Clara paid, Jakob owes 12.15

    response = client.post(
        "/wg/settlements",
        data={"csrf": token, "to_member_id": clara, "amount": "12.15"},
        headers={"origin": "http://127.0.0.1:8000"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    page = client.get("/wg/expenses").text
    assert "0,00" in page.split("Dein Saldo")[1][:200]

    client.post(
        "/wg/settlements/1/delete",
        data={"csrf": token},
        headers={"origin": "http://127.0.0.1:8000"},
    )
    page = client.get("/wg/expenses").text
    assert "−12,15" in page.split("Dein Saldo")[1][:200]


def test_expenses_all_page_lists_everything(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)
    _create_expense(client, seeded, token, description="Eins")
    _create_expense(client, seeded, token, description="Zwei")

    page = client.get("/wg/expenses/all").text
    assert "Eins" in page
    assert "Zwei" in page
