"""Tests for ``orb_service.today_from_cache`` and helpers."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from pathlib import Path

from billionaire.marketdata.historical_cache import CachedBar, HistoricalCache
from billionaire.services.orb_service import today_from_cache


def _mk_bar(token: int, ts: datetime, close: float) -> CachedBar:
    return CachedBar(
        instrument_token=token,
        timeframe="5m",
        ts=ts,
        open=close,
        high=close + 5,
        low=close - 5,
        close=close,
        volume=1_000,
        oi=0,
    )


def _seed_session(cache: HistoricalCache, token: int, day, base_price: float) -> None:
    """Seed a full 09:15–15:30 IST session of 5m bars at ``base_price``."""
    start = datetime.combine(day, time(9, 15))
    bars = []
    price = base_price
    for i in range(75):  # 75 five-minute bars = 9:15 → 15:20
        ts = start + timedelta(minutes=5 * i)
        bars.append(_mk_bar(token, ts, price))
        price += 0.2
    cache.upsert_bars(bars)


def test_today_from_cache_returns_tuple_with_bars(tmp_path: Path) -> None:
    """Regression for Devin Review #2 — bars must be returned so the route
    can call ``current_break`` on cache-backed data, not just synthetic."""
    db = tmp_path / "bars.db"
    cache = HistoricalCache(db)
    today = datetime(2024, 6, 10).date()  # a Monday
    _seed_session(cache, 256265, today, base_price=24_800.0)
    _seed_session(cache, 264969, today, base_price=14.5)
    cache.close()

    as_of = datetime.combine(today, time(10, 30))
    snap, bars = today_from_cache(db, as_of=as_of)

    assert snap is not None
    assert snap.or_formed is True
    assert snap.source == "cache"
    # bars are returned so current_break can run over them
    assert len(bars) >= 1
    assert bars[0].ts == datetime.combine(today, time(9, 15))


def test_today_from_cache_populates_prev_close_and_gap(tmp_path: Path) -> None:
    """Regression for Devin Review #3 — prev_close + today_open must come
    from the actual prior session close / today's open, not both be or_low."""
    db = tmp_path / "bars.db"
    cache = HistoricalCache(db)
    today = datetime(2024, 6, 11).date()     # Tuesday
    yday = datetime(2024, 6, 10).date()      # Monday
    day_before = datetime(2024, 6, 7).date() # Friday (skip weekend)
    _seed_session(cache, 256265, day_before, base_price=24_700.0)
    _seed_session(cache, 256265, yday, base_price=24_750.0)
    _seed_session(cache, 256265, today, base_price=24_800.0)
    cache.close()

    as_of = datetime.combine(today, time(10, 30))
    snap, _ = today_from_cache(db, as_of=as_of)

    assert snap is not None
    assert snap.prev_close is not None
    assert snap.today_open is not None
    # prev_close must NOT equal today_open — that's the exact bug.
    assert snap.prev_close != snap.today_open
    # Sanity: prev_close is the last 5m close of yday's session.
    # yday base 24750 + 74 steps * 0.2 = 24764.8
    assert abs(snap.prev_close - 24_764.8) < 0.01
    # today_open is the first bar's open = today's base 24800.
    assert snap.today_open == 24_800.0
    # prev_day_return_pct derived from (prev_close - prev_prev_close) / prev_prev_close
    assert snap.prev_day_return_pct is not None
    assert snap.prev_day_return_pct != 0.0


def test_today_from_cache_missing_db_returns_none_tuple(tmp_path: Path) -> None:
    """When the cache file doesn't exist, callers must get the tuple form,
    not a bare ``None`` — otherwise unpacking in the route raises TypeError."""
    missing = tmp_path / "does-not-exist.db"
    snap, bars = today_from_cache(missing)
    assert snap is None
    assert bars == []


