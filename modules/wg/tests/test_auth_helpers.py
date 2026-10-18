import time

from starlette.requests import Request

from app import auth
from app.config import settings


def test_auth_cookie_roundtrip() -> None:
    token = auth.sign_auth_cookie(cookie_version=3)
    assert auth.read_auth_cookie(token) == {"v": 3}


def test_member_cookie_roundtrip() -> None:
    token = auth.sign_member_cookie(member_id=7, cookie_version=2)
    assert auth.read_member_cookie(token) == {"m": 7, "v": 2}


def test_tampered_cookie_is_rejected() -> None:
    token = auth.sign_auth_cookie(cookie_version=1)
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    assert auth.read_auth_cookie(tampered) is None


def test_garbage_cookie_is_rejected() -> None:
    assert auth.read_auth_cookie("not-a-real-token") is None
    assert auth.read_member_cookie("not-a-real-token") is None


def test_csrf_token_matches_only_for_same_version_and_member() -> None:
    token = auth.csrf_token(cookie_version=1, member_id=5)
    assert auth.csrf_token_matches(token, cookie_version=1, member_id=5)
    assert not auth.csrf_token_matches(token, cookie_version=2, member_id=5)
    assert not auth.csrf_token_matches(token, cookie_version=1, member_id=6)
    assert not auth.csrf_token_matches(None, cookie_version=1, member_id=5)


def test_join_rate_limit_blocks_after_ten_failures() -> None:
    auth._join_failures.clear()
    ip = "203.0.113.42"
    for _ in range(auth.RATE_LIMIT_MAX_FAILURES):
        assert not auth.is_join_rate_limited(ip)
        auth.record_join_failure(ip)
    assert auth.is_join_rate_limited(ip)


def test_join_rate_limit_only_counts_recent_failures(monkeypatch) -> None:
    auth._join_failures.clear()
    ip = "203.0.113.99"
    stale_moment = time.time() - auth.RATE_LIMIT_WINDOW_SECONDS - 1
    auth._join_failures[ip] = [stale_moment] * auth.RATE_LIMIT_MAX_FAILURES
    assert not auth.is_join_rate_limited(ip)


def _request_with_headers(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope)


def test_origin_is_trusted_for_a_real_browser_style_bare_origin() -> None:
    # A real Origin header never carries a path, unlike APP_BASE_URL
    # ("https://<domain>/wg") - this is the bug test_welcome_and_join.py's
    # manual smoke test caught: comparing the two directly never matches.
    bare_origin = "/".join(settings.app_base_url.split("/")[:3])
    assert auth.origin_is_trusted(_request_with_headers({"origin": bare_origin}))


def test_origin_is_trusted_rejects_a_different_host() -> None:
    assert not auth.origin_is_trusted(_request_with_headers({"origin": "https://evil.example"}))


def test_origin_is_trusted_falls_back_to_referer() -> None:
    bare_origin = "/".join(settings.app_base_url.split("/")[:3])
    request = _request_with_headers({"referer": f"{bare_origin}/wg/chores"})
    assert auth.origin_is_trusted(request)


def test_origin_is_trusted_rejects_missing_headers() -> None:
    assert not auth.origin_is_trusted(_request_with_headers({}))
