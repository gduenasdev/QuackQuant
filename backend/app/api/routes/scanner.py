from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.services.stock_monitor import (
    DEFAULT_JOURNAL_PATH,
    CheckpointConfluenceStrategy,
    ScannerName,
    read_journal,
    run_orb_once,
    run_once,
    summarize_journal,
    summarize_journal_performance,
    update_journal,
)

router = APIRouter()

DataSource = Literal["yahoo_candles", "robinhood_mcp"]


@router.get("/signals")
def scanner_signals(
    symbols: str = Query(default="SPY,QQQ", description="Comma-separated ticker symbols"),
    checkpoint_minutes: int = Query(default=30),
    scanner: ScannerName = Query(default="strat_fvg_liquidity"),
    data_source: DataSource = Query(default="yahoo_candles"),
    record: bool = Query(default=True, description="Record LONG/SHORT calls to paper journal"),
) -> dict[str, object]:
    if checkpoint_minutes not in {30, 60}:
        raise HTTPException(status_code=400, detail="checkpoint_minutes must be 30 or 60")
    if data_source == "robinhood_mcp":
        raise HTTPException(
            status_code=501,
            detail=(
                "Robinhood MCP is the intended source of truth, but its tools are not exposed "
                "to this backend runtime yet. Keep paper scanning on yahoo_candles until a "
                "Robinhood data adapter can call get_scanner_filter_specs and supported "
                "Robinhood market/watchlist/option-chain tools."
            ),
        )

    symbol_list = [symbol.strip().upper() for symbol in symbols.split(",") if symbol.strip()]
    if scanner == "orb_vwap_pullback" and symbols == "SPY,QQQ":
        symbol_list = ["SPY", "QQQ", "NVDA", "TSLA", "AMD", "META", "AMZN", "AAPL", "MSFT", "GOOGL"]

    if scanner == "orb_vwap_pullback":
        signals = run_orb_once(symbol_list)
    else:
        strategy = CheckpointConfluenceStrategy()
        signals = run_once(
            symbols=symbol_list,
            checkpoint_minutes=checkpoint_minutes,
            strategy=strategy,
        )
    journal_stats = update_journal(DEFAULT_JOURNAL_PATH, signals) if record else None

    return {
        "symbols": symbol_list,
        "checkpoint_minutes": checkpoint_minutes,
        "scanner": scanner,
        "data_source": data_source,
        "recorded": record,
        "journal": journal_stats,
        "signals": [asdict(signal) for signal in signals],
    }


@router.get("/data-sources")
def scanner_data_sources() -> dict[str, object]:
    return {
        "default": "yahoo_candles",
        "sources": [
            {
                "id": "yahoo_candles",
                "label": "Yahoo candles",
                "status": "available",
                "trading_enabled": False,
            },
            {
                "id": "robinhood_mcp",
                "label": "Robinhood MCP",
                "status": "not_exposed_to_backend",
                "trading_enabled": False,
                "required_first_call": "get_scanner_filter_specs",
            },
        ],
    }


@router.get("/journal")
def scanner_journal() -> dict[str, object]:
    return {
        "path": str(DEFAULT_JOURNAL_PATH),
        "rows": read_journal(DEFAULT_JOURNAL_PATH),
    }


@router.get("/journal/summary")
def scanner_journal_summary() -> dict[str, str]:
    return {"summary": summarize_journal(DEFAULT_JOURNAL_PATH)}


@router.get("/journal/performance")
def scanner_journal_performance() -> dict[str, object]:
    return {"performance": summarize_journal_performance(DEFAULT_JOURNAL_PATH)}
