"""Tests for the feature engineering pipeline."""

import numpy as np
import pandas as pd

from ai_trader.ai.features import FEATURE_COLUMNS, build_features


def _make_candles(n: int = 200) -> pd.DataFrame:
    np.random.seed(42)
    prices = 22000 + np.cumsum(np.random.randn(n) * 10)
    return pd.DataFrame({
        "open": prices + np.random.randn(n) * 5,
        "high": prices + abs(np.random.randn(n) * 15),
        "low": prices - abs(np.random.randn(n) * 15),
        "close": prices,
        "volume": np.random.randint(1000, 50000, n),
    })


def test_build_features_shape():
    df = _make_candles()
    result = build_features(df)
    assert len(result) == len(df)


def test_all_feature_columns_present():
    df = _make_candles()
    result = build_features(df)
    for col in FEATURE_COLUMNS:
        assert col in result.columns, f"Missing column: {col}"


def test_rsi_range():
    df = _make_candles()
    result = build_features(df)
    rsi = result["rsi_14"].dropna()
    assert rsi.min() >= 0
    assert rsi.max() <= 100


def test_vix_feature():
    df = _make_candles()
    result = build_features(df, vix=25.0)
    assert (result["vix"] == 25.0).all()
    assert (result["vix_high"] == 1).all()


def test_pcr_feature():
    df = _make_candles()
    result = build_features(df, pcr=1.5)
    assert (result["pcr"] == 1.5).all()
    assert (result["pcr_bullish"] == 1).all()
