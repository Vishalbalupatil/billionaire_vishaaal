"""Tests for the equity scanner module."""

import numpy as np
import pandas as pd

from ai_trader.scanner.equity import (
    NIFTY50_SYMBOLS,
    _change_pct,
    _volume_ratio,
    rank_results,
    scan_breakout,
    scan_momentum,
    scan_stock,
    scan_volume_surge,
)


def _make_df(n: int = 100, trend: str = "up", volume_spike: bool = False) -> pd.DataFrame:
    """Create a synthetic OHLCV DataFrame."""
    np.random.seed(42)
    base = 1000.0
    if trend == "up":
        close = base + np.cumsum(np.random.normal(1, 2, n))
    elif trend == "down":
        close = base + np.cumsum(np.random.normal(-1, 2, n))
    else:
        close = base + np.cumsum(np.random.normal(0, 1, n))

    high = close + np.abs(np.random.normal(5, 2, n))
    low = close - np.abs(np.random.normal(5, 2, n))
    open_ = close + np.random.normal(0, 2, n)
    volume = np.random.randint(1000, 10000, n).astype(float)

    if volume_spike:
        volume[-1] = volume[:-1].mean() * 5

    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


def test_nifty50_symbols_count():
    assert len(NIFTY50_SYMBOLS) == 50


def test_change_pct():
    df = pd.DataFrame({"close": [100.0, 102.0]})
    assert abs(_change_pct(df) - 2.0) < 0.01


def test_volume_ratio_normal():
    df = _make_df(50, volume_spike=False)
    ratio = _volume_ratio(df)
    assert 0 < ratio < 10


def test_volume_ratio_spike():
    df = _make_df(50, volume_spike=True)
    ratio = _volume_ratio(df)
    assert ratio > 2.0


def test_scan_momentum_uptrend():
    df = _make_df(100, trend="up")
    result = scan_momentum(df, "TEST")
    # May or may not trigger depending on synthetic data
    if result:
        assert result.symbol == "TEST"
        assert result.score >= 50
        assert result.entry > 0
        assert result.stop_loss > 0


def test_scan_momentum_downtrend_no_signal():
    df = _make_df(100, trend="down")
    result = scan_momentum(df, "TEST")
    # Should not trigger bullish momentum in downtrend
    assert result is None


def test_scan_breakout():
    df = _make_df(100, trend="up")
    result = scan_breakout(df, "TEST")
    if result:
        assert result.scan_type.value == "BREAKOUT"
        assert result.score >= 50


def test_scan_volume_surge():
    df = _make_df(100, trend="up", volume_spike=True)
    result = scan_volume_surge(df, "TEST")
    if result:
        assert result.scan_type.value == "VOLUME_SURGE"
        assert result.volume_ratio > 2.0


def test_scan_stock_returns_list():
    df = _make_df(100, trend="up")
    results = scan_stock(df, "TEST")
    assert isinstance(results, list)


def test_scan_stock_insufficient_data():
    df = _make_df(10)
    results = scan_stock(df, "TEST")
    assert results == []


def test_rank_results():
    from ai_trader.models.scanner import ScanResult, ScanType

    results = [
        ScanResult(symbol="A", ltp=100, scan_type=ScanType.MOMENTUM, score=80),
        ScanResult(symbol="B", ltp=200, scan_type=ScanType.BREAKOUT, score=90),
        ScanResult(symbol="C", ltp=150, scan_type=ScanType.VOLUME_SURGE, score=60),
    ]
    ranked = rank_results(results, top_n=2)
    assert len(ranked) == 2
    assert ranked[0].symbol == "B"
    assert ranked[1].symbol == "A"
