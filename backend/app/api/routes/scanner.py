from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, Query

from app.services.stock_monitor import (
    DEFAULT_JOURNAL_PATH,
    CheckpointConfluenceStrategy,
    read_journal,
    run_once,
    summarize_journal,
    update_journal,
)

router = APIRouter()


@router.get("/signals")
def scanner_signals(
    symbols: str = Query(default="SPY,QQQ", description="Comma-separated ticker symbols"),
    checkpoint_minutes: Literal[30, 60] = Query(default=30),
    record: bool = Query(default=True, description="Record LONG/SHORT calls to paper journal"),
) -> dict[str, object]:
    symbol_list = [symbol.strip().upper() for symbol in symbols.split(",") if symbol.strip()]
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
        "recorded": record,
        "journal": journal_stats,
        "signals": [asdict(signal) for signal in signals],
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
