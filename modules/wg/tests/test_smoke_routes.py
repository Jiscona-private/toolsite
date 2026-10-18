from datetime import date

from fastapi.testclient import TestClient

from app import auth
from app.models import (
    Chore,
    Expense,
    ExpenseCategory,
    ExpenseShare,
    InfoPage,
    Member,
    Note,
    RotaConfig,
    Setting,
    Settlement,
    ShoppingItem,
)
from app.timezone import berlin_today, week_start

CHORE_KEYS = ["floor", "kitchen", "big_bath", "small_bath"]


def _seed_everything(client: TestClient) -> dict:
    """One member of every entity the app has, so every GET route - list
    pages and single-item edit pages alike - has something real to
    render. Qualitätsrunde: smoke-test every GET route in one pass."""
    with client.session_local() as db:
        db.add(Setting(key="cookie_version", value="1"))
        db.add(Setting(key="wg_name", value="WG-Manager v1"))
        db.add(Setting(key="join_token", value="smoke-token"))
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

        current_week = week_start(berlin_today())
        db.add(
            RotaConfig(
                valid_from=current_week,
                chore_ids=[chores[k].id for k in CHORE_KEYS],
                slots=[m.id for m in members.values()],
                created_by=None,
            )
        )

        category = ExpenseCategory(
            key="groceries", name_de="Lebensmittel", name_en="Groceries", position=0
        )
        db.add(category)
        db.flush()

        expense = Expense(
            description="Großeinkauf",
            amount_cents=4000,
            paid_by_id=members["Jakob"].id,
            category_id=category.id,
            spent_on=current_week,
            created_by=members["Jakob"].id,
        )
        db.add(expense)
        db.flush()
        for member in members.values():
            db.add(ExpenseShare(expense_id=expense.id, member_id=member.id, share_cents=1000))

        db.add(
            Settlement(
                from_member_id=members["Clara"].id,
                to_member_id=members["Jakob"].id,
                amount_cents=1000,
                paid_on=current_week,
                created_by=members["Clara"].id,
            )
        )

        db.add(ShoppingItem(name="Milch", source="manual", added_by=members["Jakob"].id))

        db.add(Note(body="Hallo WG!", pinned=True, expires_on=None, created_by=members["Jakob"].id))
        info_page = InfoPage(title="WLAN", body="Netz: x", position=0)
        db.add(info_page)
        db.flush()

        db.commit()
        return {
            "jakob": members["Jakob"].id,
            "week": current_week,
            "expense_id": expense.id,
            "info_page_id": info_page.id,
        }


def _login_as(client: TestClient, member_id: int) -> None:
    client.cookies.set(auth.COOKIE_AUTH, auth.sign_auth_cookie(cookie_version=1))
    client.cookies.set(auth.COOKIE_MEMBER, auth.sign_member_cookie(member_id, cookie_version=1))


def test_every_get_route_renders_successfully(client: TestClient) -> None:
    seeded = _seed_everything(client)
    _login_as(client, seeded["jakob"])

    paths = [
        "/wg/",
        "/wg/new",
        "/wg/healthz",
        "/wg/welcome",
        "/wg/chores",
        f"/wg/chores?week={seeded['week'].isoformat()}",
        "/wg/expenses",
        "/wg/expenses/all",
        "/wg/expenses/new",
        f"/wg/expenses/{seeded['expense_id']}/edit",
        "/wg/shopping",
        "/wg/board",
        "/wg/board/notes/new",
        f"/wg/board/info/{seeded['info_page_id']}/edit",
        "/wg/profile",
        "/wg/settings",
        "/wg/settings/activity",
        "/wg/settings/trash",
        "/wg/manifest.webmanifest",
        "/wg/sw.js",
        "/wg/offline",
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, f"{path} -> {response.status_code}"
