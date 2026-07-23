from __future__ import annotations

import argparse
import csv
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, time as clock_time, timedelta
from pathlib import Path
from statistics import mean
from typing import Literal
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


SignalSide = Literal["LONG", "SHORT", "WAIT"]
SetupName = Literal["continuation", "breakout", "rejection", "chop", "insufficient_data"]
PatternSide = Literal["bullish", "bearish"]
StratScenario = Literal["1", "2U", "2D", "3"]
ScannerName = Literal["strat_fvg_liquidity", "orb_vwap_pullback"]

EASTERN = ZoneInfo("America/New_York")
MARKET_OPEN = clock_time(9, 30)
MARKET_CLOSE = clock_time(16, 0)
DEFAULT_JOURNAL_PATH = Path(__file__).with_name("stock_monitor_journal.csv")
JOURNAL_COOLDOWN_MINUTES = 60
JOURNAL_FIELDS = [
    "id",
    "scanner",
    "opened_at",
    "closed_at",
    "symbol",
    "side",
    "setup",
    "grade",
    "confidence",
    "entry_price",
    "stop_price",
    "target_1_price",
    "target_2_price",
    "last_price",
    "status",
    "result_pct",
    "reasons",
]


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
    volume: float = 0


@dataclass(frozen=True)
class KeyLevels:
    symbol: str
    checkpoint_minutes: int
    current_open: float
    previous_high: float
    previous_low: float
    zone_low: float
    zone_high: float
    built_at: datetime


@dataclass(frozen=True)
class FairValueGap:
    symbol: str
    side: PatternSide
    lower_bound: float
    upper_bound: float
    formed_at: datetime
    mitigated: bool


@dataclass(frozen=True)
class LiquiditySweep:
    symbol: str
    side: PatternSide
    liquidity_level: float
    sweep_price: float
    choch_level: float
    confirmed_at: datetime


@dataclass(frozen=True)
class StratSignal:
    symbol: str
    side: PatternSide
    pattern: str
    trigger_price: float
    stop_price: float
    formed_at: datetime


@dataclass(frozen=True)
class SetupSignal:
    scanner: ScannerName
    symbol: str
    side: SignalSide
    setup: SetupName
    confidence: int
    grade: str
    price: float
    entry_price: float | None
    stop_price: float | None
    target_1_price: float | None
    target_2_price: float | None
    risk_pct: float
    target_1_pct: float
    target_2_pct: float
    reward_to_risk: float
    reasons: list[str]
    warnings: list[str]
    observed_at: datetime


class CheckpointConfluenceStrategy:
    """Paper-only setup scanner using hourly-style levels plus confluence scoring."""

    def __init__(
        self,
        risk_pct: float = 0.15,
        target_1_pct: float = 0.30,
        target_2_pct: float = 0.45,
        zone_width_pct: float = 0.03,
        breakout_buffer_pct: float = 0.02,
        min_trade_score: int = 65,
        strong_trade_score: int = 80,
    ) -> None:
        self.risk_pct = risk_pct
        self.target_1_pct = target_1_pct
        self.target_2_pct = target_2_pct
        self.zone_width_pct = zone_width_pct
        self.breakout_buffer_pct = breakout_buffer_pct
        self.min_trade_score = min_trade_score
        self.strong_trade_score = strong_trade_score

    @property
    def reward_to_risk(self) -> float:
        return self.target_1_pct / self.risk_pct

    def build_levels(self, completed_checkpoint_candle: Candle, checkpoint_minutes: int) -> KeyLevels:
        zone_width = completed_checkpoint_candle.open * (self.zone_width_pct / 100)
        return KeyLevels(
            symbol=completed_checkpoint_candle.symbol,
            checkpoint_minutes=checkpoint_minutes,
            current_open=completed_checkpoint_candle.open,
            previous_high=completed_checkpoint_candle.high,
            previous_low=completed_checkpoint_candle.low,
            zone_low=completed_checkpoint_candle.open - zone_width,
            zone_high=completed_checkpoint_candle.open + zone_width,
            built_at=completed_checkpoint_candle.opened_at,
        )

    def evaluate(
        self,
        quote: Quote,
        levels: KeyLevels,
        checkpoint_candles: list[Candle],
        market_bias: SignalSide = "WAIT",
    ) -> SetupSignal:
        if len(checkpoint_candles) < 4:
            return self._wait_signal(
                quote=quote,
                levels=levels,
                setup="insufficient_data",
                confidence=0,
                reasons=["need at least 4 completed checkpoint candles"],
                warnings=["wait for more 30m/60m structure before trusting signals"],
            )

        pattern_reasons = describe_active_patterns(checkpoint_candles)
        long_score, long_reasons, long_warnings = self._score_side(
            side="LONG",
            quote=quote,
            levels=levels,
            checkpoint_candles=checkpoint_candles,
            market_bias=market_bias,
        )
        short_score, short_reasons, short_warnings = self._score_side(
            side="SHORT",
            quote=quote,
            levels=levels,
            checkpoint_candles=checkpoint_candles,
            market_bias=market_bias,
        )

        if max(long_score, short_score) < self.min_trade_score:
            setup: SetupName = "rejection" if levels.zone_low <= quote.price <= levels.zone_high else "chop"
            reasons = [
                f"no side reached {self.min_trade_score}+ confidence",
                f"long_score={long_score}",
                f"short_score={short_score}",
                f"checkpoint range {levels.previous_low:.2f}-{levels.previous_high:.2f}",
            ] + pattern_reasons
            warnings = ["no paper entry; wait for cleaner confluence"]
            return self._wait_signal(
                quote=quote,
                levels=levels,
                setup=setup,
                confidence=max(long_score, short_score),
                reasons=reasons,
                warnings=warnings,
            )

        if long_score >= short_score:
            setup = "breakout" if quote.price > levels.previous_high else "continuation"
            return self._trade_signal(
                quote=quote,
                side="LONG",
                setup=setup,
                confidence=long_score,
                reasons=unique_reasons(long_reasons + pattern_reasons),
                warnings=long_warnings,
            )

        setup = "breakout" if quote.price < levels.previous_low else "continuation"
        return self._trade_signal(
            quote=quote,
            side="SHORT",
            setup=setup,
            confidence=short_score,
            reasons=unique_reasons(short_reasons + pattern_reasons),
            warnings=short_warnings,
        )

    def _score_side(
        self,
        side: Literal["LONG", "SHORT"],
        quote: Quote,
        levels: KeyLevels,
        checkpoint_candles: list[Candle],
        market_bias: SignalSide,
    ) -> tuple[int, list[str], list[str]]:
        recent = checkpoint_candles[-1]
        previous = checkpoint_candles[-2]
        closes = [candle.close for candle in checkpoint_candles]
        volumes = [candle.volume for candle in checkpoint_candles if candle.volume > 0]
        avg_volume = mean(volumes[-20:]) if volumes else 0
        recent_volume = recent.volume
        ema_fast = ema(closes, 8)
        ema_slow = ema(closes, 21)
        fair_value_gaps = detect_fair_value_gaps(checkpoint_candles)
        liquidity_sweeps = detect_liquidity_sweeps(checkpoint_candles)
        bullish_fvg = latest_active_gap(fair_value_gaps, "bullish")
        bearish_fvg = latest_active_gap(fair_value_gaps, "bearish")
        bullish_sweep = latest_sweep(liquidity_sweeps, "bullish")
        bearish_sweep = latest_sweep(liquidity_sweeps, "bearish")
        strat_signals = detect_strat_signals(checkpoint_candles)
        bullish_strat = latest_strat_signal(strat_signals, "bullish")
        bearish_strat = latest_strat_signal(strat_signals, "bearish")
        tfc_bias = timeframe_continuity_bias(checkpoint_candles)

        score = 0
        reasons: list[str] = []
        warnings: list[str] = []

        if side == "LONG":
            breakout = levels.previous_high * (1 + self.breakout_buffer_pct / 100)
            above_level = quote.price >= breakout
            above_open = quote.price > levels.current_open
            trend_aligned = ema_fast > ema_slow and recent.close > ema_fast
            structure_aligned = recent.high > previous.high and recent.low >= previous.low
            volume_confirmed = avg_volume > 0 and recent_volume >= avg_volume
            market_aligned = market_bias in ("LONG", "WAIT")
            fvg_aligned = bullish_fvg is not None and quote.price >= bullish_fvg.upper_bound
            sweep_aligned = bullish_sweep is not None
            strat_aligned = bullish_strat is not None and quote.price >= bullish_strat.trigger_price
            tfc_aligned = tfc_bias in ("LONG", "WAIT")

            checks = [
                (above_level, 25, f"price broke above {levels.checkpoint_minutes}m high"),
                (above_open, 15, "price is above checkpoint open"),
                (trend_aligned, 20, "fast EMA is above slow EMA"),
                (structure_aligned, 15, "higher-high / higher-low structure"),
                (volume_confirmed, 15, "volume is at or above recent average"),
                (market_aligned, 10, "market bias does not fight long setup"),
                (fvg_aligned, 10, "bullish FVG remains active below price"),
                (sweep_aligned, 15, "bullish liquidity sweep with CHOCH confirmed"),
                (strat_aligned, 20, f"bullish Strat signal in-force: {bullish_strat.pattern if bullish_strat else ''}"),
                (tfc_aligned, 10, "checkpoint timeframe continuity supports long or is neutral"),
            ]
        else:
            breakdown = levels.previous_low * (1 - self.breakout_buffer_pct / 100)
            below_level = quote.price <= breakdown
            below_open = quote.price < levels.current_open
            trend_aligned = ema_fast < ema_slow and recent.close < ema_fast
            structure_aligned = recent.low < previous.low and recent.high <= previous.high
            volume_confirmed = avg_volume > 0 and recent_volume >= avg_volume
            market_aligned = market_bias in ("SHORT", "WAIT")
            fvg_aligned = bearish_fvg is not None and quote.price <= bearish_fvg.lower_bound
            sweep_aligned = bearish_sweep is not None
            strat_aligned = bearish_strat is not None and quote.price <= bearish_strat.trigger_price
            tfc_aligned = tfc_bias in ("SHORT", "WAIT")

            checks = [
                (below_level, 25, f"price broke below {levels.checkpoint_minutes}m low"),
                (below_open, 15, "price is below checkpoint open"),
                (trend_aligned, 20, "fast EMA is below slow EMA"),
                (structure_aligned, 15, "lower-low / lower-high structure"),
                (volume_confirmed, 15, "volume is at or above recent average"),
                (market_aligned, 10, "market bias does not fight short setup"),
                (fvg_aligned, 10, "bearish FVG remains active above price"),
                (sweep_aligned, 15, "bearish liquidity sweep with CHOCH confirmed"),
                (strat_aligned, 20, f"bearish Strat signal in-force: {bearish_strat.pattern if bearish_strat else ''}"),
                (tfc_aligned, 10, "checkpoint timeframe continuity supports short or is neutral"),
            ]

        for passed, points, reason in checks:
            if passed:
                score += points
                reasons.append(f"+{points} {reason}")

        if levels.zone_low <= quote.price <= levels.zone_high:
            score -= 20
            warnings.append("-20 price is inside checkpoint open zone")

        if recent.high == recent.low:
            score -= 20
            warnings.append("-20 latest checkpoint candle has no usable range")

        return max(0, min(score, 100)), reasons, warnings

    def _trade_signal(
        self,
        quote: Quote,
        side: Literal["LONG", "SHORT"],
        setup: SetupName,
        confidence: int,
        reasons: list[str],
        warnings: list[str],
    ) -> SetupSignal:
        if side == "LONG":
            stop_price = quote.price * (1 - self.risk_pct / 100)
            target_1_price = quote.price * (1 + self.target_1_pct / 100)
            target_2_price = quote.price * (1 + self.target_2_pct / 100)
        else:
            stop_price = quote.price * (1 + self.risk_pct / 100)
            target_1_price = quote.price * (1 - self.target_1_pct / 100)
            target_2_price = quote.price * (1 - self.target_2_pct / 100)

        return SetupSignal(
            scanner="strat_fvg_liquidity",
            symbol=quote.symbol,
            side=side,
            setup=setup,
            confidence=confidence,
            grade=self._grade(confidence),
            price=quote.price,
            entry_price=quote.price,
            stop_price=stop_price,
            target_1_price=target_1_price,
            target_2_price=target_2_price,
            risk_pct=self.risk_pct,
            target_1_pct=self.target_1_pct,
            target_2_pct=self.target_2_pct,
            reward_to_risk=self.reward_to_risk,
            reasons=reasons,
            warnings=warnings,
            observed_at=quote.observed_at,
        )

    def _wait_signal(
        self,
        quote: Quote,
        levels: KeyLevels,
        setup: SetupName,
        confidence: int,
        reasons: list[str],
        warnings: list[str],
    ) -> SetupSignal:
        return SetupSignal(
            scanner="strat_fvg_liquidity",
            symbol=quote.symbol,
            side="WAIT",
            setup=setup,
            confidence=confidence,
            grade=self._grade(confidence),
            price=quote.price,
            entry_price=None,
            stop_price=None,
            target_1_price=None,
            target_2_price=None,
            risk_pct=self.risk_pct,
            target_1_pct=self.target_1_pct,
            target_2_pct=self.target_2_pct,
            reward_to_risk=self.reward_to_risk,
            reasons=reasons
            + [
                f"open zone {levels.zone_low:.2f}-{levels.zone_high:.2f}",
                f"checkpoint high/low {levels.previous_high:.2f}/{levels.previous_low:.2f}",
            ],
            warnings=warnings,
            observed_at=quote.observed_at,
        )

    def _grade(self, confidence: int) -> str:
        if confidence >= self.strong_trade_score:
            return "A"
        if confidence >= self.min_trade_score:
            return "B"
        if confidence >= 50:
            return "WATCH"
        return "NO_TRADE"


class OpeningRangeBreakoutStrategy:
    """Paper-only 15-minute opening range breakout with VWAP pullback scanner."""

    tier_1 = {"SPY", "QQQ"}
    tier_2 = {"NVDA", "TSLA", "AMD", "META", "AMZN"}
    tier_3 = {"AAPL", "MSFT", "GOOGL"}

    def __init__(
        self,
        min_score: int = 80,
        target_reward_risk: float = 1.5,
        risk_atr_multiple: float = 0.6,
        strong_volume_ratio: float = 1.5,
    ) -> None:
        self.min_score = min_score
        self.target_reward_risk = target_reward_risk
        self.risk_atr_multiple = risk_atr_multiple
        self.strong_volume_ratio = strong_volume_ratio

    def evaluate_universe(self, candles_by_symbol: dict[str, list[Candle]]) -> list[SetupSignal]:
        market_bias = self._market_bias(candles_by_symbol)
        candidates: list[SetupSignal] = []

        for symbol, candles in candles_by_symbol.items():
            signal = self.evaluate_symbol(symbol, candles, market_bias)
            candidates.append(signal)

        actionable = [
            signal for signal in candidates if signal.side != "WAIT" and signal.confidence >= self.min_score
        ]
        if not actionable:
            return sorted(candidates, key=lambda item: item.confidence, reverse=True)

        winner = sorted(actionable, key=lambda item: item.confidence, reverse=True)[0]
        return [
            winner,
            *[
                self._stand_down(signal, f"ranked below selected candidate {winner.symbol}")
                if signal.side != "WAIT" and signal.symbol != winner.symbol
                else signal
                for signal in candidates
                if signal.symbol != winner.symbol
            ],
        ]

    def evaluate_symbol(
        self,
        symbol: str,
        candles: list[Candle],
        market_bias: SignalSide,
    ) -> SetupSignal:
        session = latest_regular_session(candles)
        if len(session) < 6:
            return self._wait(symbol, candles, 0, ["not enough regular-session candles"], [])

        latest = session[-1]
        if not is_entry_window(latest.opened_at):
            return self._wait(
                symbol,
                session,
                0,
                ["outside ORB entry windows"],
                ["entries allowed 9:45-11:15 ET and 13:30-15:30 ET"],
            )

        opening_range = opening_range_candles(session)
        if len(opening_range) < 3:
            return self._wait(symbol, session, 0, ["15-minute opening range not complete"], [])

        or_high = max(candle.high for candle in opening_range)
        or_low = min(candle.low for candle in opening_range)
        vwap_value = vwap(session)
        ema_9 = ema([candle.close for candle in session], 9)
        ema_20 = ema([candle.close for candle in session], 20)
        atr_5m = average_true_range(session, 14)
        recent_volumes = [candle.volume for candle in session[-20:] if candle.volume > 0]
        avg_volume = mean(recent_volumes) if recent_volumes else 0
        volume_ratio = latest.volume / avg_volume if avg_volume else 0
        previous_high, previous_low, previous_close = previous_session_levels(candles, latest.opened_at)
        daily_move_pct = abs(((latest.close - previous_close) / previous_close) * 100) if previous_close else 0

        long_score, long_reasons, long_warnings = self._score_side(
            side="LONG",
            symbol=symbol,
            session=session,
            or_high=or_high,
            or_low=or_low,
            vwap_value=vwap_value,
            ema_9=ema_9,
            ema_20=ema_20,
            atr_5m=atr_5m,
            previous_high=previous_high,
            previous_low=previous_low,
            daily_move_pct=daily_move_pct,
            volume_ratio=volume_ratio,
            market_bias=market_bias,
        )
        short_score, short_reasons, short_warnings = self._score_side(
            side="SHORT",
            symbol=symbol,
            session=session,
            or_high=or_high,
            or_low=or_low,
            vwap_value=vwap_value,
            ema_9=ema_9,
            ema_20=ema_20,
            atr_5m=atr_5m,
            previous_high=previous_high,
            previous_low=previous_low,
            daily_move_pct=daily_move_pct,
            volume_ratio=volume_ratio,
            market_bias=market_bias,
        )

        if max(long_score, short_score) < self.min_score:
            return self._wait(
                symbol,
                session,
                max(long_score, short_score),
                [
                    f"ORB/VWAP setup below {self.min_score} threshold",
                    f"long_score={long_score}",
                    f"short_score={short_score}",
                    f"OR={or_low:.2f}-{or_high:.2f}",
                ],
                ["paper-only; Robinhood option-chain validation is not connected yet"],
            )

        if long_score >= short_score:
            return self._trade("LONG", symbol, session, atr_5m, long_score, long_reasons, long_warnings)

        return self._trade("SHORT", symbol, session, atr_5m, short_score, short_reasons, short_warnings)

    def _market_bias(self, candles_by_symbol: dict[str, list[Candle]]) -> SignalSide:
        votes: list[SignalSide] = []
        for symbol in ("SPY", "QQQ"):
            session = latest_regular_session(candles_by_symbol.get(symbol, []))
            if len(session) < 3:
                continue

            latest = session[-1]
            vwap_value = vwap(session)
            closes = [candle.close for candle in session]
            if latest.close > vwap_value and ema(closes, 9) > ema(closes, 20):
                votes.append("LONG")
            elif latest.close < vwap_value and ema(closes, 9) < ema(closes, 20):
                votes.append("SHORT")

        if votes.count("LONG") == 2:
            return "LONG"
        if votes.count("SHORT") == 2:
            return "SHORT"
        return "WAIT"

    def _score_side(
        self,
        side: Literal["LONG", "SHORT"],
        symbol: str,
        session: list[Candle],
        or_high: float,
        or_low: float,
        vwap_value: float,
        ema_9: float,
        ema_20: float,
        atr_5m: float,
        previous_high: float | None,
        previous_low: float | None,
        daily_move_pct: float,
        volume_ratio: float,
        market_bias: SignalSide,
    ) -> tuple[int, list[str], list[str]]:
        latest = session[-1]
        score = 0
        reasons: list[str] = []
        warnings = [
            "earnings, catalyst, economic-calendar, and option-spread checks need Robinhood/MCP data",
        ]

        breakout_index = find_orb_breakout_index(session, side, or_high, or_low, self.strong_volume_ratio)
        pullback_ok = breakout_index is not None and pullback_held(session, breakout_index, side, or_high, or_low, vwap_value)
        trigger_ok = breakout_index is not None and trigger_broke(session, breakout_index, side)
        room_ok = has_unobstructed_room(
            side=side,
            entry=latest.close,
            atr_5m=atr_5m,
            reward_risk=self.target_reward_risk,
            previous_high=previous_high,
            previous_low=previous_low,
        )
        market_ok = market_bias in (side, "WAIT")
        price_filter_ok = latest.close > 20
        daily_move_ok = daily_move_pct >= 0.75
        relative_volume_ok = volume_ratio >= self.strong_volume_ratio

        if side == "LONG":
            checks = [
                (relative_volume_ok, 10, f"relative volume proxy {volume_ratio:.2f} >= 1.5"),
                (latest.close > vwap_value, 10, "price is above VWAP"),
                (ema_9 > ema_20, 10, "5m 9 EMA is above 20 EMA"),
                (breakout_index is not None, 10, "closed above 15m opening-range high"),
                (relative_volume_ok, 10, "breakout/recent volume is strong"),
                (market_ok, 10, "SPY/QQQ bias does not fight long setup"),
                (room_ok, 10, "at least 1.5R of room by prior-session levels"),
                (price_filter_ok and daily_move_ok, 10, "price and daily-move filters pass"),
                (symbol in self.tier_1 or volume_ratio >= 2.0, 10, "symbol tier/liquidity filter passes"),
                (pullback_ok and trigger_ok, 10, "orderly pullback held and trigger broke"),
            ]
        else:
            checks = [
                (relative_volume_ok, 10, f"relative volume proxy {volume_ratio:.2f} >= 1.5"),
                (latest.close < vwap_value, 10, "price is below VWAP"),
                (ema_9 < ema_20, 10, "5m 9 EMA is below 20 EMA"),
                (breakout_index is not None, 10, "closed below 15m opening-range low"),
                (relative_volume_ok, 10, "breakdown/recent volume is strong"),
                (market_ok, 10, "SPY/QQQ bias does not fight short setup"),
                (room_ok, 10, "at least 1.5R of room by prior-session levels"),
                (price_filter_ok and daily_move_ok, 10, "price and daily-move filters pass"),
                (symbol in self.tier_1 or volume_ratio >= 2.0, 10, "symbol tier/liquidity filter passes"),
                (pullback_ok and trigger_ok, 10, "orderly bounce failed and trigger broke"),
            ]

        for passed, points, reason in checks:
            if passed:
                score += points
                reasons.append(f"+{points} {reason}")

        if symbol == "TSLA":
            warnings.append("TSLA should use half normal risk during the first 50 trades")
        if side == "SHORT":
            warnings.append("bearish paper signal maps to buying a put, not shorting shares")

        return score, reasons, warnings

    def _trade(
        self,
        side: Literal["LONG", "SHORT"],
        symbol: str,
        session: list[Candle],
        atr_5m: float,
        confidence: int,
        reasons: list[str],
        warnings: list[str],
    ) -> SetupSignal:
        latest = session[-1]
        pullback = session[-2]
        atr_stop = atr_5m * self.risk_atr_multiple
        if side == "LONG":
            stop_price = min(pullback.low, latest.close - atr_stop)
            risk = latest.close - stop_price
            target_1 = latest.close + risk * self.target_reward_risk
            target_2 = latest.close + risk * 2
        else:
            stop_price = max(pullback.high, latest.close + atr_stop)
            risk = stop_price - latest.close
            target_1 = latest.close - risk * self.target_reward_risk
            target_2 = latest.close - risk * 2

        risk_pct = (risk / latest.close) * 100 if latest.close else 0
        return SetupSignal(
            scanner="orb_vwap_pullback",
            symbol=symbol,
            side=side,
            setup="breakout",
            confidence=confidence,
            grade="A" if confidence >= 90 else "B",
            price=latest.close,
            entry_price=latest.close,
            stop_price=stop_price,
            target_1_price=target_1,
            target_2_price=target_2,
            risk_pct=risk_pct,
            target_1_pct=risk_pct * self.target_reward_risk,
            target_2_pct=risk_pct * 2,
            reward_to_risk=self.target_reward_risk,
            reasons=reasons,
            warnings=warnings,
            observed_at=latest.opened_at,
        )

    def _wait(
        self,
        symbol: str,
        candles: list[Candle],
        confidence: int,
        reasons: list[str],
        warnings: list[str],
    ) -> SetupSignal:
        observed_at = candles[-1].opened_at if candles else datetime.now(tz=EASTERN)
        price = candles[-1].close if candles else 0
        return SetupSignal(
            scanner="orb_vwap_pullback",
            symbol=symbol,
            side="WAIT",
            setup="chop" if candles else "insufficient_data",
            confidence=confidence,
            grade="WATCH" if confidence >= 50 else "NO_TRADE",
            price=price,
            entry_price=None,
            stop_price=None,
            target_1_price=None,
            target_2_price=None,
            risk_pct=0,
            target_1_pct=0,
            target_2_pct=0,
            reward_to_risk=self.target_reward_risk,
            reasons=reasons,
            warnings=warnings,
            observed_at=observed_at,
        )

    def _stand_down(self, signal: SetupSignal, reason: str) -> SetupSignal:
        return SetupSignal(
            scanner=signal.scanner,
            symbol=signal.symbol,
            side="WAIT",
            setup=signal.setup,
            confidence=signal.confidence,
            grade="WATCH",
            price=signal.price,
            entry_price=None,
            stop_price=None,
            target_1_price=None,
            target_2_price=None,
            risk_pct=signal.risk_pct,
            target_1_pct=signal.target_1_pct,
            target_2_pct=signal.target_2_pct,
            reward_to_risk=signal.reward_to_risk,
            reasons=[reason, *signal.reasons],
            warnings=signal.warnings,
            observed_at=signal.observed_at,
        )


def ema(values: list[float], period: int) -> float:
    if not values:
        return 0

    multiplier = 2 / (period + 1)
    result = values[0]
    for value in values[1:]:
        result = (value - result) * multiplier + result
    return result


def latest_regular_session(candles: list[Candle]) -> list[Candle]:
    regular = [candle for candle in candles if is_regular_market_open(candle.opened_at)]
    if not regular:
        return []

    latest_date = regular[-1].opened_at.astimezone(EASTERN).date()
    return [candle for candle in regular if candle.opened_at.astimezone(EASTERN).date() == latest_date]


def previous_session_levels(
    candles: list[Candle],
    current_time: datetime,
) -> tuple[float | None, float | None, float | None]:
    regular = [candle for candle in candles if is_regular_market_open(candle.opened_at)]
    current_date = current_time.astimezone(EASTERN).date()
    previous = [
        candle for candle in regular if candle.opened_at.astimezone(EASTERN).date() < current_date
    ]
    if not previous:
        return None, None, None

    previous_date = previous[-1].opened_at.astimezone(EASTERN).date()
    previous_session = [
        candle for candle in previous if candle.opened_at.astimezone(EASTERN).date() == previous_date
    ]
    return (
        max(candle.high for candle in previous_session),
        min(candle.low for candle in previous_session),
        previous_session[-1].close,
    )


def opening_range_candles(candles: list[Candle]) -> list[Candle]:
    return [
        candle
        for candle in candles
        if clock_time(9, 30) <= candle.opened_at.astimezone(EASTERN).time() < clock_time(9, 45)
    ]


def is_entry_window(now: datetime) -> bool:
    eastern_time = now.astimezone(EASTERN).time()
    return clock_time(9, 45) <= eastern_time <= clock_time(11, 15) or clock_time(
        13, 30
    ) <= eastern_time <= clock_time(15, 30)


def vwap(candles: list[Candle]) -> float:
    volume_sum = sum(candle.volume for candle in candles if candle.volume > 0)
    if volume_sum <= 0:
        return candles[-1].close if candles else 0

    typical_value_sum = sum(
        ((candle.high + candle.low + candle.close) / 3) * candle.volume
        for candle in candles
        if candle.volume > 0
    )
    return typical_value_sum / volume_sum


def average_true_range(candles: list[Candle], period: int) -> float:
    if len(candles) < 2:
        return 0

    ranges: list[float] = []
    for index in range(1, len(candles)):
        current = candles[index]
        previous_close = candles[index - 1].close
        ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous_close),
                abs(current.low - previous_close),
            )
        )

    return mean(ranges[-period:]) if ranges else 0


def find_orb_breakout_index(
    session: list[Candle],
    side: Literal["LONG", "SHORT"],
    or_high: float,
    or_low: float,
    strong_volume_ratio: float,
) -> int | None:
    for index, candle in enumerate(session):
        if candle.opened_at.astimezone(EASTERN).time() < clock_time(9, 45):
            continue

        prior_volumes = [item.volume for item in session[max(0, index - 20) : index] if item.volume > 0]
        avg_volume = mean(prior_volumes) if prior_volumes else 0
        volume_ok = avg_volume <= 0 or candle.volume >= avg_volume * strong_volume_ratio
        if side == "LONG" and candle.close > or_high and volume_ok:
            return index
        if side == "SHORT" and candle.close < or_low and volume_ok:
            return index

    return None


def pullback_held(
    session: list[Candle],
    breakout_index: int,
    side: Literal["LONG", "SHORT"],
    or_high: float,
    or_low: float,
    vwap_value: float,
) -> bool:
    pullback = session[breakout_index + 1 : breakout_index + 4]
    if not pullback:
        return False

    breakout_volume = session[breakout_index].volume
    pullback_volume_declined = mean(candle.volume for candle in pullback) < breakout_volume
    if side == "LONG":
        held_level = min(candle.low for candle in pullback) >= min(or_high, vwap_value)
    else:
        held_level = max(candle.high for candle in pullback) <= max(or_low, vwap_value)

    return pullback_volume_declined and held_level


def trigger_broke(
    session: list[Candle],
    breakout_index: int,
    side: Literal["LONG", "SHORT"],
) -> bool:
    pullback = session[breakout_index + 1 : breakout_index + 4]
    if not pullback:
        return False

    latest = session[-1]
    final_pullback = pullback[-1]
    if side == "LONG":
        return latest.close > final_pullback.high
    return latest.close < final_pullback.low


def has_unobstructed_room(
    side: Literal["LONG", "SHORT"],
    entry: float,
    atr_5m: float,
    reward_risk: float,
    previous_high: float | None,
    previous_low: float | None,
) -> bool:
    if atr_5m <= 0:
        return False

    required_room = atr_5m * reward_risk
    if side == "LONG":
        return previous_high is None or previous_high <= entry or previous_high - entry >= required_room
    return previous_low is None or previous_low >= entry or entry - previous_low >= required_room


def run_orb_once(symbols: list[str]) -> list[SetupSignal]:
    requested_symbols = sorted(set(symbols))
    candles_by_symbol = {
        symbol: fetch_yahoo_5m_candles(symbol)
        for symbol in sorted(set(requested_symbols) | {"SPY", "QQQ"})
    }
    strategy = OpeningRangeBreakoutStrategy()
    signals = strategy.evaluate_universe(candles_by_symbol)
    return [signal for signal in signals if signal.symbol in requested_symbols]


def detect_fair_value_gaps(
    candles: list[Candle],
    min_gap_pct: float = 0.03,
) -> list[FairValueGap]:
    gaps: list[FairValueGap] = []
    for index in range(2, len(candles)):
        first = candles[index - 2]
        current = candles[index]

        if current.low > first.high:
            gap_pct = ((current.low - first.high) / first.high) * 100
            if gap_pct >= min_gap_pct:
                gaps.append(
                    FairValueGap(
                        symbol=current.symbol,
                        side="bullish",
                        lower_bound=first.high,
                        upper_bound=current.low,
                        formed_at=current.opened_at,
                        mitigated=gap_was_mitigated(
                            candles[index + 1 :],
                            side="bullish",
                            lower_bound=first.high,
                            upper_bound=current.low,
                        ),
                    )
                )

        if current.high < first.low:
            gap_pct = ((first.low - current.high) / first.low) * 100
            if gap_pct >= min_gap_pct:
                gaps.append(
                    FairValueGap(
                        symbol=current.symbol,
                        side="bearish",
                        lower_bound=current.high,
                        upper_bound=first.low,
                        formed_at=current.opened_at,
                        mitigated=gap_was_mitigated(
                            candles[index + 1 :],
                            side="bearish",
                            lower_bound=current.high,
                            upper_bound=first.low,
                        ),
                    )
                )

    return gaps


def gap_was_mitigated(
    future_candles: list[Candle],
    side: PatternSide,
    lower_bound: float,
    upper_bound: float,
) -> bool:
    midpoint = (lower_bound + upper_bound) / 2
    for candle in future_candles:
        if side == "bullish" and candle.low <= midpoint:
            return True
        if side == "bearish" and candle.high >= midpoint:
            return True
    return False


def latest_active_gap(gaps: list[FairValueGap], side: PatternSide) -> FairValueGap | None:
    for gap in reversed(gaps):
        if gap.side == side and not gap.mitigated:
            return gap
    return None


def detect_liquidity_sweeps(
    candles: list[Candle],
    lookback: int = 4,
    equal_level_tolerance_pct: float = 0.05,
) -> list[LiquiditySweep]:
    sweeps: list[LiquiditySweep] = []
    if len(candles) < lookback + 1:
        return sweeps

    for index in range(lookback, len(candles)):
        prior = candles[index - lookback : index]
        current = candles[index]
        prior_high = max(candle.high for candle in prior)
        prior_low = min(candle.low for candle in prior)
        prior_high_base = mean(candle.high for candle in prior)
        prior_low_base = mean(candle.low for candle in prior)
        high_tolerance = prior_high_base * (equal_level_tolerance_pct / 100)
        low_tolerance = prior_low_base * (equal_level_tolerance_pct / 100)

        equal_highs = sum(abs(candle.high - prior_high) <= high_tolerance for candle in prior) >= 2
        equal_lows = sum(abs(candle.low - prior_low) <= low_tolerance for candle in prior) >= 2

        swept_lows = equal_lows and current.low < prior_low and current.close > prior_low
        swept_highs = equal_highs and current.high > prior_high and current.close < prior_high

        if swept_lows:
            choch_level = max(candle.high for candle in prior[-2:])
            if current.close > choch_level:
                sweeps.append(
                    LiquiditySweep(
                        symbol=current.symbol,
                        side="bullish",
                        liquidity_level=prior_low,
                        sweep_price=current.low,
                        choch_level=choch_level,
                        confirmed_at=current.opened_at,
                    )
                )

        if swept_highs:
            choch_level = min(candle.low for candle in prior[-2:])
            if current.close < choch_level:
                sweeps.append(
                    LiquiditySweep(
                        symbol=current.symbol,
                        side="bearish",
                        liquidity_level=prior_high,
                        sweep_price=current.high,
                        choch_level=choch_level,
                        confirmed_at=current.opened_at,
                    )
                )

    return sweeps


def latest_sweep(sweeps: list[LiquiditySweep], side: PatternSide) -> LiquiditySweep | None:
    for sweep in reversed(sweeps):
        if sweep.side == side:
            return sweep
    return None


def classify_strat_scenario(current: Candle, previous: Candle) -> StratScenario:
    breaks_high = current.high > previous.high
    breaks_low = current.low < previous.low

    if breaks_high and breaks_low:
        return "3"
    if breaks_high:
        return "2U"
    if breaks_low:
        return "2D"
    return "1"


def strat_scenarios(candles: list[Candle]) -> list[StratScenario]:
    if len(candles) < 2:
        return []

    return [
        classify_strat_scenario(current=candles[index], previous=candles[index - 1])
        for index in range(1, len(candles))
    ]


def detect_strat_signals(candles: list[Candle]) -> list[StratSignal]:
    if len(candles) < 3:
        return []

    scenarios = strat_scenarios(candles)
    signals: list[StratSignal] = []
    for scenario_index in range(2, len(scenarios)):
        combo = scenarios[scenario_index - 2 : scenario_index + 1]
        current = candles[scenario_index + 1]
        previous = candles[scenario_index]

        if combo == ["2U", "1", "2U"]:
            signals.append(strat_signal("2-1-2 continuation", "bullish", current, previous))
        elif combo == ["2D", "1", "2D"]:
            signals.append(strat_signal("2-1-2 continuation", "bearish", current, previous))
        elif combo == ["2D", "1", "2U"]:
            signals.append(strat_signal("2-1-2 reversal", "bullish", current, previous))
        elif combo == ["2U", "1", "2D"]:
            signals.append(strat_signal("2-1-2 reversal", "bearish", current, previous))
        elif combo == ["3", "1", "2U"]:
            signals.append(strat_signal("3-1-2 reversal", "bullish", current, previous))
        elif combo == ["3", "1", "2D"]:
            signals.append(strat_signal("3-1-2 reversal", "bearish", current, previous))
        elif combo == ["1", "2D", "2U"]:
            signals.append(strat_signal("1-2-2 revstrat", "bullish", current, previous))
        elif combo == ["1", "2U", "2D"]:
            signals.append(strat_signal("1-2-2 revstrat", "bearish", current, previous))
        elif combo[-2:] == ["2D", "2U"]:
            signals.append(strat_signal("2-2 reversal", "bullish", current, previous))
        elif combo[-2:] == ["2U", "2D"]:
            signals.append(strat_signal("2-2 reversal", "bearish", current, previous))

    return signals


def strat_signal(
    pattern: str,
    side: PatternSide,
    current: Candle,
    previous: Candle,
) -> StratSignal:
    if side == "bullish":
        trigger_price = previous.high
        stop_price = previous.low
    else:
        trigger_price = previous.low
        stop_price = previous.high

    return StratSignal(
        symbol=current.symbol,
        side=side,
        pattern=pattern,
        trigger_price=trigger_price,
        stop_price=stop_price,
        formed_at=current.opened_at,
    )


def latest_strat_signal(signals: list[StratSignal], side: PatternSide) -> StratSignal | None:
    for signal in reversed(signals):
        if signal.side == side:
            return signal
    return None


def timeframe_continuity_bias(candles: list[Candle]) -> SignalSide:
    if len(candles) < 3:
        return "WAIT"

    recent = candles[-3:]
    bullish = sum(candle.close > candle.open for candle in recent)
    bearish = sum(candle.close < candle.open for candle in recent)
    if bullish == len(recent):
        return "LONG"
    if bearish == len(recent):
        return "SHORT"
    return "WAIT"


def describe_active_patterns(candles: list[Candle]) -> list[str]:
    gaps = detect_fair_value_gaps(candles)
    sweeps = detect_liquidity_sweeps(candles)
    strat = detect_strat_signals(candles)
    descriptions: list[str] = []

    for side in ("bullish", "bearish"):
        gap = latest_active_gap(gaps, side)
        if gap:
            descriptions.append(
                f"{side} FVG {gap.lower_bound:.2f}-{gap.upper_bound:.2f}"
            )

        sweep = latest_sweep(sweeps, side)
        if sweep:
            operator = ">" if side == "bullish" else "<"
            descriptions.append(
                f"{side} liquidity sweep {sweep.sweep_price:.2f} CHOCH{operator}{sweep.choch_level:.2f}"
            )

        strat_signal_value = latest_strat_signal(strat, side)
        if strat_signal_value:
            descriptions.append(
                f"{side} Strat {strat_signal_value.pattern} trigger={strat_signal_value.trigger_price:.2f}"
            )

    return descriptions


def unique_reasons(reasons: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for reason in reasons:
        if reason in seen:
            continue
        seen.add(reason)
        unique.append(reason)
    return unique


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
        "?range=5d&interval=5m&includePrePost=false"
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
        volume = quote["volume"][index]
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
                volume=float(volume or 0),
            )
        )

    return candles


def aggregate_checkpoint_candles(candles: list[Candle], checkpoint_minutes: int) -> list[Candle]:
    buckets: dict[datetime, list[Candle]] = {}
    for candle in candles:
        if not is_regular_market_open(candle.opened_at):
            continue

        market_open = candle.opened_at.replace(hour=9, minute=30, second=0, microsecond=0)
        minutes_from_open = int((candle.opened_at - market_open).total_seconds() // 60)
        if minutes_from_open < 0:
            continue

        bucket_start = market_open + timedelta(
            minutes=(minutes_from_open // checkpoint_minutes) * checkpoint_minutes
        )
        buckets.setdefault(bucket_start, []).append(candle)

    checkpoint_candles: list[Candle] = []
    for opened_at, bucket_candles in sorted(buckets.items()):
        checkpoint_candles.append(
            Candle(
                symbol=bucket_candles[0].symbol,
                opened_at=opened_at,
                open=bucket_candles[0].open,
                high=max(candle.high for candle in bucket_candles),
                low=min(candle.low for candle in bucket_candles),
                close=bucket_candles[-1].close,
                volume=sum(candle.volume for candle in bucket_candles),
            )
        )

    return checkpoint_candles


def infer_market_bias(signals: list[SetupSignal]) -> SignalSide:
    long_votes = sum(signal.confidence for signal in signals if signal.side == "LONG")
    short_votes = sum(signal.confidence for signal in signals if signal.side == "SHORT")
    if long_votes >= short_votes + 20:
        return "LONG"
    if short_votes >= long_votes + 20:
        return "SHORT"
    return "WAIT"


def parse_symbols(raw_symbols: str, watchlist_path: str | None) -> list[str]:
    symbols = [symbol.strip().upper() for symbol in raw_symbols.split(",") if symbol.strip()]
    if watchlist_path:
        with open(watchlist_path) as watchlist:
            symbols.extend(line.strip().upper() for line in watchlist if line.strip())

    return sorted(set(symbols))


def format_signal(signal: SetupSignal) -> str:
    entry = f"{signal.entry_price:.2f}" if signal.entry_price else "-"
    stop = f"{signal.stop_price:.2f}" if signal.stop_price else "-"
    target_1 = f"{signal.target_1_price:.2f}" if signal.target_1_price else "-"
    target_2 = f"{signal.target_2_price:.2f}" if signal.target_2_price else "-"
    reasons = "; ".join(signal.reasons[:4])
    warnings = f" warnings={'; '.join(signal.warnings)}" if signal.warnings else ""
    return (
        f"{signal.observed_at.isoformat()} {signal.symbol:<5} ${signal.price:>9.2f} "
        f"{signal.side:<5} {signal.setup:<17} score={signal.confidence:>3} "
        f"grade={signal.grade:<8} entry={entry:<8} stop={stop:<8} "
        f"t1={target_1:<8} t2={target_2:<8} R:R={signal.reward_to_risk:.2f} "
        f"{reasons}{warnings}"
    )


def format_pattern_summary(symbol: str, checkpoint_candles: list[Candle]) -> str:
    gaps = detect_fair_value_gaps(checkpoint_candles)
    sweeps = detect_liquidity_sweeps(checkpoint_candles)
    bullish_gap = latest_active_gap(gaps, "bullish")
    bearish_gap = latest_active_gap(gaps, "bearish")
    bullish_sweep = latest_sweep(sweeps, "bullish")
    bearish_sweep = latest_sweep(sweeps, "bearish")

    parts: list[str] = []
    if bullish_gap:
        parts.append(f"bullish_fvg={bullish_gap.lower_bound:.2f}-{bullish_gap.upper_bound:.2f}")
    if bearish_gap:
        parts.append(f"bearish_fvg={bearish_gap.lower_bound:.2f}-{bearish_gap.upper_bound:.2f}")
    if bullish_sweep:
        parts.append(
            f"bullish_sweep={bullish_sweep.sweep_price:.2f} choch>{bullish_sweep.choch_level:.2f}"
        )
    if bearish_sweep:
        parts.append(
            f"bearish_sweep={bearish_sweep.sweep_price:.2f} choch<{bearish_sweep.choch_level:.2f}"
        )

    return f"{symbol:<5} patterns: " + (", ".join(parts) if parts else "none")


def read_journal(journal_path: Path) -> list[dict[str, str]]:
    if not journal_path.exists():
        return []

    with journal_path.open(newline="") as file:
        return list(csv.DictReader(file))


def write_journal(journal_path: Path, rows: list[dict[str, str]]) -> None:
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    with journal_path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=JOURNAL_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def journal_signal_id(signal: SetupSignal) -> str:
    timestamp = signal.observed_at.strftime("%Y%m%dT%H%M")
    return f"{timestamp}-{signal.scanner}-{signal.symbol}-{signal.side}-{signal.setup}-{signal.grade}"


def signal_to_journal_row(signal: SetupSignal) -> dict[str, str]:
    return {
        "id": journal_signal_id(signal),
        "scanner": signal.scanner,
        "opened_at": signal.observed_at.isoformat(),
        "closed_at": "",
        "symbol": signal.symbol,
        "side": signal.side,
        "setup": signal.setup,
        "grade": signal.grade,
        "confidence": str(signal.confidence),
        "entry_price": format_optional_price(signal.entry_price),
        "stop_price": format_optional_price(signal.stop_price),
        "target_1_price": format_optional_price(signal.target_1_price),
        "target_2_price": format_optional_price(signal.target_2_price),
        "last_price": f"{signal.price:.2f}",
        "status": "OPEN",
        "result_pct": "0.000",
        "reasons": " | ".join(signal.reasons[:6]),
    }


def format_optional_price(price: float | None) -> str:
    return f"{price:.2f}" if price is not None else ""


def has_open_trade(rows: list[dict[str, str]], signal: SetupSignal) -> bool:
    return any(
        row.get("status") == "OPEN"
        and row.get("scanner", "strat_fvg_liquidity") == signal.scanner
        and row.get("symbol") == signal.symbol
        and row.get("side") == signal.side
        for row in rows
    )


def has_recent_trade(rows: list[dict[str, str]], signal: SetupSignal) -> bool:
    for row in rows:
        if (
            row.get("scanner", "strat_fvg_liquidity") != signal.scanner
            or row.get("symbol") != signal.symbol
            or row.get("side") != signal.side
        ):
            continue

        opened_at = datetime.fromisoformat(row["opened_at"])
        if signal.observed_at - opened_at <= timedelta(minutes=JOURNAL_COOLDOWN_MINUTES):
            return True

    return False


def update_trade_status(row: dict[str, str], current_price: float, observed_at: datetime) -> None:
    if row.get("status") != "OPEN":
        return

    side = row["side"]
    entry_price = float(row["entry_price"])
    stop_price = float(row["stop_price"])
    target_1_price = float(row["target_1_price"])
    target_2_price = float(row["target_2_price"])
    row["last_price"] = f"{current_price:.2f}"

    status = "OPEN"
    if side == "LONG":
        if current_price <= stop_price:
            status = "STOPPED"
        elif current_price >= target_2_price:
            status = "TARGET_2"
        elif current_price >= target_1_price:
            status = "TARGET_1"
        result_pct = ((current_price - entry_price) / entry_price) * 100
    else:
        if current_price >= stop_price:
            status = "STOPPED"
        elif current_price <= target_2_price:
            status = "TARGET_2"
        elif current_price <= target_1_price:
            status = "TARGET_1"
        result_pct = ((entry_price - current_price) / entry_price) * 100

    row["result_pct"] = f"{result_pct:.3f}"
    if status != "OPEN":
        row["status"] = status
        row["closed_at"] = observed_at.isoformat()


def update_journal(journal_path: Path, signals: list[SetupSignal]) -> dict[str, int]:
    rows = read_journal(journal_path)
    latest_prices = {signal.symbol: signal.price for signal in signals}
    latest_times = {signal.symbol: signal.observed_at for signal in signals}
    closed_count = 0
    added_count = 0

    for row in rows:
        symbol = row.get("symbol", "")
        if symbol not in latest_prices or row.get("status") != "OPEN":
            continue

        previous_status = row["status"]
        update_trade_status(row, latest_prices[symbol], latest_times[symbol])
        if row["status"] != previous_status:
            closed_count += 1

    for signal in signals:
        if signal.side == "WAIT" or signal.entry_price is None:
            continue
        if has_open_trade(rows, signal) or has_recent_trade(rows, signal):
            continue

        rows.append(signal_to_journal_row(signal))
        added_count += 1

    write_journal(journal_path, rows)
    return {"added": added_count, "closed": closed_count, "open": count_open_trades(rows)}


def count_open_trades(rows: list[dict[str, str]]) -> int:
    return sum(row.get("status") == "OPEN" for row in rows)


def summarize_journal(journal_path: Path) -> str:
    rows = read_journal(journal_path)
    closed = [row for row in rows if row.get("status") in {"TARGET_1", "TARGET_2", "STOPPED"}]
    winners = [row for row in closed if row.get("status") in {"TARGET_1", "TARGET_2"}]
    open_count = count_open_trades(rows)
    win_rate = (len(winners) / len(closed) * 100) if closed else 0
    avg_result = mean(float(row["result_pct"]) for row in closed) if closed else 0
    return (
        f"journal={journal_path} total={len(rows)} open={open_count} closed={len(closed)} "
        f"wins={len(winners)} win_rate={win_rate:.1f}% avg_result={avg_result:.3f}%"
    )


def summarize_journal_performance(journal_path: Path) -> list[dict[str, object]]:
    rows = read_journal(journal_path)
    scanners = sorted({row.get("scanner", "strat_fvg_liquidity") for row in rows})
    summaries: list[dict[str, object]] = []
    for scanner in scanners:
        scanner_rows = [
            row for row in rows if row.get("scanner", "strat_fvg_liquidity") == scanner
        ]
        closed = [
            row for row in scanner_rows if row.get("status") in {"TARGET_1", "TARGET_2", "STOPPED"}
        ]
        winners = [row for row in closed if row.get("status") in {"TARGET_1", "TARGET_2"}]
        losses = [row for row in closed if row.get("status") == "STOPPED"]
        open_count = count_open_trades(scanner_rows)
        win_rate = (len(winners) / len(closed) * 100) if closed else 0
        avg_result = mean(float(row["result_pct"]) for row in closed) if closed else 0
        summaries.append(
            {
                "scanner": scanner,
                "total": len(scanner_rows),
                "open": open_count,
                "closed": len(closed),
                "wins": len(winners),
                "losses": len(losses),
                "win_rate": round(win_rate, 1),
                "avg_result_pct": round(avg_result, 3),
                "ready_for_review": len(closed) >= 10,
                "trades_until_review": max(0, 10 - len(closed)),
            }
        )

    return summaries


def run_once(
    symbols: list[str],
    checkpoint_minutes: int,
    strategy: CheckpointConfluenceStrategy,
) -> list[SetupSignal]:
    candles_by_symbol: dict[str, list[Candle]] = {}
    checkpoints_by_symbol: dict[str, list[Candle]] = {}
    signals: list[SetupSignal] = []

    for symbol in symbols:
        raw_candles = fetch_yahoo_5m_candles(symbol)
        checkpoint_candles = aggregate_checkpoint_candles(
            raw_candles,
            checkpoint_minutes=checkpoint_minutes,
        )
        candles_by_symbol[symbol] = raw_candles
        checkpoints_by_symbol[symbol] = checkpoint_candles
        if not raw_candles or len(checkpoint_candles) < 2:
            continue

        quote = Quote(
            symbol=symbol,
            price=raw_candles[-1].close,
            observed_at=raw_candles[-1].opened_at,
        )
        levels = strategy.build_levels(checkpoint_candles[-1], checkpoint_minutes)
        signals.append(
            strategy.evaluate(
                quote=quote,
                levels=levels,
                checkpoint_candles=checkpoint_candles,
            )
        )

    market_bias = infer_market_bias(
        [signal for signal in signals if signal.symbol in {"SPY", "QQQ"}]
    )
    if market_bias == "WAIT":
        return signals

    biased_signals: list[SetupSignal] = []
    for symbol in symbols:
        raw_candles = candles_by_symbol.get(symbol, [])
        checkpoint_candles = checkpoints_by_symbol.get(symbol, [])
        if not raw_candles or len(checkpoint_candles) < 2:
            continue

        quote = Quote(
            symbol=symbol,
            price=raw_candles[-1].close,
            observed_at=raw_candles[-1].opened_at,
        )
        levels = strategy.build_levels(checkpoint_candles[-1], checkpoint_minutes)
        biased_signals.append(
            strategy.evaluate(
                quote=quote,
                levels=levels,
                checkpoint_candles=checkpoint_candles,
                market_bias=market_bias,
            )
        )

    return biased_signals


def run_once_using_quote_endpoint(
    symbols: list[str],
    checkpoint_minutes: int,
    strategy: CheckpointConfluenceStrategy,
) -> list[SetupSignal]:
    quotes_by_symbol = {quote.symbol: quote for quote in fetch_yahoo_quotes(symbols)}
    signals: list[SetupSignal] = []

    for symbol in symbols:
        quote = quotes_by_symbol.get(symbol)
        checkpoint_candles = aggregate_checkpoint_candles(
            fetch_yahoo_5m_candles(symbol),
            checkpoint_minutes=checkpoint_minutes,
        )
        if quote is None or len(checkpoint_candles) < 2:
            continue

        levels = strategy.build_levels(checkpoint_candles[-1], checkpoint_minutes)
        signals.append(
            strategy.evaluate(
                quote=quote,
                levels=levels,
                checkpoint_candles=checkpoint_candles,
            )
        )

    market_bias = infer_market_bias(
        [signal for signal in signals if signal.symbol in {"SPY", "QQQ"}]
    )
    if market_bias == "WAIT":
        return signals

    biased_signals: list[SetupSignal] = []
    for symbol in symbols:
        quote = quotes_by_symbol.get(symbol)
        checkpoint_candles = aggregate_checkpoint_candles(
            fetch_yahoo_5m_candles(symbol),
            checkpoint_minutes=checkpoint_minutes,
        )
        if quote is None or len(checkpoint_candles) < 2:
            continue

        levels = strategy.build_levels(checkpoint_candles[-1], checkpoint_minutes)
        biased_signals.append(
            strategy.evaluate(
                quote=quote,
                levels=levels,
                checkpoint_candles=checkpoint_candles,
                market_bias=market_bias,
            )
        )

    return biased_signals


def run_live_monitor() -> None:
    parser = argparse.ArgumentParser(description="QuackQuant paper-only setup scanner")
    parser.add_argument(
        "--symbols",
        default=os.getenv("QUACKQUANT_SYMBOLS", "SPY,QQQ"),
        help="Comma-separated symbols, for example SPY,QQQ,AAPL,NVDA",
    )
    parser.add_argument("--watchlist", default=os.getenv("QUACKQUANT_WATCHLIST"))
    parser.add_argument(
        "--checkpoint-minutes",
        type=int,
        choices=(30, 60),
        default=int(os.getenv("QUACKQUANT_CHECKPOINT_MINUTES", "60")),
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=int(os.getenv("QUACKQUANT_POLL_SECONDS", "300")),
    )
    parser.add_argument(
        "--journal",
        type=Path,
        default=Path(os.getenv("QUACKQUANT_JOURNAL", DEFAULT_JOURNAL_PATH)),
        help="CSV paper-trade journal path",
    )
    parser.add_argument("--no-journal", action="store_true", help="Disable paper journal updates")
    parser.add_argument("--journal-summary", action="store_true", help="Print journal summary and exit")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    if args.journal_summary:
        print(summarize_journal(args.journal))
        return

    symbols = parse_symbols(args.symbols, args.watchlist)
    strategy = CheckpointConfluenceStrategy(
        risk_pct=float(os.getenv("QUACKQUANT_RISK_PCT", "0.15")),
        target_1_pct=float(os.getenv("QUACKQUANT_TARGET_1_PCT", "0.30")),
        target_2_pct=float(os.getenv("QUACKQUANT_TARGET_2_PCT", "0.45")),
        zone_width_pct=float(os.getenv("QUACKQUANT_ZONE_WIDTH_PCT", "0.03")),
        breakout_buffer_pct=float(os.getenv("QUACKQUANT_BREAKOUT_BUFFER_PCT", "0.02")),
    )

    print("QuackQuant confluence setup scanner")
    print(
        f"symbols={symbols} checkpoint={args.checkpoint_minutes}m "
        f"risk={strategy.risk_pct}% t1={strategy.target_1_pct}% "
        f"t2={strategy.target_2_pct}% R:R={strategy.reward_to_risk:.2f}"
    )
    print("Paper-only: prints signals, entries, stops, and targets. It never places trades.")

    while True:
        now = datetime.now(tz=EASTERN)
        if not is_regular_market_open(now):
            print(f"{now.isoformat()} market not open; waiting {args.poll_seconds}s")
            if args.once:
                return
            time.sleep(args.poll_seconds)
            continue

        signals = run_once(
            symbols=symbols,
            checkpoint_minutes=args.checkpoint_minutes,
            strategy=strategy,
        )
        for signal in sorted(signals, key=lambda item: item.confidence, reverse=True):
            print(format_signal(signal))

        if not args.no_journal:
            journal_stats = update_journal(args.journal, signals)
            print(
                f"journal updated: added={journal_stats['added']} "
                f"closed={journal_stats['closed']} open={journal_stats['open']} "
                f"path={args.journal}"
            )

        if args.once:
            return
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    run_live_monitor()
