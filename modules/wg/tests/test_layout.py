from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from app import auth
from app.models import Member, Setting
from app.templating import templates


def _authenticated_member(client: TestClient) -> int:
    with client.session_local() as db:
        db.add(Setting(key="cookie_version", value="1"))
        db.add(Setting(key="wg_name", value="WG-Manager v1"))
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
        member_id = member.id

    client.cookies.set(auth.COOKIE_AUTH, auth.sign_auth_cookie(cookie_version=1))
    client.cookies.set(auth.COOKIE_MEMBER, auth.sign_member_cookie(member_id, cookie_version=1))
    return member_id


def test_static_assets_are_served(client: TestClient) -> None:
    _authenticated_member(client)
    for path, content_type_prefix in [
        ("/wg/static/css/app.css", "text/css"),
        ("/wg/static/js/htmx.min.js", "text/javascript"),
        ("/wg/static/js/app.js", "text/javascript"),
        ("/wg/static/icons/sprite.svg", "image/svg"),
        ("/wg/static/fonts/figtree-400.woff2", "font/woff2"),
    ]:
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.headers["content-type"].startswith(content_type_prefix), path


def test_static_assets_are_behind_the_access_gate(client: TestClient) -> None:
    with client.session_local() as db:
        db.add(Setting(key="cookie_version", value="1"))
        db.commit()
    response = client.get("/wg/static/css/app.css")
    assert response.status_code == 404


def test_new_page_lists_all_three_sheet_options(client: TestClient) -> None:
    _authenticated_member(client)
    response = client.get("/wg/new")
    assert response.status_code == 200
    assert "Ausgabe" in response.text
    assert "Einkaufsliste" in response.text
    assert "Notiz an die Pinnwand" in response.text


def test_new_page_uses_wg_name_and_member_avatar(client: TestClient) -> None:
    _authenticated_member(client)
    response = client.get("/wg/new")
    assert "WG-Manager v1" in response.text
    assert ">J</a>" in response.text  # avatar initial


def test_base_layout_marks_active_nav_item_with_aria_current() -> None:
    template = templates.env.from_string(
        '{% extends "base.html" %}{% block content %}x{% endblock %}'
    )
    html = template.render(
        t=lambda key, **params: key,
        lang="de",
        base_path="/wg",
        wg_name="WG-Manager v1",
        member=None,
        active_nav="chores",
    )
    assert html.count('aria-current="page"') == 1
    chores_link_start = html.index('href="/wg/chores"')
    next_link_start = html.index('href="/wg/new"')
    assert 'aria-current="page"' in html[chores_link_start:next_link_start]


def test_base_layout_has_no_active_nav_when_unset() -> None:
    template = templates.env.from_string(
        '{% extends "base.html" %}{% block content %}x{% endblock %}'
    )
    html = template.render(
        t=lambda key, **params: key,
        lang="de",
        base_path="/wg",
        wg_name="WG-Manager v1",
        member=None,
        active_nav=None,
    )
    assert "aria-current" not in html


def test_icon_svgs_have_a_default_size() -> None:
    # Regression test: an <svg> with no explicit width/height falls back to
    # the browser default replaced-element size (300x150), which showed up
    # as a large empty box next to the chores week-switcher before this css
    # rule existed (every icon svg here is on a 24px grid and aria-hidden).
    css = (Path(__file__).parent.parent / "app" / "static" / "css" / "app.css").read_text()
    assert 'svg[aria-hidden="true"]' in css
