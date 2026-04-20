"""Heuristic price-path forecaster.

**This is a transparent scaffold, not a magical AI.** It fits a log-return
random walk with drift from the last ``lookback`` bars of closes and projects
the expected path plus a 95% confidence band forward. That's it. It does not
look at volume, order flow, news, options chain, regime, or anything else a
serious forecaster would care about. It exists so the dashboard has something
honest to render while a real model is trained and plugged in via
:class:`ForecastModel` (swap in-place).

The returned :class:`ForecastResult` carries an explicit disclaimer; the UI
must display it next to any chart.

Horizons:
- ``intraday``: project N one-minute steps (default 30).
- ``daily``: project N one-day steps (default 5), wider band.
- ``bias``: compute drift + vol and produce only a directional label and a
  confidence score (no predicted path — the UI shows an arrow).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np

DISCLAIMER = (
    "Heuristic projection from historical closes. NOT financial advice, "
    "NOT a prediction of future prices. Model assumes log-returns are iid "
    "Gaussian — real markets are not. Band is 95% confidence under those "
    "assumptions; real tail events routinely exceed it."
)


@dataclass
class ForecastPoint:
    step: int
    ts_iso: str
    price: float
    lower: float
    upper: float


@dataclass
class ForecastResult:
    symbol: str
    horizon: str
    last_price: float
    drift_per_step: float
    vol_per_step: float
    bias: str  # "BULLISH" | "BEARISH" | "NEUTRAL"
    confidence: float  # 0..1, purely for display (inverse of relative vol)
    points: list[ForecastPoint] = field(default_factory=list)
    notes: str = ""
    disclaimer: str = DISCLAIMER


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)


def _bias_from(drift: float, vol: float) -> str:
    """Label the direction relative to noise.

    A drift smaller than ~10% of per-step volatility is well within noise and
    is labelled NEUTRAL; that avoids the UI flipping bullish/bearish on
    essentially zero signal.
    """
    if vol <= 1e-12:
        return "NEUTRAL"
    z = drift / vol
    if z > 0.1:
        return "BULLISH"
    if z < -0.1:
        return "BEARISH"
    return "NEUTRAL"


def _display_confidence(vol: float) -> float:
    """Map per-step vol to a 0..1 pseudo-confidence purely for the UI badge.

    This is not a probability — it just lets us render "Low / Med / High
    confidence" consistently. Lower vol -> higher displayed confidence.
    """
    # Per-minute vol of ~0.1% is typical for Nifty; scale so that maps to ~0.8.
    scaled = 1.0 - min(1.0, vol / 0.005)
    return round(max(0.0, min(1.0, scaled)), 3)


def forecast(
    closes: list[float] | np.ndarray,
    horizon: str = "intraday",
    steps: int = 30,
    symbol: str = "NIFTY",
    lookback: int = 60,
    step_seconds: int | None = None,
) -> ForecastResult:
    """Produce a heuristic forecast result.

    ``step_seconds`` overrides the default step size (60s for intraday, one
    trading day ~= 6h15m worth of seconds for daily; only used to label the
    projected timestamps in the response).
    """
    horizon = horizon.lower()
    if horizon not in {"intraday", "daily", "bias"}:
        raise ValueError(f"unknown horizon: {horizon!r}")

    arr = np.asarray(list(closes), dtype=float)
    if arr.size < 20:
        raise ValueError(
            f"forecast needs >= 20 closes, got {arr.size}; "
            "seed more history or wait for enough bars to accumulate."
        )
    window = arr[-lookback:] if arr.size > lookback else arr
    rets = np.diff(np.log(window))
    drift = float(np.mean(rets))
    vol = float(np.std(rets, ddof=1)) if rets.size > 1 else 0.0
    last = float(arr[-1])

    bias = _bias_from(drift, vol)
    conf = _display_confidence(vol)

    if horizon == "bias":
        return ForecastResult(
            symbol=symbol,
            horizon=horizon,
            last_price=last,
            drift_per_step=drift,
            vol_per_step=vol,
            bias=bias,
            confidence=conf,
            points=[],
            notes="Bias only; no projected path.",
        )

    if horizon == "intraday":
        ss = step_seconds if step_seconds is not None else 60
    else:  # daily
        ss = step_seconds if step_seconds is not None else 22500  # ~6h15m session

    base_ts = _now_utc()
    pts: list[ForecastPoint] = []
    for k in range(1, steps + 1):
        proj = last * math.exp(drift * k)
        # Lognormal 95% band derived from Brownian motion scaling.
        band_factor = 1.96 * vol * math.sqrt(k)
        lower = last * math.exp(drift * k - band_factor)
        upper = last * math.exp(drift * k + band_factor)
        ts = (base_ts + timedelta(seconds=ss * k)).isoformat()
        pts.append(ForecastPoint(step=k, ts_iso=ts, price=proj, lower=lower, upper=upper))

    return ForecastResult(
        symbol=symbol,
        horizon=horizon,
        last_price=last,
        drift_per_step=drift,
        vol_per_step=vol,
        bias=bias,
        confidence=conf,
        points=pts,
        notes=(
            f"drift={drift:+.5f}/step, vol={vol:.5f}/step, "
            f"lookback={min(lookback, arr.size)} bars"
        ),
    )


def synthetic_closes(n: int = 120, seed: int = 7, last: float = 24800.0) -> list[float]:
    """Deterministic fake close series for demos / smoke tests.

    Used by the ``/api/forecast`` endpoint when no real candle history has
    accumulated yet (e.g. the app just booted, or it is outside market hours).
    Explicitly marked synthetic in the API response so the UI can label it.
    """
    rng = np.random.default_rng(seed)
    rets = rng.normal(loc=0.00005, scale=0.0018, size=n)
    arr = np.empty(n)
    arr[0] = last * math.exp(-np.sum(rets))  # so the series ends at ~``last``
    for i in range(1, n):
        arr[i] = arr[i - 1] * math.exp(rets[i])
    return [float(x) for x in arr]
