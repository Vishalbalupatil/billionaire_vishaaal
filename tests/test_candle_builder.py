"""Tests for CandleBuilder history buffer (used by the forecast endpoint)."""

from __future__ import annotations

from datetime import datetime, timedelta

from billionaire.marketdata.candle_builder import CandleBuilder
from billionaire.models import Candle, Tick


def _tick(token: int, price: float, ts: datetime) -> Tick:
    return Tick(instrument_token=token, ltp=price, ts=ts, volume=10, oi=0)


def test_recent_candles_empty_by_default() -> None:
    cb = CandleBuilder(timeframes=["1m"])
    assert cb.recent_candles(123, "1m") == []


def test_rollover_populates_history_ring() -> None:
    cb = CandleBuilder(timeframes=["1m"])
    base = datetime(2024, 1, 2, 3, 30, 0)
    # 25 consecutive one-minute ticks; each new-minute tick rolls over the
    # prior bucket, producing 24 completed candles.
    for i in range(25):
        cb.on_tick(_tick(42, 100.0 + i, base + timedelta(minutes=i)))
    recent = cb.recent_candles(42, "1m")
    assert len(recent) == 24
    assert recent[0].close == 100.0
    assert recent[-1].close == 123.0
    # Current (in-progress) bucket is separate from history.
    cur = cb.current_candle(42, "1m")
    assert cur is not None and cur.close == 124.0


def test_history_respects_max_size() -> None:
    cb = CandleBuilder(timeframes=["1m"], history_size=5)
    base = datetime(2024, 1, 2, 3, 30, 0)
    for i in range(10):
        cb.on_tick(_tick(7, 50.0 + i, base + timedelta(minutes=i)))
    recent = cb.recent_candles(7, "1m")
    assert len(recent) == 5  # oldest dropped by the deque


def test_seed_history_preloads_buffer() -> None:
    cb = CandleBuilder(timeframes=["1m"])
    base = datetime(2024, 1, 2, 9, 15, 0)
    preload = [
        Candle(
            instrument_token=1, timeframe="1m",
            open=100.0 + i, high=100.5 + i, low=99.5 + i, close=100.2 + i,
            volume=1_000, oi=0, ts=base + timedelta(minutes=i),
        )
        for i in range(30)
    ]
    cb.seed_history(1, "1m", preload)
    closes = [c.close for c in cb.recent_candles(1, "1m")]
    assert len(closes) == 30
    assert closes[0] == 100.2
    assert closes[-1] == 129.2


def test_seed_history_merges_with_live_ticks_in_chronological_order() -> None:
    """Real scenario: ws.set_tokens() runs first so live ticks populate the
    deque, then the REST-backed seed finishes ~5-30s later with *older*
    bars. Appending naively would leave the series non-monotonic and
    corrupt np.diff(np.log(...)) in the forecaster. Seed must merge + sort
    by timestamp."""
    cb = CandleBuilder(timeframes=["1m"])
    base = datetime(2024, 1, 2, 9, 15, 0)
    # Simulate 2 minutes of live ticks that already completed 1 candle.
    cb.on_tick(_tick(1, 110.0, base + timedelta(minutes=5)))
    cb.on_tick(_tick(1, 111.0, base + timedelta(minutes=6)))
    live_ts = cb.recent_candles(1, "1m")[0].ts
    assert live_ts == base + timedelta(minutes=5)

    # Historical seed backfills bars from 09:15 through 09:19 (older than live).
    historical = [
        Candle(
            instrument_token=1, timeframe="1m",
            open=100.0 + i, high=100.5 + i, low=99.5 + i, close=100.2 + i,
            volume=1_000, oi=0, ts=base + timedelta(minutes=i),
        )
        for i in range(5)  # 09:15..09:19
    ]
    cb.seed_history(1, "1m", historical)
    recent = cb.recent_candles(1, "1m")
    timestamps = [c.ts for c in recent]
    assert timestamps == sorted(timestamps), "series must be chronological"
    assert timestamps[0] == base  # earliest historical bar first
    assert timestamps[-1] == live_ts  # live bar still last


def test_seed_history_live_candle_wins_on_timestamp_collision() -> None:
    """When the historical REST snapshot and the live tick both produced a
    bar for the same minute (seed running *through* a minute rollover),
    keep the live one — it reflects actual observed ticks through close."""
    cb = CandleBuilder(timeframes=["1m"])
    ts = datetime(2024, 1, 2, 9, 20, 0)
    # Live tick builds a candle for 09:20 with close=111.0.
    cb.on_tick(_tick(1, 111.0, ts))
    cb.on_tick(_tick(1, 112.0, ts + timedelta(minutes=1)))

    # Historical REST returns its own version of the same 09:20 bar,
    # with a different close.
    rest_version = Candle(
        instrument_token=1, timeframe="1m",
        open=105.0, high=106.0, low=104.0, close=999.0,
        volume=1_000, oi=0, ts=ts,
    )
    cb.seed_history(1, "1m", [rest_version])

    recent = cb.recent_candles(1, "1m")
    at_ts = next(c for c in recent if c.ts == ts)
    assert at_ts.close == 111.0, "live tick's value must win on collision"
