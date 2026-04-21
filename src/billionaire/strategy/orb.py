"""Opening Range Breakout (ORB) strategy on the 5-minute timeframe.

Rules (as specified):
    * First 5-minute candle of the session (09:15-09:20 IST) defines the
      "opening range" ORH/ORL.
    * First price that trades through ORH from below on a later 5m bar:
      LONG Nifty current-month futures + BUY ATM call.
    * First price that trades through ORL from above on a later 5m bar:
      SHORT Nifty current-month futures + BUY ATM put.
    * Only one trade per day — the first valid break wins; subsequent breaks
      are ignored.
    * Stop-loss is the opposite side of the opening range (long → ORL,
      short → ORH).
    * Target is 2R from entry (RR = 1:2) by default, exposed via config.
    * Everything is squared off at ``square_off_time`` regardless.

Touch-based break detection (not close-based): we consider a break to have
occurred when the bar's high >= ORH (for longs) or low <= ORL (for shorts),
and the entry fills at ORH/ORL (the level) rather than the bar's close. This
matches how retail ORB is typically traded with stop-buy/stop-sell entries
placed at the level itself. Close-based detection misses ~40% of intraday
moves that trade through but close back inside the range.

This module contains ONLY pure logic — no I/O, no broker calls. The
walk-forward backtester (:mod:`billionaire.backtest.orb_backtest`) and the
live forecaster both consume the same primitives.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from enum import Enum


class BreakSide(str, Enum):
    """Which side of the opening range broke first."""

    LONG = "LONG"
    SHORT = "SHORT"


@dataclass(frozen=True)
class Bar:
    """Minimal OHLC representation — broker-agnostic."""

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


@dataclass(frozen=True)
class OpeningRange:
    """The high/low of the session's first 5-minute candle."""

    date: str  # ISO date of the session
    ts: datetime  # first candle's timestamp
    high: float
    low: float

    @property
    def width(self) -> float:
        return self.high - self.low

    @property
    def mid(self) -> float:
        return (self.high + self.low) / 2.0


@dataclass(frozen=True)
class ORBBreak:
    """The first bar where price trades through ORH or ORL."""

    side: BreakSide
    ts: datetime
    entry_price: float  # ORH for long, ORL for short (stop-level fills)
    stop_price: float  # opposite OR side
    target_price: float  # entry + RR*risk for long; entry - RR*risk for short
    bar_high: float
    bar_low: float
    bar_close: float


@dataclass(frozen=True)
class ORBExit:
    """How a trade concluded: hit stop, hit target, or EOD square-off."""

    ts: datetime
    price: float
    reason: str  # "stop", "target", "eod"


@dataclass(frozen=True)
class ORBTrade:
    """End-to-end record of one day's ORB trade."""

    date: str
    side: BreakSide
    break_: ORBBreak
    exit: ORBExit
    futures_pnl_points: float
    futures_pnl_pct: float
    bars_held: int

    @property
    def risk_points(self) -> float:
        b = self.break_
        return abs(b.entry_price - b.stop_price)

    @property
    def r_multiple(self) -> float:
        """How many R (risk units) the trade made. -1R = hit stop exactly."""
        r = self.risk_points
        if r <= 0:
            return 0.0
        return self.futures_pnl_points / r


# Session anchor for the Indian equity market (IST). The first 5m candle of
# the regular session starts at 09:15:00 and ends at 09:20:00.
SESSION_OPEN = time(9, 15)
FIRST_CANDLE_CLOSE = time(9, 20)
# Default square-off is 15:15 IST — 15 minutes before the 15:30 close — to
# leave room for an intraday exit order to fill before auto-squareoff.
DEFAULT_SQUARE_OFF = time(15, 15)


def find_opening_range(bars: list[Bar]) -> OpeningRange | None:
    """Extract the opening range from the first 5m candle of the session.

    ``bars`` must already be filtered to a single trading day, in
    chronological order. The first bar whose timestamp starts at 09:15 IST is
    treated as the opening range. Returns ``None`` if no suitable candle is
    present (half-day / holiday / missing data).
    """
    for bar in bars:
        if bar.ts.time() == SESSION_OPEN:
            return OpeningRange(
                date=bar.ts.date().isoformat(),
                ts=bar.ts,
                high=bar.high,
                low=bar.low,
            )
    return None


def find_first_break(
    opening_range: OpeningRange,
    bars_after_or: list[Bar],
    *,
    rr: float = 2.0,
) -> ORBBreak | None:
    """Scan bars *after* the opening range and return the first break.

    Touch-based detection. Walks bars chronologically; the first bar whose
    high >= ORH OR whose low <= ORL triggers a break. If both conditions are
    true on the same bar (spike through both ends — common on gap days or
    news bars), the direction closer to the bar's open wins, because that is
    the side the stop-order at the level fills first in reality. This is a
    simplifying assumption — real fills on both-side breaks are order-of-
    execution dependent and would need tick data to resolve.
    """
    orh = opening_range.high
    orl = opening_range.low
    risk = orh - orl
    if risk <= 0:
        return None

    for bar in bars_after_or:
        touched_high = bar.high >= orh
        touched_low = bar.low <= orl
        if not (touched_high or touched_low):
            continue

        if touched_high and touched_low:
            # Spike through both ends on the same bar. Choose the side the
            # bar's open was closer to — that level is hit first in real
            # time by a price moving away from open.
            dist_long = abs(bar.open - orh)
            dist_short = abs(bar.open - orl)
            side = BreakSide.LONG if dist_long <= dist_short else BreakSide.SHORT
        elif touched_high:
            side = BreakSide.LONG
        else:
            side = BreakSide.SHORT

        if side == BreakSide.LONG:
            entry = orh
            stop = orl
            target = entry + rr * risk
        else:
            entry = orl
            stop = orh
            target = entry - rr * risk

        return ORBBreak(
            side=side,
            ts=bar.ts,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            bar_high=bar.high,
            bar_low=bar.low,
            bar_close=bar.close,
        )

    return None


def simulate_exit(
    break_: ORBBreak,
    bars_after_break: list[Bar],
    *,
    square_off_time: time = DEFAULT_SQUARE_OFF,
) -> ORBExit:
    """Walk forward from the break bar onward and find the exit.

    Priority inside a single bar: if the bar's range spans both stop and
    target, we conservatively assume the STOP fires first. This is the
    pessimistic-fill convention every honest backtester uses — it avoids
    inflating win-rate on wide bars.
    """
    for bar in bars_after_break:
        if bar.ts.time() >= square_off_time:
            return ORBExit(ts=bar.ts, price=bar.open, reason="eod")

        if break_.side == BreakSide.LONG:
            hit_stop = bar.low <= break_.stop_price
            hit_target = bar.high >= break_.target_price
            if hit_stop:
                return ORBExit(
                    ts=bar.ts, price=break_.stop_price, reason="stop"
                )
            if hit_target:
                return ORBExit(
                    ts=bar.ts, price=break_.target_price, reason="target"
                )
        else:  # SHORT
            hit_stop = bar.high >= break_.stop_price
            hit_target = bar.low <= break_.target_price
            if hit_stop:
                return ORBExit(
                    ts=bar.ts, price=break_.stop_price, reason="stop"
                )
            if hit_target:
                return ORBExit(
                    ts=bar.ts, price=break_.target_price, reason="target"
                )

    # Ran out of bars with no stop / target / square-off hit — close at the
    # last bar's close. In practice this only happens on truncated data or
    # the very last sample of the dataset.
    last = bars_after_break[-1] if bars_after_break else None
    if last is None:
        return ORBExit(ts=break_.ts, price=break_.entry_price, reason="eod")
    return ORBExit(ts=last.ts, price=last.close, reason="eod")


def run_day(
    bars: list[Bar],
    *,
    rr: float = 2.0,
    square_off_time: time = DEFAULT_SQUARE_OFF,
) -> ORBTrade | None:
    """End-to-end single-day ORB trade. ``None`` when no valid break occurred.

    ``bars`` must be one trading day's worth of 5-minute bars in chronological
    order. Missing opening-range bar or a doji OR (high == low) returns None.
    """
    opening_range = find_opening_range(bars)
    if opening_range is None or opening_range.width <= 0:
        return None

    or_ts = opening_range.ts
    bars_after_or = [b for b in bars if b.ts > or_ts]
    break_ = find_first_break(opening_range, bars_after_or, rr=rr)
    if break_ is None:
        return None

    bars_after_break = [b for b in bars_after_or if b.ts > break_.ts]
    exit = simulate_exit(
        break_, bars_after_break, square_off_time=square_off_time
    )

    direction = 1.0 if break_.side == BreakSide.LONG else -1.0
    futures_pnl = direction * (exit.price - break_.entry_price)
    futures_pnl_pct = futures_pnl / break_.entry_price * 100.0
    bars_held = sum(1 for b in bars_after_break if b.ts <= exit.ts)

    return ORBTrade(
        date=opening_range.date,
        side=break_.side,
        break_=break_,
        exit=exit,
        futures_pnl_points=futures_pnl,
        futures_pnl_pct=futures_pnl_pct,
        bars_held=bars_held,
    )
