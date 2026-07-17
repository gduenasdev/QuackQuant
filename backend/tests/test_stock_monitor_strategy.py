from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, time as clock_time, timedelta
from typing import Literal
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


SignalSide = Literal["LONG", "SHORT", "WAIT"]

EASTERN = ZoneInfo("America/New_York")
MARKET_OPEN = clock_time(9, 30)
MARKET_CLOSE = clock_time(16, 0)


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    observed_at: datetime


@dataclass(frozen=True)
class Candle:
    symbol: str
    opened_at: datetime
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class HourlyLevels:
    symbol: str
    hour_open: float
    previous_hour_high: float
    previous_hour_low: float
    zone_low: float
    zone_high: float
    built_at: datetime


@dataclass(frozen=True)
class PaperSignal:
    symbol: str
    side: SignalSide
    price: float
    entry_price: float | None
    stop_price: float | None
    target_price: float | None
    risk_pct: float
    target_pct: float
    reward_to_risk: float
    reason: str
    observed_at: datetime


class HourlyLevelStrategy:
    """Paper-only hourly level strategy for SPY/QQQ monitoring."""

    def __init__(
        self,
        risk_pct: float = 0.15,
        target_pct: float = 0.30,
        zone_width_pct: float = 0.03,
        breakout_buffer_pct: float = 0.02,
    ) -> None:
        self.risk_pct = risk_pct
        self.target_pct = target_pct
        self.zone_width_pct = zone_width_pct
        self.breakout_buffer_pct = breakout_buffer_pct

    @property
    def reward_to_risk(self) -> float:
        return self.target_pct / self.risk_pct

    def build_levels(self, completed_hourly_candle: Candle) -> HourlyLevels:
        zone_width = completed_hourly_candle.open * (self.zone_width_pct / 100)
        return HourlyLevels(
            symbol=completed_hourly_candle.symbol,
            hour_open=completed_hourly_candle.open,
            previous_hour_high=completed_hourly_candle.high,
            previous_hour_low=completed_hourly_candle.low,
            zone_low=completed_hourly_candle.open - zone_width,
            zone_high=completed_hourly_candle.open + zone_width,
            built_at=completed_hourly_candle.opened_at,
        )

    def evaluate(self, quote: Quote, levels: HourlyLevels) -> PaperSignal:
        long_breakout = levels.previous_hour_high * (1 + self.breakout_buffer_pct / 100)
        short_breakdown = levels.previous_hour_low * (1 - self.breakout_buffer_pct / 100)

        if quote.price >= long_breakout:
            return self._trade_signal(
                quote=quote,
                side="LONG",
                reason=(
                    f"break above prior hourly high {levels.previous_hour_high:.2f}; "
                    f"hour open zone {levels.zone_low:.2f}-{levels.zone_high:.2f}"
                ),
            )

        if quote.price <= short_breakdown:
            return self._trade_signal(
                quote=quote,
                side="SHORT",
                reason=(
                    f"break below prior hourly low {levels.previous_hour_low:.2f}; "
                    f"hour open zone {levels.zone_low:.2f}-{levels.zone_high:.2f}"
                ),
            )

        if levels.zone_low <= quote.price <= levels.zone_high:
            reason = (
                f"watch retest of hourly open {levels.hour_open:.2f}; "
                f"zone {levels.zone_low:.2f}-{levels.zone_high:.2f}"
            )
        else:
            reason = (
                f"inside prior hourly range {levels.previous_hour_low:.2f}-"
                f"{levels.previous_hour_high:.2f}; no entry"
            )

        return PaperSignal(
            symbol=quote.symbol,
            side="WAIT",
            price=quote.price,
            entry_price=None,
            stop_price=None,
            target_price=None,
            risk_pct=self.risk_pct,
            target_pct=self.target_pct,
            reward_to_risk=self.reward_to_risk,
            reason=reason,
            observed_at=quote.observed_at,
        )

    def _trade_signal(self, quote: Quote, side: Literal["LONG", "SHORT"], reason: str) -> PaperSignal:
        if side == "LONG":
            stop_price = quote.price * (1 - self.risk_pct / 100)
            target_price = quote.price * (1 + self.target_pct / 100)
        else:
            stop_price = quote.price * (1 + self.risk_pct / 100)
            target_price = quote.price * (1 - self.target_pct / 100)

        return PaperSignal(
            symbol=quote.symbol,
            side=side,
            price=quote.price,
            entry_price=quote.price,
            stop_price=stop_price,
            target_price=target_price,
            risk_pct=self.risk_pct,
            target_pct=self.target_pct,
            reward_to_risk=self.reward_to_risk,
            reason=reason,
            observed_at=quote.observed_at,
        )


def is_regular_market_open(now: datetime) -> bool:
    eastern_now = now.astimezone(EASTERN)
    if eastern_now.weekday() >= 5:
        return False

    return MARKET_OPEN <= eastern_now.time() <= MARKET_CLOSE


def fetch_yahoo_quotes(symbols: list[str]) -> list[Quote]:
    query = urlencode({"symbols": ",".join(symbols)})
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?{query}"
    request = Request(url, headers={"User-Agent": "QuackQuant paper monitor"})

    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))

    observed_at = datetime.now(tz=EASTERN)
    quotes: list[Quote] = []
    for item in payload["quoteResponse"]["result"]:
        price = item.get("regularMarketPrice")
        symbol = item.get("symbol")
        if symbol and price is not None:
            quotes.append(Quote(symbol=symbol, price=float(price), observed_at=observed_at))

    return quotes


def fetch_yahoo_5m_candles(symbol: str) -> list[Candle]:
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        "?range=2d&interval=5m&includePrePost=false"
    )
    request = Request(url, headers={"User-Agent": "QuackQuant paper monitor"})

    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))

    result = payload["chart"]["result"][0]
    timestamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]

    candles: list[Candle] = []
    for index, timestamp in enumerate(timestamps):
        opened_at = datetime.fromtimestamp(timestamp, tz=EASTERN)
        candle_open = quote["open"][index]
        high = quote["high"][index]
        low = quote["low"][index]
        close = quote["close"][index]
        if None in (candle_open, high, low, close):
            continue
        candles.append(
            Candle(
                symbol=symbol,
                opened_at=opened_at,
                open=float(candle_open),
                high=float(high),
                low=float(low),
                close=float(close),
            )
        )

    return candles


def aggregate_hourly_candles(candles: list[Candle]) -> list[Candle]:
    buckets: dict[datetime, list[Candle]] = {}
    for candle in candles:
        if not is_regular_market_open(candle.opened_at):
            continue

        market_open = candle.opened_at.replace(hour=9, minute=30, second=0, microsecond=0)
        minutes_from_open = int((candle.opened_at - market_open).total_seconds() // 60)
        if minutes_from_open < 0:
            continue

        bucket_start = market_open + timedelta(hours=minutes_from_open // 60)
        buckets.setdefault(bucket_start, []).append(candle)

    hourly: list[Candle] = []
    for opened_at, bucket_candles in sorted(buckets.items()):
        hourly.append(
            Candle(
                symbol=bucket_candles[0].symbol,
                opened_at=opened_at,
                open=bucket_candles[0].open,
                high=max(candle.high for candle in bucket_candles),
                low=min(candle.low for candle in bucket_candles),
                close=bucket_candles[-1].close,
            )
        )

    return hourly


def run_live_monitor() -> None:
    symbols = [
        symbol.strip().upper()
        for symbol in os.getenv("QUACKQUANT_SYMBOLS", "SPY,QQQ").split(",")
        if symbol.strip()
    ]
    poll_seconds = int(os.getenv("QUACKQUANT_POLL_SECONDS", "300"))
    strategy = HourlyLevelStrategy(
        risk_pct=float(os.getenv("QUACKQUANT_RISK_PCT", "0.15")),
        target_pct=float(os.getenv("QUACKQUANT_TARGET_PCT", "0.30")),
        zone_width_pct=float(os.getenv("QUACKQUANT_ZONE_WIDTH_PCT", "0.03")),
        breakout_buffer_pct=float(os.getenv("QUACKQUANT_BREAKOUT_BUFFER_PCT", "0.02")),
    )

    print("QuackQuant SPY/QQQ hourly-level paper monitor")
    print(
        f"symbols={symbols} poll_seconds={poll_seconds} risk_pct={strategy.risk_pct} "
        f"target_pct={strategy.target_pct} reward_to_risk={strategy.reward_to_risk:.2f}"
    )
    print("This script prints paper signals only. It does not place trades.")

    while True:
        now = datetime.now(tz=EASTERN)
        if not is_regular_market_open(now):
            print(f"{now.isoformat()} market not open; waiting {poll_seconds}s")
            time.sleep(poll_seconds)
            continue

        quotes_by_symbol = {quote.symbol: quote for quote in fetch_yahoo_quotes(symbols)}
        for symbol in symbols:
            quote = quotes_by_symbol.get(symbol)
            hourly_candles = aggregate_hourly_candles(fetch_yahoo_5m_candles(symbol))
            if quote is None or not hourly_candles:
                print(f"{now.isoformat()} {symbol:<5} missing quote or hourly candle data")
                continue

            levels = strategy.build_levels(hourly_candles[-1])
            signal = strategy.evaluate(quote, levels)
            entry = f"{signal.entry_price:.2f}" if signal.entry_price else "-"
            stop = f"{signal.stop_price:.2f}" if signal.stop_price else "-"
            target = f"{signal.target_price:.2f}" if signal.target_price else "-"
            print(
                f"{signal.observed_at.isoformat()} {signal.symbol:<5} "
                f"${signal.price:>9.2f} {signal.side:<5} "
                f"entry={entry:<8} stop={stop:<8} target={target:<8} "
                f"R:R={signal.reward_to_risk:.2f} {signal.reason}"
            )

        time.sleep(poll_seconds)


def test_hourly_level_strategy_generates_long_breakout() -> None:
    strategy = HourlyLevelStrategy(risk_pct=0.15, target_pct=0.30, breakout_buffer_pct=0.02)
    observed_at = datetime(2026, 7, 17, 9, 31, tzinfo=EASTERN)
    levels = strategy.build_levels(
        Candle("SPY", observed_at, open=500.00, high=501.00, low=499.00, close=500.50)
    )

    signal = strategy.evaluate(Quote("SPY", 501.11, observed_at), levels)

    assert signal.side == "LONG"
    assert signal.entry_price == 501.11
    assert round(signal.stop_price or 0, 2) == 500.36
    assert round(signal.target_price or 0, 2) == 502.61


def test_hourly_level_strategy_generates_short_breakdown() -> None:
    strategy = HourlyLevelStrategy(risk_pct=0.15, target_pct=0.30, breakout_buffer_pct=0.02)
    observed_at = datetime(2026, 7, 17, 9, 31, tzinfo=EASTERN)
    levels = strategy.build_levels(
        Candle("QQQ", observed_at, open=400.00, high=401.00, low=399.00, close=399.50)
    )

    signal = strategy.evaluate(Quote("QQQ", 398.90, observed_at), levels)

    assert signal.side == "SHORT"
    assert signal.entry_price == 398.90
    assert round(signal.stop_price or 0, 2) == 399.50
    assert round(signal.target_price or 0, 2) == 397.70


def test_hourly_level_strategy_waits_inside_open_zone() -> None:
    strategy = HourlyLevelStrategy(zone_width_pct=0.03)
    observed_at = datetime(2026, 7, 17, 9, 31, tzinfo=EASTERN)
    levels = strategy.build_levels(
        Candle("SPY", observed_at, open=500.00, high=501.00, low=499.00, close=500.50)
    )

    signal = strategy.evaluate(Quote("SPY", 500.05, observed_at), levels)

    assert signal.side == "WAIT"
    assert signal.entry_price is None
    assert "watch retest" in signal.reason


def test_aggregate_hourly_candles_from_5m_data() -> None:
    candles = [
        Candle("SPY", datetime(2026, 7, 17, 9, 30, tzinfo=EASTERN), 500, 501, 499, 500.5),
        Candle("SPY", datetime(2026, 7, 17, 9, 35, tzinfo=EASTERN), 500.5, 502, 500, 501),
        Candle("SPY", datetime(2026, 7, 17, 10, 30, tzinfo=EASTERN), 501, 503, 500, 502),
    ]

    hourly = aggregate_hourly_candles(candles)

    assert len(hourly) == 2
    assert hourly[0].open == 500
    assert hourly[0].high == 502
    assert hourly[0].low == 499
    assert hourly[0].close == 501


def test_regular_market_open_window() -> None:
    assert is_regular_market_open(datetime(2026, 7, 17, 9, 30, tzinfo=EASTERN))
    assert is_regular_market_open(datetime(2026, 7, 17, 16, 0, tzinfo=EASTERN))
    assert not is_regular_market_open(datetime(2026, 7, 17, 8, 0, tzinfo=EASTERN))
    assert not is_regular_market_open(datetime(2026, 7, 18, 10, 0, tzinfo=EASTERN))


if __name__ == "__main__":
    run_live_monitor()
