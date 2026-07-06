from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_unimplemented_endpoint_fails_loudly() -> None:
    response = client.get("/api/v1/strategies")

    assert response.status_code == 501
    assert response.json()["detail"]["status"] == "not_implemented"

