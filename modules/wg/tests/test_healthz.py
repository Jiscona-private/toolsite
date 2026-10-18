from fastapi.testclient import TestClient


def test_healthz_ok(client: TestClient) -> None:
    response = client.get("/wg/healthz")
    assert response.status_code == 200
    assert response.text == "ok"


def test_healthz_only_under_base_path(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 404
