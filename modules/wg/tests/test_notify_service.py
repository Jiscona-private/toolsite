import httpx
import pytest
from sqlalchemy.orm import sessionmaker

from app.models import Setting
from app.services import notify


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None


def test_send_ntfy_posts_the_expected_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_post(url, *, json, timeout):
        calls.append((url, json, timeout))
        return _FakeResponse()

    monkeypatch.setattr(httpx, "post", fake_post)

    assert notify.send_ntfy("wg-admin-x", title="WG-App", message="hallo", tags=["warning"])
    url, payload, timeout = calls[0]
    assert payload == {
        "topic": "wg-admin-x",
        "title": "WG-App",
        "message": "hallo",
        "priority": 3,
        "tags": ["warning"],
    }
    assert timeout == notify.NTFY_TIMEOUT_SECONDS


def test_send_ntfy_retries_once_then_gives_up(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = []

    def failing_post(url, *, json, timeout):
        attempts.append(1)
        raise httpx.ConnectError("unreachable")

    monkeypatch.setattr(httpx, "post", failing_post)

    assert notify.send_ntfy("wg-admin-x", title="t", message="m") is False
    assert len(attempts) == 2  # one retry, per spec.md §8.2


def test_send_admin_alert_without_a_configured_topic_is_a_noop(
    session_local: sessionmaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = []
    monkeypatch.setattr(notify, "send_ntfy", lambda *a, **k: called.append(1))

    with session_local() as db:
        assert notify.send_admin_alert(db, "x") is False
    assert called == []


def test_send_admin_alert_posts_to_the_configured_topic(
    session_local: sessionmaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = {}
    monkeypatch.setattr(
        notify, "send_ntfy", lambda topic, **kwargs: captured.update(topic=topic, **kwargs) or True
    )

    with session_local() as db:
        db.add(Setting(key="admin_ntfy_topic", value="wg-admin-abc123"))
        db.commit()
        assert notify.send_admin_alert(db, "Backup fehlgeschlagen") is True

    assert captured["topic"] == "wg-admin-abc123"
    assert captured["message"] == "Backup fehlgeschlagen"
