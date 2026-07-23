from datetime import datetime, timedelta
from dataclasses import replace

from app.services.stock_monitor import (
    EASTERN,
    Candle,
    OpeningRangeBreakoutStrategy,
    has_open_trade,
    signal_to_journal_row,
)


def session_candle(
    minutes_after_open: int,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float,
) -> Candle:
    return Candle(
        symbol="SPY",
        opened_at=datetime(2026, 7, 21, 9, 30, tzinfo=EASTERN) + timedelta(minutes=minutes_after_open),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def test_orb_vwap_pullback_generates_single_long_candidate() -> None:
    strategy = OpeningRangeBreakoutStrategy()
    candles = [
        session_candle(0, 99.8, 100.3, 99.7, 100.0, 100),
        session_candle(5, 100.0, 100.4, 99.9, 100.2, 100),
        session_candle(10, 100.2, 100.6, 100.1, 100.4, 100),
        session_candle(15, 100.4, 101.7, 100.4, 101.5, 400),
        session_candle(20, 101.5, 101.6, 100.9, 101.0, 150),
        session_candle(25, 101.0, 101.4, 100.8, 101.2, 120),
        session_candle(30, 101.2, 101.5, 100.9, 101.3, 100),
        session_candle(35, 101.3, 102.6, 101.2, 102.4, 350),
    ]

    signal = strategy.evaluate_symbol("SPY", candles, market_bias="LONG")

    assert signal.scanner == "orb_vwap_pullback"
    assert signal.side == "LONG"
    assert signal.confidence >= 80
    assert signal.entry_price == 102.4
    assert signal.stop_price is not None
    assert signal.target_1_price is not None


def test_orb_universe_selects_zero_or_one_actionable_call() -> None:
    strategy = OpeningRangeBreakoutStrategy()
    strong = [
        session_candle(0, 99.8, 100.3, 99.7, 100.0, 100),
        session_candle(5, 100.0, 100.4, 99.9, 100.2, 100),
        session_candle(10, 100.2, 100.6, 100.1, 100.4, 100),
        session_candle(15, 100.4, 101.7, 100.4, 101.5, 400),
        session_candle(20, 101.5, 101.6, 100.9, 101.0, 150),
        session_candle(25, 101.0, 101.4, 100.8, 101.2, 120),
        session_candle(30, 101.2, 101.5, 100.9, 101.3, 100),
        session_candle(35, 101.3, 102.6, 101.2, 102.4, 350),
    ]

    signals = strategy.evaluate_universe({"SPY": strong, "QQQ": strong})

    assert sum(signal.side != "WAIT" for signal in signals) <= 1


def test_journal_duplicate_check_is_scanner_specific() -> None:
    strategy = OpeningRangeBreakoutStrategy()
    orb_signal = strategy._trade(
        "LONG",
        "SPY",
        [
            session_candle(0, 100, 101, 99, 100, 100),
            session_candle(5, 100, 102, 99, 101, 100),
        ],
        1,
        80,
        [],
        [],
    )
    strat_signal = replace(orb_signal, scanner="strat_fvg_liquidity")
    row = signal_to_journal_row(orb_signal)

    assert not has_open_trade([row], strat_signal)
