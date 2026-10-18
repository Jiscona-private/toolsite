from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient

from app import auth
from app.models import (
    ActivityLog,
    Chore,
    ExpenseCategory,
    Member,
    Note,
    RotaConfig,
    Setting,
    Settlement,
)
from app.timezone import berlin_today, week_start

CHORE_KEYS = ["floor", "kitchen", "big_bath", "small_bath"]


def _seed(client: TestClient) -> dict:
    with client.session_local() as db:
        db.add(Setting(key="cookie_version", value="1"))
        db.add(Setting(key="join_token", value="secret-token"))
        db.add(Setting(key="default_language", value="de"))
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
        return {
            "member_id": {name: m.id for name, m in members.items()},
            "chore_id": {key: c.id for key, c in chores.items()},
        }


def _login_as(client: TestClient, member_id: int) -> None:
    client.cookies.set(auth.COOKIE_AUTH, auth.sign_auth_cookie(cookie_version=1))
    client.cookies.set(auth.COOKIE_MEMBER, auth.sign_member_cookie(member_id, cookie_version=1))


def _csrf_for(client: TestClient, member_id: int) -> str:
    with client.session_local() as db:
        cookie_version = int(db.get(Setting, "cookie_version").value)
    return auth.csrf_token(cookie_version, member_id)


def test_settings_page_lists_members_chores_categories_and_link(client: TestClient) -> None:
    seeded = _seed(client)
    _login_as(client, seeded["member_id"]["Jakob"])

    page = client.get("/wg/settings").text
    assert "Jakob" in page
    assert "Clara" in page
    assert "floor" in page
    assert "secret-token" in page
    assert "data:image/svg+xml" in page  # QR code


def test_add_member_creates_member_and_rebuilds_rota(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    response = client.post(
        "/wg/settings/members/new",
        data={"csrf": token, "name": "Eva"},
        headers={"origin": "http://127.0.0.1:8000"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    with client.session_local() as db:
        eva = db.query(Member).filter_by(name="Eva").one()
        assert eva.active
        next_week = week_start(berlin_today())
        configs = db.query(RotaConfig).filter(RotaConfig.valid_from >= next_week).all()
        assert len(configs) >= 1


def test_deactivate_member_frees_their_chore_slot(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    bato = seeded["member_id"]["Bato"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    client.post(
        f"/wg/settings/members/{bato}/toggle-active",
        data={"csrf": token},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    with client.session_local() as db:
        assert not db.get(Member, bato).active
        assert db.get(Member, bato).left_on is not None


def test_toggle_chore_active(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    floor_id = seeded["chore_id"]["floor"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    client.post(
        f"/wg/settings/chores/{floor_id}/toggle-active",
        data={"csrf": token},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    with client.session_local() as db:
        assert not db.get(Chore, floor_id).active


def test_add_and_toggle_category(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    client.post(
        "/wg/settings/categories/new",
        data={"csrf": token, "name": "Freizeit"},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    with client.session_local() as db:
        category = db.query(ExpenseCategory).filter_by(key="freizeit").one()
        assert category.active

    client.post(
        f"/wg/settings/categories/{category.id}/toggle-active",
        data={"csrf": token},
        headers={"origin": "http://127.0.0.1:8000"},
    )
    with client.session_local() as db:
        assert not db.get(ExpenseCategory, category.id).active


def test_manual_rota_rebuild_this_week(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    response = client.post(
        "/wg/settings/rota/rebuild",
        data={"csrf": token, "when": "this"},
        headers={"origin": "http://127.0.0.1:8000"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    with client.session_local() as db:
        configs = db.query(RotaConfig).all()
        assert any(c.valid_from == week_start(berlin_today()) for c in configs)


def test_rotate_link_invalidates_old_token(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    client.post(
        "/wg/settings/rotate-link",
        data={"csrf": token},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    assert client.get("/wg/join/secret-token").status_code == 404
    with client.session_local() as db:
        new_token = db.get(Setting, "join_token").value
    assert new_token != "secret-token"


def test_logout_all_invalidates_the_current_session_too(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    client.post(
        "/wg/settings/logout-all",
        data={"csrf": token},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    assert client.get("/wg/").status_code == 404


def test_toggle_member_active_writes_an_activity_log_entry(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    bato = seeded["member_id"]["Bato"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    client.post(
        f"/wg/settings/members/{bato}/toggle-active",
        data={"csrf": token},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    with client.session_local() as db:
        entry = db.query(ActivityLog).filter_by(entity="member", entity_id=bato).one()
        assert entry.actor_member_id == jakob
        assert entry.summary_key == "log.member.deactivate"
        assert entry.summary_params == {"name": "Bato"}


def test_rebuild_rota_writes_an_activity_log_entry(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    client.post(
        "/wg/settings/rota/rebuild",
        data={"csrf": token, "when": "this"},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    with client.session_local() as db:
        entry = db.query(ActivityLog).filter_by(entity="rota_config").one()
        assert entry.summary_key == "log.rota.rebuild"


def test_activity_page_lists_recent_entries(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    client.post(
        "/wg/settings/rotate-link",
        data={"csrf": token},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    page = client.get("/wg/settings/activity").text
    assert "Jakob" in page


def test_trash_page_lists_a_deleted_note_and_restores_it(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    with client.session_local() as db:
        note = Note(body="Müll raus bringen", pinned=False, expires_on=None, created_by=jakob)
        db.add(note)
        db.flush()
        note.deleted_at = datetime.now(UTC)
        note_id = note.id
        db.commit()

    trash_page = client.get("/wg/settings/trash").text
    assert "Müll raus bringen" in trash_page

    response = client.post(
        f"/wg/settings/trash/note/{note_id}/restore",
        data={"csrf": token},
        headers={"origin": "http://127.0.0.1:8000"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    with client.session_local() as db:
        assert db.get(Note, note_id).deleted_at is None
        entry = db.query(ActivityLog).filter_by(entity="note", entity_id=note_id).one()
        assert entry.summary_key == "log.note.restore"

    assert "Müll raus bringen" not in client.get("/wg/settings/trash").text


def test_trash_page_lists_deleted_settlement(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)

    with client.session_local() as db:
        settlement = Settlement(
            from_member_id=jakob,
            to_member_id=seeded["member_id"]["Clara"],
            amount_cents=1234,
            paid_on=berlin_today(),
            created_by=jakob,
        )
        db.add(settlement)
        db.flush()
        settlement.deleted_at = datetime.now(UTC)
        db.commit()

    trash_page = client.get("/wg/settings/trash").text
    assert "12,34" in trash_page


def test_restoring_an_item_not_in_the_trash_is_a_no_op(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)
    token = _csrf_for(client, jakob)

    with client.session_local() as db:
        note = Note(body="not deleted", pinned=False, expires_on=None, created_by=jakob)
        db.add(note)
        db.commit()
        note_id = note.id

    client.post(
        f"/wg/settings/trash/note/{note_id}/restore",
        data={"csrf": token},
        headers={"origin": "http://127.0.0.1:8000"},
    )

    with client.session_local() as db:
        assert db.query(ActivityLog).filter_by(entity="note", entity_id=note_id).first() is None


def test_restore_trash_item_requires_csrf(client: TestClient) -> None:
    seeded = _seed(client)
    jakob = seeded["member_id"]["Jakob"]
    _login_as(client, jakob)

    with client.session_local() as db:
        note = Note(body="x", pinned=False, expires_on=None, created_by=jakob)
        db.add(note)
        db.flush()
        note.deleted_at = datetime.now(UTC) - timedelta(days=1)
        note_id = note.id
        db.commit()

    response = client.post(
        f"/wg/settings/trash/note/{note_id}/restore",
        headers={"origin": "http://127.0.0.1:8000"},
    )
    assert response.status_code == 403

    with client.session_local() as db:
        assert db.get(Note, note_id).deleted_at is not None
