from datetime import date

from fastapi.testclient import TestClient

from app import auth
from app.models import Chore, Member, RotaConfig, Setting
from app.timezone import berlin_today, week_start

CHORE_KEYS = ["floor", "kitchen", "big_bath", "small_bath"]


def _seed_members_and_chores(client: TestClient) -> dict:
    with client.session_local() as db:
        db.add(Setting(key="cookie_version", value="1"))
        db.add(Setting(key="wg_name", value="WG-Manager v1"))
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
        db.commit()
        return {
            "member_id": {name: m.id for name, m in members.items()},
            "chore_id": {key: c.id for key, c in chores.items()},
        }


def _assign_current_week(client: TestClient, seeded: dict) -> None:
    """Gives Jakob `floor` for the real current week, so the home page has
    something other than "free" to show regardless of what day tests run."""
    with client.session_local() as db:
        db.add(
            RotaConfig(
                valid_from=week_start(berlin_today()),
                chore_ids=[seeded["chore_id"][k] for k in CHORE_KEYS],
                slots=[
                    seeded["member_id"]["Jakob"],
                    seeded["member_id"]["Clara"],
                    seeded["member_id"]["Daniel"],
                    seeded["member_id"]["Bato"],
                ],
                created_by=None,
            )
        )
        db.commit()


def _login_as(client: TestClient, member_id: int) -> None:
    client.cookies.set(auth.COOKIE_AUTH, auth.sign_auth_cookie(cookie_version=1))
    client.cookies.set(auth.COOKIE_MEMBER, auth.sign_member_cookie(member_id, cookie_version=1))


def _csrf_for(client: TestClient, member_id: int) -> str:
    with client.session_local() as db:
        cookie_version = int(db.get(Setting, "cookie_version").value)
    return auth.csrf_token(cookie_version, member_id)


def test_home_shows_greeting_and_week(client: TestClient) -> None:
    seeded = _seed_members_and_chores(client)
    _login_as(client, seeded["member_id"]["Jakob"])

    page = client.get("/wg/").text
    assert "Hallo Jakob" in page
    assert "WG-Manager v1" in page  # <title>


def test_hero_shows_free_state_without_a_rota_config(client: TestClient) -> None:
    seeded = _seed_members_and_chores(client)
    _login_as(client, seeded["member_id"]["Jakob"])

    page = client.get("/wg/").text
    assert "Diese Woche frei" in page


def test_hero_shows_open_chore_with_actions(client: TestClient) -> None:
    seeded = _seed_members_and_chores(client)
    _assign_current_week(client, seeded)
    _login_as(client, seeded["member_id"]["Jakob"])

    page = client.get("/wg/").text
    assert "Erledigt" in page
    assert "Auslassen" in page
    assert "Fällig bis" in page


def test_hero_shows_done_state_after_marking_done(client: TestClient) -> None:
    seeded = _seed_members_and_chores(client)
    _assign_current_week(client, seeded)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)
    week = week_start(berlin_today()).isoformat()
    floor_id = seeded["chore_id"]["floor"]

    client.post(
        f"/wg/chores/{week}/{floor_id}/done",
        data={"csrf": token},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    page = client.get("/wg/").text
    assert "Erledigt – danke!" in page
    assert "Rückgängig" in page


def test_chores_card_lists_own_row_first_with_suffix(client: TestClient) -> None:
    seeded = _seed_members_and_chores(client)
    _assign_current_week(client, seeded)
    _login_as(client, seeded["member_id"]["Jakob"])

    page = client.get("/wg/").text
    assert page.index("Jakob (du)") < page.index("Clara")


def test_balance_tile_shows_settled_when_zero(client: TestClient) -> None:
    seeded = _seed_members_and_chores(client)
    _login_as(client, seeded["member_id"]["Jakob"])

    page = client.get("/wg/").text
    assert "Alles ausgeglichen" in page


def test_balance_tile_shows_who_to_pay_when_negative(client: TestClient) -> None:
    seeded = _seed_members_and_chores(client)
    jakob = seeded["member_id"]["Jakob"]
    clara = seeded["member_id"]["Clara"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)
    all_four = list(seeded["member_id"].values())

    client.post(
        "/wg/expenses/new",
        data={
            "csrf": token,
            "description": "Internet",
            "amount": "40",
            "paid_by_id": clara,
            "spent_on": "2026-10-18",
            "participants": all_four,
        },
        headers={"origin": "http://127.0.0.1:8000"},
    )

    page = client.get("/wg/").text
    assert "−10,00" in page
    assert "an Clara überweisen" in page


def test_shopping_tile_shows_open_count_and_preview(client: TestClient) -> None:
    seeded = _seed_members_and_chores(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    client.post(
        "/wg/shopping",
        data={"csrf": token, "name": "Kaffee"},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    page = client.get("/wg/").text
    assert "1 offen" in page
    assert "Kaffee" in page


def test_board_card_links_to_board_and_shows_note_preview(client: TestClient) -> None:
    seeded = _seed_members_and_chores(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    client.post(
        "/wg/board/notes/new",
        data={"csrf": token, "body": "Hallo WG"},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    page = client.get("/wg/").text
    assert 'href="/wg/board"' in page
    assert "Hallo WG" in page


def test_home_does_not_double_render_profile_avatar(client: TestClient) -> None:
    # base.html's generic profile-avatar link must be suppressed on home
    # (own_avatar_header), since home.html builds its own combined
    # greeting+avatar header - otherwise the link to /profile would appear
    # twice (once from base.html, once from home.html's own header).
    seeded = _seed_members_and_chores(client)
    _login_as(client, seeded["member_id"]["Jakob"])

    page = client.get("/wg/").text
    assert page.count('href="/wg/profile"') == 1
