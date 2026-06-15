"""Tests for risk management."""

import os

os.environ["MAX_CAPITAL"] = "100000"
os.environ["MAX_DAILY_LOSS_PCT"] = "5"

from ai_trader.models.domain import (
    Exchange,
    Instrument,
    MarketRegime,
    Signal,
    SignalDirection,
)
from ai_trader.risk.manager import RiskManager


def _signal(confidence: float = 0.7, risk: float = 1000) -> Signal:
    return Signal(
        instrument=Instrument(instrument_token=0, tradingsymbol="NIFTY", exchange=Exchange.NSE),
        direction=SignalDirection.BULLISH,
        entry=22000,
        stop_loss=21960,
        target1=22080,
        confidence=confidence,
        regime=MarketRegime.TRENDING_UP,
        strategy_name="test",
        risk_rupees=risk,
    )


def test_can_trade_initially():
    rm = RiskManager()
    can, reason = rm.can_trade()
    assert can is True


def test_kill_switch():
    rm = RiskManager()
    rm.activate_kill_switch("test")
    assert rm.kill_switch_active
    can, _ = rm.can_trade()
    assert can is False

    rm.deactivate_kill_switch()
    assert not rm.kill_switch_active


def test_daily_loss_limit():
    rm = RiskManager()
    rm.update_daily_pnl(-6000)  # > 5% of 100k
    assert rm.kill_switch_active


def test_validate_signal():
    rm = RiskManager()
    sig = _signal(confidence=0.7, risk=1000)
    ok, _ = rm.validate_signal(sig, [])
    assert ok is True


def test_validate_signal_low_confidence():
    rm = RiskManager()
    sig = _signal(confidence=0.3)
    ok, reason = rm.validate_signal(sig, [])
    assert ok is False
    assert "Confidence" in reason


def test_reset_daily():
    rm = RiskManager()
    rm.update_daily_pnl(-6000)
    assert rm.kill_switch_active
    rm.reset_daily()
    assert not rm.kill_switch_active
    assert rm.daily_pnl == 0
