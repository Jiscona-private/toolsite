from datetime import date

from fastapi.testclient import TestClient

from app import auth
from app.models import Chore, Member, RotaConfig, Setting
from app.timezone import berlin_today, week_start

CHORE_KEYS = ["floor", "kitchen", "big_bath", "small_bath"]


def _seed(client: TestClient) -> dict:
    with client.session_local() as db:
        db.add(Setting(key="cookie_version", value="1"))

        members = {}
        for position, name in enumerate(["Jakob", "Clara", "Daniel", "Bato"]):
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
        db.flush()

        chores = {}
        for position, key in enumerate(CHORE_KEYS):
            chore = Chore(key=key, name_de=key, name_en=key, position=position)
            db.add(chore)
            chores[key] = chore
        db.flush()

        current_monday = week_start(berlin_today())
        db.add(
            RotaConfig(
                valid_from=current_monday,
                chore_ids=[chores[k].id for k in CHORE_KEYS],
                # Jakob gets `floor` this week, so the logged-in user below
                # always has an action-eligible "own" row regardless of
                # which real-world date the suite runs on.
                slots=[
                    members["Jakob"].id,
                    members["Clara"].id,
                    members["Daniel"].id,
                    members["Bato"].id,
                ],
                created_by=None,
            )
        )
        db.commit()

        return {
            "week": current_monday,
            "member_id": {name: m.id for name, m in members.items()},
            "chore_id": {key: c.id for key, c in chores.items()},
        }


def _login_as(client: TestClient, member_id: int) -> None:
    client.cookies.set(auth.COOKIE_AUTH, auth.sign_auth_cookie(cookie_version=1))
    client.cookies.set(auth.COOKIE_MEMBER, auth.sign_member_cookie(member_id, cookie_version=1))


def test_chores_page_shows_own_chore_first_with_actions(client: TestClient) -> None:
    seeded = _seed(client)
    _login_as(client, seeded["member_id"]["Jakob"])

    response = client.get("/wg/chores")
    assert response.status_code == 200
    body = response.text
    assert "Erledigt" in body
    assert "Auslassen" in body
    assert body.index("floor") < body.index("kitchen")  # own chore (floor) listed first


def _csrf_for(client: TestClient, member_id: int) -> str:
    with client.session_local() as db:
        cookie_version = int(db.get(Setting, "cookie_version").value)
    return auth.csrf_token(cookie_version, member_id)


def test_mark_done_via_hidden_form_field_works(client: TestClient) -> None:
    # This is the exact path a real BaseHTTPMiddleware body-read bug broke:
    # reading request.form() in the gate drained the body before this
    # Form(...) field could be parsed. Regression test for that fix.
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    week = seeded["week"].isoformat()
    chore_id = seeded["chore_id"]["floor"]
    response = client.post(
        f"/wg/chores/{week}/{chore_id}/done",
        data={"csrf": token},
        headers={"origin": "http://127.0.0.1:8000"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    page = client.get("/wg/chores")
    assert "erledigt" in page.text


def test_mark_done_via_header_works(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    week = seeded["week"].isoformat()
    chore_id = seeded["chore_id"]["floor"]
    response = client.post(
        f"/wg/chores/{week}/{chore_id}/done",
        headers={"origin": "http://127.0.0.1:8000", "x-csrf-token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_mark_done_without_csrf_is_forbidden(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)

    week = seeded["week"].isoformat()
    chore_id = seeded["chore_id"]["floor"]
    response = client.post(
        f"/wg/chores/{week}/{chore_id}/done",
        headers={"origin": "http://127.0.0.1:8000"},
    )
    assert response.status_code == 403


def test_mark_done_with_untrusted_origin_is_forbidden(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    week = seeded["week"].isoformat()
    chore_id = seeded["chore_id"]["floor"]
    response = client.post(
        f"/wg/chores/{week}/{chore_id}/done",
        data={"csrf": token},
        headers={"origin": "https://evil.example"},
    )
    assert response.status_code == 403


def test_skip_requires_a_reason_of_at_least_three_characters(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    week = seeded["week"].isoformat()
    chore_id = seeded["chore_id"]["floor"]
    response = client.post(
        f"/wg/chores/{week}/{chore_id}/skip",
        data={"csrf": token, "reason": "ab"},
        headers={"origin": "http://127.0.0.1:8000"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "error=reason_required" in response.headers["location"]

    page = client.get("/wg/chores")
    assert "ausgelassen" not in page.text


def test_skip_with_valid_reason_shows_skipped_status_and_reason(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    week = seeded["week"].isoformat()
    chore_id = seeded["chore_id"]["floor"]
    client.post(
        f"/wg/chores/{week}/{chore_id}/skip",
        data={"csrf": token, "reason": "im Urlaub"},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    page = client.get("/wg/chores").text
    assert "ausgelassen" in page
    assert "im Urlaub" in page


def test_undo_restores_open_status_for_current_week(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    week = seeded["week"].isoformat()
    chore_id = seeded["chore_id"]["floor"]
    client.post(
        f"/wg/chores/{week}/{chore_id}/done",
        data={"csrf": token},
        headers={"origin": "http://127.0.0.1:8000"},
    )
    client.post(
        f"/wg/chores/{week}/{chore_id}/undo",
        data={"csrf": token},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    page = client.get("/wg/chores").text
    assert "chip done" not in page


def test_undo_is_rejected_for_weeks_further_back_than_last_week(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    old_week = seeded["week"].fromisocalendar(2020, 1, 1).isoformat()
    chore_id = seeded["chore_id"]["floor"]
    response = client.post(
        f"/wg/chores/{old_week}/{chore_id}/undo",
        data={"csrf": token},
        headers={"origin": "http://127.0.0.1:8000"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "error=undo_not_allowed" in response.headers["location"]


def _seed_spec_table(client: TestClient) -> dict:
    """The exact seed.toml configuration, so the upcoming-weeks table can
    be checked against spec.md §10.1's own worked example."""
    with client.session_local() as db:
        db.add(Setting(key="cookie_version", value="1"))
        members = {}
        for position, name in enumerate(["Jakob", "Clara", "Daniel", "Bato"]):
            member = Member(
                name=name,
                language="de",
                color=position,
                position=position,
                active=True,
                joined_on=date(2026, 10, 19),
                ntfy_topic=f"wg-bbbbbbb{position}-{name.lower()}",
                notify_prefs={},
            )
            db.add(member)
            members[name] = member
        db.flush()
        chores = {}
        for position, key in enumerate(CHORE_KEYS):
            chore = Chore(key=key, name_de=key, name_en=key, position=position)
            db.add(chore)
            chores[key] = chore
        db.flush()
        db.add(
            RotaConfig(
                valid_from=date(2026, 10, 19),
                chore_ids=[chores[k].id for k in CHORE_KEYS],
                slots=[
                    members["Clara"].id,
                    members["Bato"].id,
                    members["Jakob"].id,
                    members["Daniel"].id,
                ],
                created_by=None,
            )
        )
        db.commit()
        return {"member_id": {name: m.id for name, m in members.items()}}


def test_upcoming_table_columns_stay_aligned_to_the_header_across_weeks(
    client: TestClient,
) -> None:
    # Regression test: the table header must list chores in a fixed order,
    # and every week's row must follow that same order - not each week's
    # own "my chore first" order (which differs week to week and broke the
    # header/cell alignment in an earlier version of this page).
    seeded = _seed_spec_table(client)
    _login_as(client, seeded["member_id"]["Clara"])  # Clara: floor in KW43, kitchen in KW44

    page = client.get("/wg/chores?week=2026-10-19").text
    header_order = page.split("<thead>")[1].split("</thead>")[0]
    assert header_order.index("floor") < header_order.index("kitchen")

    week_44_row = page.split('scope="row">KW 44</th>')[1].split("</tr>")[0]
    assert week_44_row.index("Daniel") < week_44_row.index("Clara")  # floor col before kitchen col
