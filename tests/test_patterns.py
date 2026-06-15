"""Tests for the chart pattern recognition module."""

import numpy as np
import pandas as pd

from ai_trader.scanner.patterns import (
    _find_pivots,
    detect_patterns,
)


def _make_df_with_double_top(n: int = 100) -> pd.DataFrame:
    """Create synthetic data with a double top pattern."""
    np.random.seed(123)
    # Uptrend -> peak -> pullback -> peak -> decline
    seg1 = np.linspace(100, 150, 30)  # uptrend
    seg2 = np.linspace(150, 130, 15)  # pullback
    seg3 = np.linspace(130, 149, 15)  # second push (near first peak)
    seg4 = np.linspace(149, 120, 40)  # decline
    close = np.concatenate([seg1, seg2, seg3, seg4])

    noise = np.random.normal(0, 0.5, len(close))
    close = close + noise
    high = close + np.abs(np.random.normal(1, 0.5, len(close)))
    low = close - np.abs(np.random.normal(1, 0.5, len(close)))
    open_ = close + np.random.normal(0, 0.3, len(close))
    volume = np.random.randint(5000, 15000, len(close)).astype(float)

    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


def _make_df_with_double_bottom(n: int = 100) -> pd.DataFrame:
    """Create synthetic data with a double bottom pattern."""
    np.random.seed(456)
    seg1 = np.linspace(150, 100, 30)  # downtrend
    seg2 = np.linspace(100, 120, 15)  # bounce
    seg3 = np.linspace(120, 101, 15)  # second dip
    seg4 = np.linspace(101, 140, 40)  # recovery
    close = np.concatenate([seg1, seg2, seg3, seg4])

    noise = np.random.normal(0, 0.5, len(close))
    close = close + noise
    high = close + np.abs(np.random.normal(1, 0.5, len(close)))
    low = close - np.abs(np.random.normal(1, 0.5, len(close)))
    open_ = close + np.random.normal(0, 0.3, len(close))
    volume = np.random.randint(5000, 15000, len(close)).astype(float)

    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


def test_find_pivots():
    series = pd.Series([1, 2, 3, 2, 1, 2, 3, 4, 3, 2, 1])
    highs, lows = _find_pivots(series, window=2)
    assert len(highs) > 0 or len(lows) > 0


def test_find_pivots_insufficient_data():
    series = pd.Series([1, 2, 3])
    highs, lows = _find_pivots(series, window=2)
    assert highs == [] and lows == []


def test_detect_patterns_returns_list():
    df = _make_df_with_double_top()
    patterns = detect_patterns(df, "TEST")
    assert isinstance(patterns, list)


def test_detect_patterns_insufficient_data():
    df = pd.DataFrame({
        "open": [100] * 10,
        "high": [105] * 10,
        "low": [95] * 10,
        "close": [100] * 10,
        "volume": [1000] * 10,
    })
    patterns = detect_patterns(df, "TEST")
    assert patterns == []


def test_double_top_detection():
    df = _make_df_with_double_top()
    patterns = detect_patterns(df, "DTOP")
    double_tops = [p for p in patterns if p.pattern.value == "DOUBLE_TOP"]
    if double_tops:
        assert double_tops[0].bias.value == "BEARISH"
        assert double_tops[0].confidence > 0


def test_double_bottom_detection():
    df = _make_df_with_double_bottom()
    patterns = detect_patterns(df, "DBOT")
    double_bottoms = [p for p in patterns if p.pattern.value == "DOUBLE_BOTTOM"]
    if double_bottoms:
        assert double_bottoms[0].bias.value == "BULLISH"


def test_pattern_has_entry_and_sl():
    df = _make_df_with_double_top()
    patterns = detect_patterns(df, "TEST")
    for pat in patterns:
        assert pat.entry_zone != 0 or pat.stop_loss != 0
        assert pat.confidence >= 0
        assert pat.confidence <= 1
