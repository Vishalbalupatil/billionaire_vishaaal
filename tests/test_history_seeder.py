"""Tests for the Kite historical-data seeder that bootstraps the CandleBuilder
ring buffer at startup.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from billionaire.marketdata.candle_builder import CandleBuilder
from billionaire.marketdata.history_seeder import (
    SeedResult,
    _row_to_candle,
    seed_candle_history,
)


class _FakeSource:
    """Deterministic stand-in for ZerodhaClient.historical_data."""

    def __init__(self, rows_by_token: dict[int, list[dict[str, Any]]]) -> None:
        self._rows = rows_by_token
        self.calls: list[tuple[int, datetime, datetime, str]] = []

    def historical_data(
        self,
        instrument_token: int,
        from_dt: Any,
        to_dt: Any,
        interval: str = "minute",
        continuous: bool = False,
        oi: bool = False,
    ) -> list[dict[str, Any]]:
        self.calls.append((instrument_token, from_dt, to_dt, interval))
        if instrument_token not in self._rows:
            raise RuntimeError("no data for token")
        return list(self._rows[instrument_token])


def _row(ts: datetime, close: float, volume: int = 100) -> dict[str, Any]:
    return {
        "date": ts,
        "open": close - 0.5,
        "high": close + 0.7,
        "low": close - 1.0,
        "close": close,
        "volume": volume,
    }


def test_row_to_candle_normalises_tzaware_ist_to_naive_utc() -> None:
    ist = timezone(timedelta(hours=5, minutes=30))
    row = _row(datetime(2024, 6, 1, 10, 30, tzinfo=ist), close=100.0)
    c = _row_to_candle(42, row)
    assert c is not None
    assert c.ts.tzinfo is None
    # 10:30 IST == 05:00 UTC
    assert c.ts == datetime(2024, 6, 1, 5, 0)
    assert c.close == 100.0


def test_row_to_candle_handles_iso_string_date() -> None:
    row = _row(datetime(2024, 6, 1, 5, 0), close=42.0)
    row["date"] = row["date"].isoformat()
    c = _row_to_candle(7, row)
    assert c is not None
    assert c.ts == datetime(2024, 6, 1, 5, 0)


def test_row_to_candle_returns_none_on_garbage() -> None:
    assert _row_to_candle(1, {"date": None, "open": 1, "high": 1, "low": 1, "close": 1}) is None
    assert _row_to_candle(1, {"date": "not-a-date", "open": 1, "high": 1, "low": 1, "close": 1}) is None
    assert _row_to_candle(1, {"date": datetime(2024, 6, 1)}) is None  # missing OHLC


def test_seed_candle_history_populates_ring_and_feeds_recent_candles() -> None:
    base = datetime(2024, 6, 1, 3, 45)
    rows = [_row(base + timedelta(minutes=i), close=100.0 + i) for i in range(30)]
    source = _FakeSource({42: rows})
    cb = CandleBuilder(timeframes=["1m"])

    result = seed_candle_history(source, cb, [42], lookback_minutes=60, now=base + timedelta(minutes=30))

    assert result == SeedResult(tokens_requested=1, tokens_seeded=1, candles_total=30, errors={})
    recent = cb.recent_candles(42, "1m")
    assert len(recent) == 30
    assert recent[0].close == 100.0
    assert recent[-1].close == 129.0
    # The from/to window was (now - lookback) .. now
    assert len(source.calls) == 1
    token, from_dt, to_dt, interval = source.calls[0]
    assert token == 42
    assert interval == "minute"
    assert to_dt - from_dt == timedelta(minutes=60)


def test_seed_candle_history_swallows_per_token_errors() -> None:
    base = datetime(2024, 6, 1, 3, 45)
    rows = [_row(base + timedelta(minutes=i), close=50.0 + i) for i in range(5)]
    source = _FakeSource({42: rows})  # token 99 will raise
    cb = CandleBuilder(timeframes=["1m"])

    result = seed_candle_history(source, cb, [42, 99], lookback_minutes=10, now=base + timedelta(minutes=10))

    assert result.tokens_requested == 2
    assert result.tokens_seeded == 1
    assert result.candles_total == 5
    assert 99 in result.errors
    # Working token still ended up in the buffer.
    assert len(cb.recent_candles(42, "1m")) == 5
    assert cb.recent_candles(99, "1m") == []


def test_seed_candle_history_empty_tokens_is_noop() -> None:
    source = _FakeSource({})
    cb = CandleBuilder(timeframes=["1m"])
    result = seed_candle_history(source, cb, [])
    assert result == SeedResult(0, 0, 0, {})
    assert source.calls == []


def test_seed_candle_history_skips_empty_response() -> None:
    source = _FakeSource({42: []})
    cb = CandleBuilder(timeframes=["1m"])
    result = seed_candle_history(source, cb, [42])
    assert result.tokens_seeded == 0
    assert result.candles_total == 0
    assert cb.recent_candles(42, "1m") == []


@pytest.mark.parametrize("lookback,expected_delta", [(60, 60), (240, 240), (15, 15)])
def test_seed_candle_history_honours_lookback_minutes(lookback: int, expected_delta: int) -> None:
    source = _FakeSource({1: []})
    cb = CandleBuilder(timeframes=["1m"])
    now = datetime(2024, 6, 1, 12, 0)
    seed_candle_history(source, cb, [1], lookback_minutes=lookback, now=now)
    _, from_dt, to_dt, _ = source.calls[0]
    assert (to_dt - from_dt).total_seconds() == expected_delta * 60
    assert to_dt == now
