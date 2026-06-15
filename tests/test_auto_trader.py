"""Tests for the autonomous trading engine."""

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from ai_trader.broker.paper import PaperBroker
from ai_trader.models.scanner import AutoTradeAction, ScanResult, ScanType
from ai_trader.risk.manager import RiskManager
from ai_trader.strategy.auto_trader import AutoTrader


def _make_df(n: int = 100, trend: str = "up", volume_spike: bool = False) -> pd.DataFrame:
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
    if volume_spike:
        volume[-1] = volume[:-1].mean() * 5

    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


@pytest.fixture
def auto_trader():
    broker = PaperBroker(initial_capital=100_000)
    risk = RiskManager()
    return AutoTrader(broker=broker, risk_manager=risk)


def test_auto_trader_init(auto_trader: AutoTrader):
    assert auto_trader.scan_results == []
    assert auto_trader.patterns == []
    assert auto_trader.trends == {}
    assert auto_trader.trade_log == []
    assert auto_trader.active_trades == {}


@patch("ai_trader.strategy.auto_trader.is_market_open", return_value=True)
def test_scan_market(mock_open, auto_trader: AutoTrader):
    market_data = {
        "RELIANCE": _make_df(100, "up"),
        "TCS": _make_df(100, "down"),
        "INFY": _make_df(100, "up", volume_spike=True),
    }
    results = auto_trader.scan_market(market_data)
    assert isinstance(results, list)
    # Should have trends for all symbols
    assert len(auto_trader.trends) == 3


@patch("ai_trader.strategy.auto_trader.is_market_open", return_value=False)
def test_scan_market_closed(mock_open, auto_trader: AutoTrader):
    market_data = {"RELIANCE": _make_df(100)}
    results = auto_trader.scan_market(market_data)
    assert results == []


@patch("ai_trader.strategy.auto_trader.is_market_open", return_value=True)
@patch("ai_trader.strategy.auto_trader.minutes_to_close", return_value=60)
def test_evaluate_and_trade(mock_close, mock_open, auto_trader: AutoTrader):
    market_data = {
        "RELIANCE": _make_df(100, "up"),
        "TCS": _make_df(100, "up", volume_spike=True),
    }
    logs = auto_trader.evaluate_and_trade(market_data)
    assert isinstance(logs, list)


def test_should_enter_low_score(auto_trader: AutoTrader):
    result = ScanResult(
        symbol="TEST", ltp=100, scan_type=ScanType.MOMENTUM, score=40,
        entry=100, stop_loss=95, target=110,
    )
    assert auto_trader._should_enter(result) is False


def test_should_enter_high_score(auto_trader: AutoTrader):
    result = ScanResult(
        symbol="TEST", ltp=100, scan_type=ScanType.MOMENTUM, score=85,
        entry=100, stop_loss=95, target=115,
    )
    # No trend data, should pass with high score
    assert auto_trader._should_enter(result) is True


def test_active_trades_property(auto_trader: AutoTrader):
    from ai_trader.strategy.auto_trader import _ActiveTrade
    auto_trader._active_trades["TEST"] = _ActiveTrade(
        symbol="TEST", side="BUY", entry=100, stop_loss=95,
        target=110, quantity=10, last_price=105,
    )
    trades = auto_trader.active_trades
    assert "TEST" in trades
    assert trades["TEST"]["pnl"] == 50.0  # (105-100)*10


def test_trade_log_entry(auto_trader: AutoTrader):
    auto_trader._log("TEST", AutoTradeAction.SCAN, "test scan")
    assert len(auto_trader.trade_log) == 1
    assert auto_trader.trade_log[0].action == AutoTradeAction.SCAN
