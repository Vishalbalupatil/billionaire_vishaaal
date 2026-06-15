"""Tests for the AI ensemble model."""

import numpy as np
import pandas as pd

from ai_trader.ai.features import build_features
from ai_trader.ai.model import EnsembleModel


def _make_features() -> pd.DataFrame:
    np.random.seed(42)
    n = 200
    prices = 22000 + np.cumsum(np.random.randn(n) * 10)
    df = pd.DataFrame({
        "open": prices + np.random.randn(n) * 5,
        "high": prices + abs(np.random.randn(n) * 15),
        "low": prices - abs(np.random.randn(n) * 15),
        "close": prices,
        "volume": np.random.randint(1000, 50000, n),
    })
    return build_features(df)


def test_model_predict_rule_based():
    model = EnsembleModel()
    assert not model.is_trained

    features = _make_features()
    direction, confidence = model.predict(features)
    assert direction in (-1, 0, 1)
    assert 0.0 <= confidence <= 1.0


def test_model_predict_empty():
    model = EnsembleModel()
    direction, confidence = model.predict(pd.DataFrame())
    assert direction == 0
    assert confidence == 0.0
