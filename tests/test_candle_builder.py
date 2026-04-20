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
