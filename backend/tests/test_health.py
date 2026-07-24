from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_scanner_journal_summary() -> None:
    response = client.get("/api/v1/scanner/journal/summary")

    assert response.status_code == 200
    assert "summary" in response.json()


def test_scanner_journal_performance() -> None:
    response = client.get("/api/v1/scanner/journal/performance")

    assert response.status_code == 200
    scanners = {row["scanner"] for row in response.json()["performance"]}
    assert {"orb_vwap_pullback", "strat_fvg_liquidity"} <= scanners


def test_scanner_symbol_performance() -> None:
    response = client.get("/api/v1/scanner/journal/symbol-performance")

    assert response.status_code == 200
    assert "performance" in response.json()


def test_robinhood_data_source_is_blocked_until_adapter_exists() -> None:
    response = client.get(
        "/api/v1/scanner/signals",
        params={"data_source": "robinhood_mcp", "record": "false"},
    )

    assert response.status_code == 501
    assert "verified in Codex" in response.json()["detail"]


def test_robinhood_filter_specs_endpoint() -> None:
    response = client.get("/api/v1/scanner/robinhood/filter-specs")

    assert response.status_code == 200
    assert "FILTER_TYPE_VWAP" in response.json()["filters"]


def test_model_providers_endpoint() -> None:
    response = client.get("/api/v1/agents/model-providers")

    assert response.status_code == 200
    assert response.json()["active"] == "none"
    assert "deterministic math" in response.json()["scanner_dependency"]
