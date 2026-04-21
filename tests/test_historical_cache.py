"""Tests for the SQLite historical-bar cache + Kite-backed fetcher."""

from __future__ import annotations

from datetime import datetime, timedelta

from billionaire.marketdata.historical_cache import CachedBar, HistoricalCache
from billionaire.marketdata.historical_fetcher import (
    _chunked_windows,
    _row_to_cached_bar,
    fetch_and_cache,
)


def _bar(token: int, tf: str, t: datetime, close: float) -> CachedBar:
    return CachedBar(
        instrument_token=token,
        timeframe=tf,
        ts=t,
        open=close - 0.5,
        high=close + 0.5,
        low=close - 1.0,
        close=close,
        volume=1_000,
        oi=0,
    )


def test_cache_roundtrip_upsert_and_get() -> None:
    cache = HistoricalCache(":memory:")
    base = datetime(2024, 1, 2, 9, 15)
    bars = [_bar(256265, "5m", base + timedelta(minutes=5 * i), 24800 + i) for i in range(10)]
    assert cache.upsert_bars(bars) == 10

    fetched = cache.get_bars(256265, "5m", base, base + timedelta(hours=1))
    assert [b.close for b in fetched] == [24800 + i for i in range(10)]
    assert cache.count(256265, "5m") == 10
    cache.close()


def test_cache_upsert_overwrites_same_ts() -> None:
    cache = HistoricalCache(":memory:")
    t = datetime(2024, 1, 2, 9, 15)
    cache.upsert_bars([_bar(1, "5m", t, 100.0)])
    cache.upsert_bars([_bar(1, "5m", t, 200.0)])  # same PK
    rows = cache.get_bars(1, "5m", t, t)
    assert len(rows) == 1
    assert rows[0].close == 200.0  # replaced
    cache.close()


def test_cache_last_ts_tracks_most_recent() -> None:
    cache = HistoricalCache(":memory:")
    base = datetime(2024, 1, 2, 9, 15)
    cache.upsert_bars([
        _bar(1, "5m", base, 100),
        _bar(1, "5m", base + timedelta(hours=1), 101),
        _bar(1, "5m", base + timedelta(hours=2), 102),
    ])
    assert cache.last_ts(1, "5m") == base + timedelta(hours=2)
    assert cache.last_ts(2, "5m") is None  # different token
    cache.close()


def test_chunked_windows_respects_max_days() -> None:
    windows = _chunked_windows(
        datetime(2024, 1, 1), datetime(2024, 6, 1), max_days=100
    )
    # About 152 days total → 2 chunks: 0..100, 100..152.
    assert len(windows) == 2
    assert windows[0][0] == datetime(2024, 1, 1)
    assert windows[0][1] == datetime(2024, 4, 10)
    assert windows[-1][1] == datetime(2024, 6, 1)
    # Chunks must join end-to-end, no overlap, no gap.
    for a, b in zip(windows[:-1], windows[1:], strict=True):
        assert a[1] == b[0]


def test_chunked_windows_empty_when_from_equals_to() -> None:
    assert _chunked_windows(
        datetime(2024, 1, 1), datetime(2024, 1, 1), max_days=100
    ) == []


def test_row_to_cached_bar_converts_ist_tz() -> None:
    from datetime import timezone
    ist = timezone(timedelta(hours=5, minutes=30))
    row = {
        "date": datetime(2024, 1, 2, 9, 15, tzinfo=ist),
        "open": 100.0, "high": 101.0, "low": 99.5, "close": 100.5,
        "volume": 1_234, "oi": 0,
    }
    bar = _row_to_cached_bar(42, "5m", row)
    assert bar is not None
    # Strip to naive IST — downstream strategy reasons about time(9,15) literal.
    assert bar.ts.tzinfo is None
    assert bar.ts == datetime(2024, 1, 2, 9, 15)
    assert bar.close == 100.5


def test_row_to_cached_bar_handles_naive_datetime() -> None:
    row = {
        "date": datetime(2024, 1, 2, 9, 15),
        "open": 100.0, "high": 101.0, "low": 99.5, "close": 100.5,
    }
    bar = _row_to_cached_bar(42, "5m", row)
    assert bar is not None
    assert bar.ts == datetime(2024, 1, 2, 9, 15)
    assert bar.volume == 0  # default


class _FakeKite:
    """In-memory Kite historical_data impl for tests."""

    def __init__(self, bars_by_token: dict[int, list[dict]]) -> None:
        self.bars_by_token = bars_by_token
        self.call_args: list[dict] = []

    def historical_data(
        self,
        instrument_token: int,
        from_dt: datetime,
        to_dt: datetime,
        interval: str = "5minute",
        continuous: bool = False,
        oi: bool = False,
    ) -> list[dict]:
        self.call_args.append({
            "token": instrument_token,
            "from": from_dt,
            "to": to_dt,
            "interval": interval,
        })
        return [
            r for r in self.bars_by_token.get(instrument_token, [])
            if from_dt <= r["date"] <= to_dt
        ]


def test_fetch_and_cache_only_pulls_missing_window() -> None:
    """The fetcher must consult the cache's last_ts and only fetch the
    incremental gap — otherwise we'd burn Kite rate limit unnecessarily."""
    cache = HistoricalCache(":memory:")
    base = datetime(2024, 1, 2, 9, 15)
    # Seed cache with 5 bars.
    cache.upsert_bars([_bar(1, "5m", base + timedelta(minutes=5 * i), 100 + i) for i in range(5)])

    # Fake Kite has 10 bars total.
    fake_bars = [
        {
            "date": base + timedelta(minutes=5 * i),
            "open": 100 + i, "high": 100.5 + i, "low": 99.5 + i, "close": 100.1 + i,
            "volume": 1000,
        }
        for i in range(10)
    ]
    kite = _FakeKite({1: fake_bars})

    # Ask for the full window. Fetcher should only pull the 5 missing bars.
    result = fetch_and_cache(
        kite, cache, token=1, timeframe="5m",
        from_ts=base, to_ts=base + timedelta(minutes=5 * 9),
        sleep=lambda _: None,
    )
    # 1 chunk (5m is capped at 100 days; 5-bar window is trivially 1 chunk).
    assert result.chunks == 1
    # Kite was asked for a window starting AFTER the last cached ts, not the origin.
    assert kite.call_args[0]["from"] > base + timedelta(minutes=5 * 4)

    cache.close()


def test_fetch_and_cache_is_cache_hit_noop() -> None:
    """If the cache already extends past to_ts, no Kite call should fire."""
    cache = HistoricalCache(":memory:")
    base = datetime(2024, 1, 2, 9, 15)
    cache.upsert_bars([_bar(1, "5m", base + timedelta(minutes=5 * i), 100 + i) for i in range(20)])
    kite = _FakeKite({1: []})

    result = fetch_and_cache(
        kite, cache, token=1, timeframe="5m",
        from_ts=base, to_ts=base + timedelta(minutes=5 * 10),
        sleep=lambda _: None,
    )
    assert result.chunks == 0
    assert kite.call_args == []
    cache.close()
