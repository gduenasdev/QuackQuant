# QuackQuant

Paper-trading scanner dashboard for testing intraday strategies before any broker execution is
enabled.

## Local Development

Start the FastAPI backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
uvicorn app.main:app --reload --port 8001
```

Start the static dashboard from the repository root:

```bash
python3 -m http.server 8000 --bind 127.0.0.1
```

Open:

```text
http://127.0.0.1:8000
```

API docs are available at:

```text
http://127.0.0.1:8001/docs
```

## Current API

- `GET /api/v1/health`
- `GET /api/v1/ready`
- `GET /api/v1/scanner/signals`
- `GET /api/v1/scanner/data-sources`
- `GET /api/v1/scanner/robinhood/filter-specs`
- `GET /api/v1/scanner/journal`
- `GET /api/v1/scanner/journal/summary`
- `GET /api/v1/scanner/journal/performance`
- `GET /api/v1/agents/model-providers`

The scanner is paper-only. It records LONG/SHORT calls to a local CSV journal and updates open calls
as later scans touch stops or targets. It does not place trades.

## Scanner Notes

The dashboard currently supports:

- ORB/VWAP pullback scanner
- Strat/FVG/liquidity-sweep scanner
- Yahoo candle data for live paper scanning
- Robinhood MCP status/filter-spec documentation for the future adapter
- Optional LLM status display

Scanner signals, stops, targets, journal updates, and performance stats are deterministic math. An
LLM such as Ollama can be added later for explanations and journal review, but it is not required for
market data or paper trading.

See [`backend/tests/README_stock_monitor.md`](backend/tests/README_stock_monitor.md) for the trading
workflow and scanner operating notes.

## Docker Compose

For a local always-on stack:

```bash
docker compose up --build -d
```

Open:

```text
http://localhost:8080
```

Compose runs Caddy for the static dashboard and the FastAPI backend. Keep Ollama or any other model
server native on the host at `http://127.0.0.1:11434`.
