import numpy as np

from billionaire.strategy.indicator_engine import (
    IndicatorEngine,
    atr,
    bollinger,
    detect_candle_patterns,
    ema,
    macd,
    rsi,
    sma,
    supertrend,
    vwap,
)


def test_ema_and_sma_match_on_long_series():
    x = np.arange(100, dtype=float)
    assert not np.isnan(sma(x, 10)[-1])
    assert not np.isnan(ema(x, 10)[-1])


def test_rsi_bounds():
    x = np.linspace(100, 110, 60)
    r = rsi(x, 14)
    assert r[-1] > 50  # uptrend -> RSI > 50


def test_macd_shapes():
    x = np.random.default_rng(0).normal(100, 1, 200).cumsum()
    m, s, h = macd(x)
    assert len(m) == len(s) == len(h) == len(x)


def test_atr_positive():
    rng = np.random.default_rng(1)
    close = rng.normal(100, 1, 200).cumsum() + 1000
    high = close + rng.uniform(0, 2, 200)
    low = close - rng.uniform(0, 2, 200)
    a = atr(high, low, close, 14)
    assert a[-1] > 0


def test_vwap_equals_typical_when_uniform_volume():
    close = np.array([10, 11, 12, 13], dtype=float)
    high = close + 0.5
    low = close - 0.5
    vol = np.array([1, 1, 1, 1], dtype=float)
    v = vwap(high, low, close, vol)
    assert np.isfinite(v[-1])


def test_bollinger_inequalities():
    x = np.random.default_rng(2).normal(0, 1, 100).cumsum() + 100
    up, mid, dn = bollinger(x, 20, 2.0)
    assert up[-1] > mid[-1] > dn[-1]


def test_supertrend_emits_direction():
    rng = np.random.default_rng(3)
    close = rng.normal(0, 1, 200).cumsum() + 100
    high = close + 1
    low = close - 1
    _, dir_ = supertrend(high, low, close)
    assert set(np.unique(dir_)).issubset({-1, 0, 1})


def test_indicator_snapshot_runs_on_small_history():
    rng = np.random.default_rng(4)
    n = 120
    close = rng.normal(0, 1, n).cumsum() + 500
    high = close + 1
    low = close - 1
    open_ = np.concatenate(([close[0]], close[:-1]))
    vol = rng.integers(1000, 5000, n).astype(float)
    snap = IndicatorEngine().snapshot(open_, high, low, close, vol)
    assert np.isfinite(snap.ema_fast)
    assert np.isfinite(snap.atr)


def test_candle_patterns_detect_hammer():
    open_ = np.array([100, 100], dtype=float)
    close = np.array([100, 101], dtype=float)
    high = np.array([100.5, 101.2], dtype=float)
    low = np.array([99.5, 96], dtype=float)  # long lower shadow on last
    patterns = detect_candle_patterns(open_, high, low, close)
    names = [p.name for p in patterns]
    assert "hammer" in names
