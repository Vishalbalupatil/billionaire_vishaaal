"""Bootstrap the :class:`CandleBuilder` history ring buffer from Kite's
historical REST API.

The forecast endpoint needs >= 20 completed 1m bars to return
``source=live`` instead of the synthetic fallback. Without seeding, the ring
buffer starts empty and only fills as live ticks produce rollovers — so the
forecast stays synthetic for ~20 minutes after every restart, even in the
middle of the trading day.

This module fetches the most recent ``lookback_minutes`` minutes of 1m
candles for each configured token via ``kite.historical_data`` and feeds them
into :meth:`CandleBuilder.seed_history`. It is a best-effort, synchronous,
one-shot call invoked during FastAPI startup.

Design notes:
    * Only runs when both a live broker *and* an access token are configured.
      Paper mode is a complete no-op.
    * Kite's 1m historical window is capped at 60 days per request; we request
      far less (`lookback_minutes` defaults to 240 = 4h, matching
      ``HISTORY_MAX``).
    * Failures per-token are logged and swallowed so one bad symbol never
      blocks the boot sequence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from billionaire.marketdata.candle_builder import CandleBuilder
from billionaire.models import Candle

log = logging.getLogger(__name__)

# Kite Connect interprets ``from``/``to`` on historical_data as IST
# (Asia/Kolkata, UTC+05:30). On a UTC server ``datetime.now()`` would be
# ~5h30m behind real IST, making the requested window point at a dead
# pre-market slot and returning empty/stale candles. Construct request
# timestamps explicitly in IST.
IST = timezone(timedelta(hours=5, minutes=30))


class _HistoricalDataSource(Protocol):
    def historical_data(
        self,
        instrument_token: int,
        from_dt: Any,
        to_dt: Any,
        interval: str = "minute",
        continuous: bool = False,
        oi: bool = False,
    ) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class SeedResult:
    tokens_requested: int
    tokens_seeded: int
    candles_total: int
    errors: dict[int, str]


def _row_to_candle(token: int, row: dict[str, Any], timeframe: str = "1m") -> Candle | None:
    """Convert one Kite historical row into a :class:`Candle`.

    Kite returns ``date`` as a ``datetime`` with IST tzinfo. The
    :class:`CandleBuilder` uses naive UTC internally (see
    ``_bucket_start``), so we normalise here.
    """
    date = row.get("date")
    if date is None:
        return None
    if isinstance(date, str):
        try:
            date = datetime.fromisoformat(date)
        except ValueError:
            return None
    if getattr(date, "tzinfo", None) is not None:
        # Convert to naive UTC to match CandleBuilder's internal convention.
        date = date.astimezone(timezone.utc).replace(tzinfo=None)
    try:
        return Candle(
            instrument_token=token,
            timeframe=timeframe,
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=int(row.get("volume") or 0),
            oi=int(row.get("oi") or 0),
            ts=date,
        )
    except (KeyError, TypeError, ValueError):
        return None


def seed_candle_history(
    source: _HistoricalDataSource,
    candle_builder: CandleBuilder,
    tokens: list[int],
    *,
    lookback_minutes: int = 240,
    interval: str = "minute",
    timeframe: str = "1m",
    now: datetime | None = None,
) -> SeedResult:
    """Backfill ``candle_builder`` with recent historical candles per token.

    Returns a :class:`SeedResult` summarising the outcome for logging.
    """
    if not tokens:
        return SeedResult(0, 0, 0, {})

    to_dt = now or datetime.now(IST)
    from_dt = to_dt - timedelta(minutes=lookback_minutes)

    errors: dict[int, str] = {}
    seeded = 0
    total = 0
    for token in tokens:
        try:
            rows = source.historical_data(
                instrument_token=token,
                from_dt=from_dt,
                to_dt=to_dt,
                interval=interval,
            )
        except Exception as e:  # pragma: no cover — network-dependent
            errors[token] = f"{type(e).__name__}: {e}"
            continue

        candles: list[Candle] = []
        for row in rows:
            c = _row_to_candle(token, row, timeframe=timeframe)
            if c is not None:
                candles.append(c)
        if candles:
            candle_builder.seed_history(token, timeframe, candles)
            seeded += 1
            total += len(candles)

    return SeedResult(
        tokens_requested=len(tokens),
        tokens_seeded=seeded,
        candles_total=total,
        errors=errors,
    )
