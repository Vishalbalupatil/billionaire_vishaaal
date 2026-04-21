"""Pull historical OHLCV bars from Kite Connect and fill the local cache.

This module has three responsibilities and no others:

    1. Figure out what bars are *missing* from the cache for a given
       (token, timeframe, [from, to]) tuple — i.e. the smallest incremental
       window the cache hasn't seen yet.
    2. Slice the missing window into chunks that respect Kite's per-request
       day-count caps (100 days for ``5minute``; 60 days for ``minute``;
       400 days for ``day``). Oversized requests silently truncate on
       Kite's side, so we MUST chunk client-side.
    3. Call the broker's ``historical_data`` method per chunk, convert rows
       into :class:`CachedBar` values, and UPSERT them through the cache.

Rate limiting: Kite allows 3 historical_data requests per second per API
key. This module respects that with a ``request_interval_seconds`` throttle
between chunks (default ``0.35`` seconds = ~3 req/s). Wire a stricter value
in production if you hit 429s from other callers sharing the key.

Typed-away from the kite SDK via the :class:`_HistoricalDataSource`
Protocol in ``history_seeder`` — we reuse it so tests can substitute a
fake source without any real Kite dependency.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from billionaire.marketdata.historical_cache import CachedBar, HistoricalCache
from billionaire.marketdata.history_seeder import IST, _HistoricalDataSource

log = logging.getLogger(__name__)


# Kite's per-request day caps for each interval. Hitting these without
# chunking gets you silently truncated data, not an error — which is the
# worst failure mode because it looks like you just have holes.
_MAX_DAYS_BY_INTERVAL: dict[str, int] = {
    "minute": 60,
    "3minute": 200,
    "5minute": 100,
    "10minute": 100,
    "15minute": 200,
    "30minute": 200,
    "60minute": 400,
    "day": 2000,
}


@dataclass(frozen=True)
class FetchResult:
    """Summary of a pull — returned so callers can log / surface it."""

    token: int
    timeframe: str
    chunks: int
    bars_written: int
    from_ts: datetime
    to_ts: datetime


def _timeframe_to_kite_interval(timeframe: str) -> str:
    """Map our timeframe strings (``"5m"``, ``"1m"``) onto Kite's."""
    return {
        "1m": "minute",
        "3m": "3minute",
        "5m": "5minute",
        "10m": "10minute",
        "15m": "15minute",
        "30m": "30minute",
        "1h": "60minute",
        "1d": "day",
    }.get(timeframe, timeframe)


def _row_to_cached_bar(
    token: int, timeframe: str, row: dict[str, Any]
) -> CachedBar | None:
    """Convert a Kite historical_data row to a :class:`CachedBar`.

    Kite returns ``date`` as a tz-aware datetime in IST. Cache stores naive
    IST — stripping tzinfo is intentional so downstream strategy code can
    compare against ``time(9, 15)`` without timezone gymnastics.
    """
    dt = row.get("date")
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except ValueError:
            return None
    if getattr(dt, "tzinfo", None) is not None:
        dt = dt.astimezone(IST).replace(tzinfo=None)
    try:
        return CachedBar(
            instrument_token=token,
            timeframe=timeframe,
            ts=dt,
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=int(row.get("volume") or 0),
            oi=int(row.get("oi") or 0),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _chunked_windows(
    from_ts: datetime, to_ts: datetime, max_days: int
) -> list[tuple[datetime, datetime]]:
    """Split [from_ts, to_ts] into chunks each <= ``max_days`` days wide."""
    if from_ts >= to_ts:
        return []
    out: list[tuple[datetime, datetime]] = []
    cursor = from_ts
    while cursor < to_ts:
        end = min(cursor + timedelta(days=max_days), to_ts)
        out.append((cursor, end))
        cursor = end
    return out


def fetch_and_cache(
    source: _HistoricalDataSource,
    cache: HistoricalCache,
    *,
    token: int,
    timeframe: str,
    from_ts: datetime,
    to_ts: datetime,
    request_interval_seconds: float = 0.35,
    sleep: Any = time.sleep,
) -> FetchResult:
    """Pull the missing [from_ts, to_ts] slice of bars for ``token`` and
    persist them. Idempotent — re-calling with the same window is a no-op.

    Only the gap *after* the cache's current ``last_ts`` is pulled, so
    repeated calls stay cheap. If the cache is empty, the full window is
    pulled.
    """
    kite_interval = _timeframe_to_kite_interval(timeframe)
    max_days = _MAX_DAYS_BY_INTERVAL.get(kite_interval, 60)

    last_cached = cache.last_ts(token, timeframe)
    fetch_from = from_ts
    if last_cached is not None and last_cached >= from_ts:
        # Start one bar past the last cached ts to avoid a wasted duplicate
        # fetch of the boundary bar.
        fetch_from = last_cached + timedelta(seconds=1)

    if fetch_from >= to_ts:
        log.info(
            "Historical cache hit: token=%d tf=%s already covers [%s, %s]",
            token, timeframe, from_ts.isoformat(), to_ts.isoformat(),
        )
        return FetchResult(
            token=token, timeframe=timeframe, chunks=0, bars_written=0,
            from_ts=from_ts, to_ts=to_ts,
        )

    chunks = _chunked_windows(fetch_from, to_ts, max_days)
    total_written = 0
    for i, (cf, ct) in enumerate(chunks):
        if i > 0:
            sleep(request_interval_seconds)
        try:
            rows = source.historical_data(
                instrument_token=token,
                from_dt=cf,
                to_dt=ct,
                interval=kite_interval,
            )
        except Exception as e:  # pragma: no cover — network-dependent
            log.warning(
                "Kite historical_data failed for token=%d tf=%s [%s..%s]: %s",
                token, timeframe, cf.isoformat(), ct.isoformat(), e,
            )
            continue
        bars: list[CachedBar] = []
        for row in rows:
            cb = _row_to_cached_bar(token, timeframe, row)
            if cb is not None:
                bars.append(cb)
        if bars:
            total_written += cache.upsert_bars(bars)

    log.info(
        "Historical fetch: token=%d tf=%s chunks=%d bars_written=%d",
        token, timeframe, len(chunks), total_written,
    )
    return FetchResult(
        token=token,
        timeframe=timeframe,
        chunks=len(chunks),
        bars_written=total_written,
        from_ts=from_ts,
        to_ts=to_ts,
    )


def backfill_last_n_years(
    source: _HistoricalDataSource,
    cache: HistoricalCache,
    *,
    tokens: list[int],
    timeframe: str,
    years: int,
    now: datetime | None = None,
    request_interval_seconds: float = 0.35,
) -> list[FetchResult]:
    """Convenience: backfill each token with the last ``years`` years of
    bars at ``timeframe``. Used by the ``backtest-orb`` CLI."""
    if not tokens:
        return []
    to_ts = now or datetime.now(IST).replace(tzinfo=None)
    from_ts = to_ts - timedelta(days=int(365 * years))
    results: list[FetchResult] = []
    for t in tokens:
        r = fetch_and_cache(
            source,
            cache,
            token=t,
            timeframe=timeframe,
            from_ts=from_ts,
            to_ts=to_ts,
            request_interval_seconds=request_interval_seconds,
        )
        results.append(r)
    return results


# Well-known Kite instrument tokens that we care about for the ORB strategy.
# These are stable (indices get permanent tokens on Kite) so hardcoding is
# acceptable — the alternative is an extra round-trip to the instruments
# endpoint every startup, which the codebase already does separately.
NIFTY50_INDEX_TOKEN = 256265
INDIA_VIX_TOKEN = 264969


def resolve_front_month_future_token(
    instruments: object,
    underlying: str = "NIFTY",
    now: datetime | None = None,
) -> int:
    """Look up the current-month NIFTY futures instrument_token from an
    :class:`InstrumentMaster`. Returns ``0`` if no match.

    Current-month = the nearest monthly expiry whose date is on or after
    ``now.date()``. If the back-month is closer (expiry week roll), we
    intentionally keep the current month — rolling by calendar-week would
    need a more nuanced volume/OI check which is outside the scope of this
    module.
    """
    if instruments is None:
        return 0
    reference = now or datetime.now(IST).replace(tzinfo=None)
    # Underlying is typically ``"NIFTY"`` which matches Kite's ``name``
    # field on the futures contract. The ``by_underlying`` helper (if it
    # exists) is preferred; otherwise fall back to scanning ``__iter__``.
    candidates: list[Any] = []
    if hasattr(instruments, "by_underlying"):
        candidates = list(
            instruments.by_underlying(underlying)  # type: ignore[attr-defined]
        )
    else:
        for inst in getattr(instruments, "__iter__", lambda: iter([]))():
            if getattr(inst, "name", "") == underlying and getattr(
                inst, "segment", None
            ) == "FUTURES":
                candidates.append(inst)
    # Pick the earliest expiry on or after today.
    def _expiry_as_date(inst: Any) -> date | None:
        exp = getattr(inst, "expiry", None)
        if exp is None:
            return None
        if isinstance(exp, date):
            return exp
        try:
            return datetime.fromisoformat(str(exp)).date()
        except ValueError:
            return None

    eligible = []
    for c in candidates:
        exp = _expiry_as_date(c)
        if exp is None or exp < reference.date():
            continue
        eligible.append((exp, c))
    if not eligible:
        return 0
    eligible.sort(key=lambda p: p[0])
    return int(eligible[0][1].instrument_token)
