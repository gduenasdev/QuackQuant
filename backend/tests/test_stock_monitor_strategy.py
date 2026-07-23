from datetime import datetime, timedelta
from pathlib import Path

from app.services.stock_monitor import (
    EASTERN,
    Candle,
    CheckpointConfluenceStrategy,
    Quote,
    SetupSignal,
    aggregate_checkpoint_candles,
    classify_strat_scenario,
    detect_fair_value_gaps,
    detect_liquidity_sweeps,
    detect_strat_signals,
    is_regular_market_open,
    parse_symbols,
    read_journal,
    timeframe_continuity_bias,
    update_journal,
)


def test_strategy_generates_high_confidence_long_breakout() -> None:
    strategy = CheckpointConfluenceStrategy(risk_pct=0.15, target_1_pct=0.30)
    observed_at = datetime(2026, 7, 17, 11, 30, tzinfo=EASTERN)
    candles = [
        Candle("SPY", observed_at - timedelta(minutes=180), 498, 499, 497, 498.5, 100),
        Candle("SPY", observed_at - timedelta(minutes=120), 498.5, 500, 498, 499.8, 110),
        Candle("SPY", observed_at - timedelta(minutes=60), 499.8, 501, 499.5, 500.8, 120),
        Candle("SPY", observed_at, 500.8, 502, 500.7, 501.8, 200),
    ]
    levels = strategy.build_levels(candles[-1], checkpoint_minutes=60)

    signal = strategy.evaluate(Quote("SPY", 502.12, observed_at), levels, candles)

    assert signal.side == "LONG"
    assert signal.grade == "A"
    assert signal.confidence >= 80
    assert round(signal.stop_price or 0, 2) == 501.37
    assert round(signal.target_1_price or 0, 2) == 503.63


def test_detects_bullish_and_bearish_fair_value_gaps() -> None:
    observed_at = datetime(2026, 7, 17, 10, 0, tzinfo=EASTERN)
    candles = [
        Candle("SPY", observed_at, 100, 101, 99, 100.5, 100),
        Candle("SPY", observed_at + timedelta(minutes=5), 100.5, 104, 100.4, 103.8, 200),
        Candle("SPY", observed_at + timedelta(minutes=10), 103.8, 105, 102, 104.8, 180),
        Candle("SPY", observed_at + timedelta(minutes=15), 104.8, 105, 104, 104.5, 120),
        Candle("SPY", observed_at + timedelta(minutes=20), 104.5, 104.6, 98, 98.5, 250),
        Candle("SPY", observed_at + timedelta(minutes=25), 98.5, 99, 97, 97.5, 220),
    ]

    gaps = detect_fair_value_gaps(candles, min_gap_pct=0.03)

    assert any(gap.side == "bullish" and gap.lower_bound == 101 for gap in gaps)
    assert any(gap.side == "bearish" and gap.upper_bound == 104 for gap in gaps)


def test_detects_liquidity_sweeps_with_choch() -> None:
    observed_at = datetime(2026, 7, 17, 10, 0, tzinfo=EASTERN)
    bullish = [
        Candle("QQQ", observed_at, 100, 101, 99, 100.5, 100),
        Candle("QQQ", observed_at + timedelta(minutes=5), 100.5, 101.2, 99.02, 100.8, 100),
        Candle("QQQ", observed_at + timedelta(minutes=10), 100.8, 101.1, 99.01, 100.7, 100),
        Candle("QQQ", observed_at + timedelta(minutes=15), 100.7, 101.0, 99.03, 100.6, 100),
        Candle("QQQ", observed_at + timedelta(minutes=20), 100.6, 101.5, 98.7, 101.45, 220),
    ]
    bearish = [
        Candle("QQQ", observed_at, 100, 101, 99, 100.5, 100),
        Candle("QQQ", observed_at + timedelta(minutes=5), 100.5, 100.98, 98.9, 99.6, 100),
        Candle("QQQ", observed_at + timedelta(minutes=10), 99.6, 100.99, 98.8, 99.5, 100),
        Candle("QQQ", observed_at + timedelta(minutes=15), 99.5, 100.97, 98.7, 99.2, 100),
        Candle("QQQ", observed_at + timedelta(minutes=20), 99.2, 101.4, 98.4, 98.5, 220),
    ]

    bullish_sweeps = detect_liquidity_sweeps(bullish, lookback=4)
    bearish_sweeps = detect_liquidity_sweeps(bearish, lookback=4)

    assert bullish_sweeps[0].side == "bullish"
    assert bullish_sweeps[0].sweep_price == 98.7
    assert bearish_sweeps[0].side == "bearish"
    assert bearish_sweeps[0].sweep_price == 101.4


def test_classifies_strat_candle_scenarios_and_reversal() -> None:
    previous = Candle("SPY", datetime(2026, 7, 17, 9, 30, tzinfo=EASTERN), 100, 101, 99, 100)
    observed_at = datetime(2026, 7, 17, 9, 30, tzinfo=EASTERN)
    candles = [
        Candle("SPY", observed_at, 100, 101, 99, 100, 100),
        Candle("SPY", observed_at + timedelta(minutes=30), 100, 100.5, 98, 98.5, 120),
        Candle("SPY", observed_at + timedelta(minutes=60), 98.5, 100.2, 98.2, 99.5, 80),
        Candle("SPY", observed_at + timedelta(minutes=90), 99.5, 101, 98.4, 100.8, 150),
    ]

    assert classify_strat_scenario(
        Candle("SPY", observed_at + timedelta(minutes=5), 100, 100.8, 99.2, 100),
        previous,
    ) == "1"
    assert classify_strat_scenario(
        Candle("SPY", observed_at + timedelta(minutes=5), 100, 102, 99.2, 101.5),
        previous,
    ) == "2U"
    assert classify_strat_scenario(
        Candle("SPY", observed_at + timedelta(minutes=5), 100, 100.8, 98, 98.5),
        previous,
    ) == "2D"
    assert classify_strat_scenario(
        Candle("SPY", observed_at + timedelta(minutes=5), 100, 102, 98, 101),
        previous,
    ) == "3"
    assert detect_strat_signals(candles)[-1].pattern == "2-1-2 reversal"


def test_timeframe_continuity_bias() -> None:
    observed_at = datetime(2026, 7, 17, 9, 30, tzinfo=EASTERN)
    bullish = [
        Candle("SPY", observed_at, 100, 101, 99, 100.5),
        Candle("SPY", observed_at + timedelta(minutes=30), 100.5, 102, 100, 101.5),
        Candle("SPY", observed_at + timedelta(minutes=60), 101.5, 103, 101, 102.5),
    ]
    mixed = [
        Candle("SPY", observed_at, 100, 101, 99, 100.5),
        Candle("SPY", observed_at + timedelta(minutes=30), 100.5, 102, 100, 100.2),
        Candle("SPY", observed_at + timedelta(minutes=60), 100.2, 101, 99, 100.8),
    ]

    assert timeframe_continuity_bias(bullish) == "LONG"
    assert timeframe_continuity_bias(mixed) == "WAIT"


def test_journal_records_and_closes_long_target(tmp_path: Path) -> None:
    journal_path = tmp_path / "journal.csv"
    observed_at = datetime(2026, 7, 17, 10, 0, tzinfo=EASTERN)
    signal = SetupSignal(
        scanner="strat_fvg_liquidity",
        symbol="SPY",
        side="LONG",
        setup="breakout",
        confidence=85,
        grade="A",
        price=100,
        entry_price=100,
        stop_price=99,
        target_1_price=101,
        target_2_price=102,
        risk_pct=1,
        target_1_pct=1,
        target_2_pct=2,
        reward_to_risk=1,
        reasons=["test"],
        warnings=[],
        observed_at=observed_at,
    )

    first_stats = update_journal(journal_path, [signal])
    second_stats = update_journal(
        journal_path,
        [
            SetupSignal(
                **{
                    **signal.__dict__,
                    "price": 101.5,
                    "observed_at": observed_at + timedelta(minutes=30),
                }
            )
        ],
    )
    rows = read_journal(journal_path)

    assert first_stats == {"added": 1, "closed": 0, "open": 1}
    assert second_stats == {"added": 0, "closed": 1, "open": 0}
    assert rows[0]["status"] == "TARGET_1"
    assert rows[0]["result_pct"] == "1.500"


def test_aggregate_checkpoint_candles_and_market_hours() -> None:
    candles = [
        Candle("SPY", datetime(2026, 7, 17, 9, 30, tzinfo=EASTERN), 500, 501, 499, 500.5, 10),
        Candle("SPY", datetime(2026, 7, 17, 9, 35, tzinfo=EASTERN), 500.5, 502, 500, 501, 20),
        Candle("SPY", datetime(2026, 7, 17, 10, 0, tzinfo=EASTERN), 501, 503, 500, 502, 30),
    ]

    checkpoint = aggregate_checkpoint_candles(candles, checkpoint_minutes=30)

    assert len(checkpoint) == 2
    assert checkpoint[0].open == 500
    assert checkpoint[0].high == 502
    assert checkpoint[0].low == 499
    assert checkpoint[0].close == 501
    assert checkpoint[0].volume == 30
    assert parse_symbols("spy, qqq,SPY,AAPL", None) == ["AAPL", "QQQ", "SPY"]
    assert is_regular_market_open(datetime(2026, 7, 17, 9, 30, tzinfo=EASTERN))
    assert not is_regular_market_open(datetime(2026, 7, 18, 10, 0, tzinfo=EASTERN))
