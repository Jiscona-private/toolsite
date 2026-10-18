from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz_ok() -> None:
    response = client.get("/wg/healthz")
    assert response.status_code == 200
    assert response.text == "ok"


def test_healthz_only_under_base_path() -> None:
    response = client.get("/healthz")
    assert response.status_code == 404
