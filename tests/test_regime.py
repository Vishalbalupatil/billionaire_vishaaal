"""Tests for market regime detection."""

import numpy as np
import pandas as pd

from ai_trader.ai.regime import detect_regime
from ai_trader.models.domain import MarketRegime


def _trending_up_candles(n: int = 100) -> pd.DataFrame:
    prices = 22000 + np.arange(n) * 5.0 + np.random.randn(n) * 2
    return pd.DataFrame({
        "open": prices - 2,
        "high": prices + 10,
        "low": prices - 10,
        "close": prices,
        "volume": np.random.randint(5000, 20000, n),
    })


def _range_bound_candles(n: int = 100) -> pd.DataFrame:
    prices = 22000 + np.sin(np.linspace(0, 10, n)) * 20 + np.random.randn(n) * 3
    return pd.DataFrame({
        "open": prices - 2,
        "high": prices + 10,
        "low": prices - 10,
        "close": prices,
        "volume": np.random.randint(5000, 20000, n),
    })


def test_trending_up_detected():
    np.random.seed(42)
    df = _trending_up_candles()
    regime = detect_regime(df, vix=14.0)
    assert regime in (MarketRegime.TRENDING_UP, MarketRegime.RANGE_BOUND)


def test_high_vix_volatile():
    np.random.seed(42)
    df = _range_bound_candles()
    regime = detect_regime(df, vix=30.0)
    assert regime in (MarketRegime.VOLATILE, MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN)


def test_insufficient_data():
    df = pd.DataFrame({
        "open": [22000], "high": [22010], "low": [21990], "close": [22005], "volume": [1000]
    })
    regime = detect_regime(df)
    assert regime == MarketRegime.UNKNOWN
