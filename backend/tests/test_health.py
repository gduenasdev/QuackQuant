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


def test_scanner_journal_summary() -> None:
    response = client.get("/api/v1/scanner/journal/summary")

    assert response.status_code == 200
    assert "summary" in response.json()


def test_scanner_journal_performance() -> None:
    response = client.get("/api/v1/scanner/journal/performance")

    assert response.status_code == 200
    assert "performance" in response.json()


def test_robinhood_data_source_is_blocked_until_adapter_exists() -> None:
    response = client.get(
        "/api/v1/scanner/signals",
        params={"data_source": "robinhood_mcp", "record": "false"},
    )

    assert response.status_code == 501
    assert "Robinhood MCP" in response.json()["detail"]
