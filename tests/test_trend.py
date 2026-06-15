"""Tests for the multi-timeframe trend analysis module."""

import numpy as np
import pandas as pd

from ai_trader.models.scanner import TrendDirection
from ai_trader.scanner.trend import (
    _classify_trend,
    _compute_adx,
    _compute_strength,
    analyze_trend,
    multi_timeframe_trend,
)


def _make_trend_df(n: int = 200, trend: str = "up") -> pd.DataFrame:
    np.random.seed(42)
    base = 1000.0
    if trend == "up":
        close = base + np.cumsum(np.random.normal(2, 1, n))
    elif trend == "down":
        close = base + np.cumsum(np.random.normal(-2, 1, n))
    else:
        close = base + np.cumsum(np.random.normal(0, 0.5, n))

    high = close + np.abs(np.random.normal(3, 1, n))
    low = close - np.abs(np.random.normal(3, 1, n))
    open_ = close + np.random.normal(0, 1, n)
    volume = np.random.randint(1000, 10000, n).astype(float)

    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


def test_analyze_trend_uptrend():
    df = _make_trend_df(200, "up")
    result = analyze_trend(df, "TEST")
    assert result.symbol == "TEST"
    assert result.overall in (TrendDirection.UP, TrendDirection.STRONG_UP)
    assert result.strength > 50


def test_analyze_trend_downtrend():
    df = _make_trend_df(200, "down")
    result = analyze_trend(df, "TEST")
    assert result.overall in (TrendDirection.DOWN, TrendDirection.STRONG_DOWN)


def test_analyze_trend_sideways():
    df = _make_trend_df(200, "sideways")
    result = analyze_trend(df, "TEST")
    # Sideways should not be strongly directional
    assert result.overall in (TrendDirection.SIDEWAYS, TrendDirection.UP, TrendDirection.DOWN)


def test_analyze_trend_insufficient_data():
    df = _make_trend_df(10)
    result = analyze_trend(df, "TEST")
    assert result.symbol == "TEST"
    assert result.overall == TrendDirection.SIDEWAYS


def test_multi_timeframe_trend():
    data_by_tf = {
        "5m": _make_trend_df(100, "up"),
        "15m": _make_trend_df(100, "up"),
        "1h": _make_trend_df(100, "up"),
    }
    result = multi_timeframe_trend(data_by_tf, "TEST")
    assert result.symbol == "TEST"
    assert result.overall in (TrendDirection.UP, TrendDirection.STRONG_UP)


def test_multi_timeframe_mixed():
    data_by_tf = {
        "5m": _make_trend_df(100, "down"),
        "15m": _make_trend_df(100, "up"),
        "1h": _make_trend_df(100, "up"),
    }
    result = multi_timeframe_trend(data_by_tf, "MIXED")
    assert result.symbol == "MIXED"
    # With higher TFs bullish, overall should lean bullish
    assert result.overall in (TrendDirection.UP, TrendDirection.STRONG_UP, TrendDirection.SIDEWAYS)


def test_classify_trend_strong_up():
    direction = _classify_trend(
        ltp=110, ema20=105, ema50=100, ema200=90,
        st_signal=1, adx=30, rsi_val=65,
    )
    assert direction == TrendDirection.STRONG_UP


def test_classify_trend_strong_down():
    direction = _classify_trend(
        ltp=90, ema20=95, ema50=100, ema200=110,
        st_signal=-1, adx=30, rsi_val=35,
    )
    assert direction == TrendDirection.STRONG_DOWN


def test_compute_adx():
    df = _make_trend_df(100, "up")
    adx = _compute_adx(df)
    assert isinstance(adx, float)
    assert adx >= 0


def test_compute_strength():
    # Perfect alignment
    s = _compute_strength(ltp=110, ema20=105, ema50=100, ema200=90, adx=30, rsi_val=75)
    assert s >= 70

    # No alignment
    s2 = _compute_strength(ltp=100, ema20=100, ema50=100, ema200=100, adx=10, rsi_val=50)
    assert s2 < s
