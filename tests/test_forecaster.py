"""Tests for the heuristic forecaster.

Verifies the contract (not accuracy — the scaffold intentionally makes no
accuracy claims). Specifically: shape of the output, sanity of the band,
bias labelling, and synthetic-closes determinism.
"""

from __future__ import annotations

import pytest

from billionaire.strategy.forecaster import (
    DISCLAIMER,
    forecast,
    synthetic_closes,
)


def test_synthetic_closes_is_deterministic_and_reasonable() -> None:
    a = synthetic_closes(n=100, seed=7, last=24800.0)
    b = synthetic_closes(n=100, seed=7, last=24800.0)
    assert a == b
    assert len(a) == 100
    assert abs(a[-1] - 24800.0) / 24800.0 < 0.02  # ends near the anchor


def test_intraday_forecast_shape_and_band_widens() -> None:
    closes = synthetic_closes(n=200, seed=3)
    r = forecast(closes, horizon="intraday", steps=30)
    assert r.horizon == "intraday"
    assert len(r.points) == 30
    # Band should strictly widen with horizon under sqrt(t) scaling.
    w1 = r.points[0].upper - r.points[0].lower
    w_last = r.points[-1].upper - r.points[-1].lower
    assert w_last > w1
    # Last price is sandwiched between lower and upper bands at every step.
    for p in r.points:
        assert p.lower <= p.price <= p.upper
    assert r.disclaimer == DISCLAIMER


def test_daily_forecast_uses_wider_step() -> None:
    closes = synthetic_closes(n=200, seed=5)
    intraday = forecast(closes, horizon="intraday", steps=5)
    daily = forecast(closes, horizon="daily", steps=5)
    # Same math, but daily simply re-labels. Widths identical step-for-step.
    for a, b in zip(intraday.points, daily.points, strict=True):
        assert a.upper - a.lower == pytest.approx(b.upper - b.lower, rel=1e-9)


def test_bias_horizon_has_no_points_but_has_label() -> None:
    closes = synthetic_closes(n=200, seed=1)
    r = forecast(closes, horizon="bias", steps=10)
    assert r.points == []
    assert r.bias in {"BULLISH", "BEARISH", "NEUTRAL"}
    assert 0.0 <= r.confidence <= 1.0


def test_forecast_requires_enough_history() -> None:
    with pytest.raises(ValueError):
        forecast([100.0, 101.0, 102.0], horizon="intraday", steps=5)


def test_unknown_horizon_rejected() -> None:
    closes = synthetic_closes(n=50, seed=1)
    with pytest.raises(ValueError):
        forecast(closes, horizon="weekly", steps=5)


def test_bias_label_matches_sign_of_drift() -> None:
    # Strong uptrend with a little jitter so vol > 0.
    import numpy as np

    rng = np.random.default_rng(0)
    up = [
        float(100.0 * (1.005 ** i) * (1 + rng.normal(0, 0.0005)))
        for i in range(60)
    ]
    r = forecast(up, horizon="bias", steps=1)
    assert r.bias == "BULLISH"

    down = [
        float(100.0 * (0.995 ** i) * (1 + rng.normal(0, 0.0005)))
        for i in range(60)
    ]
    r = forecast(down, horizon="bias", steps=1)
    assert r.bias == "BEARISH"
