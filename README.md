# QuantQuack

Demonstration of quantitative analysis using AI agents.

## Website

The landing page is static. From the repository root, preview it with:

```bash
python3 -m http.server 8000
```

Then open <http://127.0.0.1:8000>.

## API scaffold

The FastAPI scaffold lives in `backend/`. Health checks work; product endpoints intentionally
return HTTP `501 Not Implemented` until the security and persistence TODOs in each route are done.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
uvicorn app.main:app --reload --port 8001
```

API documentation is available at <http://127.0.0.1:8001/docs>. See
[`backend/IMPLEMENTATION_TODO.md`](backend/IMPLEMENTATION_TODO.md) for the recommended build order.

## Trading research

Read [`docs/TRADING_RESEARCH.md`](docs/TRADING_RESEARCH.md) before implementing backtests, scanners,
strategy logic, or broker execution. It covers realistic objective-setting, multi-symbol research,
backtesting, liquidity-sweep hypotheses, training stages, risk controls, and the current U.S.
intraday-margin transition.
