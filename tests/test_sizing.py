"""Tests for position sizing algorithms."""

from ai_trader.risk.sizing import fixed_fraction_size, kelly_fraction, options_lot_size


def test_fixed_fraction_basic():
    qty = fixed_fraction_size(
        capital=100000, risk_pct=2.0,
        entry=22000, stop_loss=21960, lot_size=25,
    )
    # Risk = 2000, per unit = 40, raw = 50, lots = 2 * 25 = 50
    assert qty == 50


def test_fixed_fraction_zero_risk():
    qty = fixed_fraction_size(
        capital=100000, risk_pct=2.0,
        entry=22000, stop_loss=22000, lot_size=25,
    )
    assert qty == 0


def test_kelly_basic():
    f = kelly_fraction(win_rate=0.6, avg_win=100, avg_loss=80)
    assert 0 < f < 0.25  # half-kelly capped at 25%


def test_kelly_losing():
    f = kelly_fraction(win_rate=0.3, avg_win=50, avg_loss=100)
    assert f == 0.0


def test_options_lot_size():
    lots = options_lot_size(
        capital=100000, max_premium_pct=3.0,
        premium_per_lot=500, lot_size=25,
    )
    # Max premium = 3000, per lot = 500, lots = 6
    assert lots == 6
