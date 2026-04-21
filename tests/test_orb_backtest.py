"""End-to-end tests for the ORB backtester with combined futures + options P&L."""

from __future__ import annotations

from datetime import datetime, timedelta

from billionaire.backtest.orb_backtest import run_backtest
from billionaire.strategy.orb import Bar


def _build_day(
    day: datetime,
    *,
    or_high: float,
    or_low: float,
    trajectory: list[tuple[float, float, float, float]],
) -> list[Bar]:
    """Build 5m bars for one trading day. trajectory = 09:20 onwards."""
    bars = [
        Bar(
            ts=day.replace(hour=9, minute=15),
            open=or_low, high=or_high, low=or_low, close=(or_high + or_low) / 2,
        )
    ]
    t = day.replace(hour=9, minute=20)
    for (o, h, lo, c) in trajectory:
        bars.append(Bar(ts=t, open=o, high=h, low=lo, close=c))
        t += timedelta(minutes=5)
    return bars


def _pad_to_eod(
    bars: list[Bar], *, day: datetime, steady_price: float
) -> list[Bar]:
    """Add steady-price bars from the last ts up through 15:15 so the
    EOD square-off branch is reachable without affecting stops/targets."""
    t = bars[-1].ts + timedelta(minutes=5)
    while t <= day.replace(hour=15, minute=20):
        bars.append(
            Bar(
                ts=t, open=steady_price, high=steady_price + 0.1,
                low=steady_price - 0.1, close=steady_price,
            )
        )
        t += timedelta(minutes=5)
    return bars


def _constant_vix_bars(days: list[datetime], vix_level: float) -> list[Bar]:
    """A flat-VIX dataset covering all bars in the given days, used by the
    options leg to get stable BS premia. VIX treated as a 'price'."""
    out: list[Bar] = []
    for d in days:
        t = d.replace(hour=9, minute=15)
        while t <= d.replace(hour=15, minute=30):
            out.append(Bar(ts=t, open=vix_level, high=vix_level, low=vix_level, close=vix_level))
            t += timedelta(minutes=5)
    return out


def test_backtest_single_winning_long_day() -> None:
    day = datetime(2024, 1, 2)
    fut_bars = _build_day(
        day,
        or_high=24_800.0, or_low=24_750.0,
        trajectory=[
            (24770, 24790, 24755, 24780),           # inside
            (24780, 24810, 24775, 24805),           # breaks ORH -> LONG entry at 24800
        ],
    )
    # Drive price up to target 24800 + 2*(24800-24750) = 24900 on a later bar.
    fut_bars.append(Bar(ts=day.replace(hour=9, minute=30), open=24_810,
                        high=24_905, low=24_810, close=24_895))
    fut_bars = _pad_to_eod(fut_bars, day=day, steady_price=24_895)

    spot_bars = fut_bars  # same grid for spot (good-enough approximation)
    vix_bars = _constant_vix_bars([day], vix_level=15.0)

    res = run_backtest(
        futures_bars=fut_bars, spot_bars=spot_bars, vix_bars=vix_bars,
        rr=2.0, futures_lot_size=75, options_lot_size=75,
        fees_per_leg_rupees=0.0,  # disable fees for clean math
    )
    assert res.metrics.total_trades == 1
    assert res.metrics.wins == 1
    trade = res.trades[0]
    assert trade.side == "LONG"
    assert trade.exit_reason == "target"
    # Target is exactly +2R => r_multiple == 2.0
    assert abs(trade.r_multiple - 2.0) < 1e-6
    # Target P&L in points = 100, * 75 lot = 7500
    assert abs(trade.futures_pnl_rupees - 7500.0) < 1e-6
    # Options leg P&L should be positive on a call going ITM on spot rising.
    assert trade.option_type == "CE"
    assert trade.option_strike == 24_800
    assert trade.option_pnl_rupees > 0


def test_backtest_single_losing_short_day_hits_stop() -> None:
    day = datetime(2024, 1, 2)
    fut_bars = _build_day(
        day,
        or_high=24_800.0, or_low=24_750.0,
        trajectory=[
            (24770, 24790, 24745, 24760),          # breaks ORL -> SHORT entry at 24750
            (24760, 24810, 24755, 24805),          # pulls back, hits stop at 24800
        ],
    )
    fut_bars = _pad_to_eod(fut_bars, day=day, steady_price=24_800)
    spot_bars = fut_bars
    vix_bars = _constant_vix_bars([day], vix_level=15.0)

    res = run_backtest(
        futures_bars=fut_bars, spot_bars=spot_bars, vix_bars=vix_bars,
        rr=2.0, fees_per_leg_rupees=0.0,
    )
    assert res.metrics.total_trades == 1
    assert res.metrics.losses == 1
    t = res.trades[0]
    assert t.side == "SHORT"
    assert t.exit_reason == "stop"
    # Risk is 50 points (24800-24750); stopped out at -1R.
    assert abs(t.r_multiple + 1.0) < 1e-6


def test_backtest_no_trade_day_counted_separately() -> None:
    """A day where price stays inside the OR all session should count as
    a 'no-trade' day, not as a losing trade."""
    day = datetime(2024, 1, 2)
    bars = _build_day(
        day,
        or_high=24_800.0, or_low=24_750.0,
        trajectory=[],
    )
    bars = _pad_to_eod(bars, day=day, steady_price=24_775)
    spot_bars = bars
    vix_bars = _constant_vix_bars([day], vix_level=15.0)

    res = run_backtest(
        futures_bars=bars, spot_bars=spot_bars, vix_bars=vix_bars,
    )
    assert res.metrics.total_trades == 0
    assert res.metrics.no_trade_days == 1


def test_backtest_equity_curves_align_and_sum() -> None:
    """combined equity must equal futures equity + options equity at each
    point. This is an invariant of how we aggregate P&L."""
    day = datetime(2024, 1, 2)
    fut_bars = _build_day(
        day,
        or_high=24_800.0, or_low=24_750.0,
        trajectory=[(24780, 24810, 24775, 24805)],
    )
    fut_bars.append(Bar(ts=day.replace(hour=9, minute=30),
                        open=24_810, high=24_905, low=24_810, close=24_895))
    fut_bars = _pad_to_eod(fut_bars, day=day, steady_price=24_895)
    vix_bars = _constant_vix_bars([day], vix_level=15.0)

    res = run_backtest(
        futures_bars=fut_bars, spot_bars=fut_bars, vix_bars=vix_bars,
        fees_per_leg_rupees=0.0,
    )
    assert len(res.equity_curve_combined) == len(res.equity_curve_futures)
    for c, f, o in zip(
        res.equity_curve_combined, res.equity_curve_futures, res.equity_curve_options,
        strict=True,
    ):
        assert c["date"] == f["date"] == o["date"]
        assert abs(c["equity"] - (f["equity"] + o["equity"])) < 1e-6


def test_backtest_fees_deducted_from_both_legs() -> None:
    """Non-zero fees must reduce both futures and options P&L."""
    day = datetime(2024, 1, 2)
    fut_bars = _build_day(
        day,
        or_high=24_800.0, or_low=24_750.0,
        trajectory=[(24780, 24810, 24775, 24805)],
    )
    fut_bars.append(Bar(ts=day.replace(hour=9, minute=30),
                        open=24_810, high=24_905, low=24_810, close=24_895))
    fut_bars = _pad_to_eod(fut_bars, day=day, steady_price=24_895)
    vix_bars = _constant_vix_bars([day], vix_level=15.0)

    zero_fee = run_backtest(
        futures_bars=fut_bars, spot_bars=fut_bars, vix_bars=vix_bars,
        fees_per_leg_rupees=0.0,
    )
    with_fee = run_backtest(
        futures_bars=fut_bars, spot_bars=fut_bars, vix_bars=vix_bars,
        fees_per_leg_rupees=40.0,
    )
    # Two legs * (entry + exit) = 4 fee deductions of 40 = -160.
    expected_delta = -160.0
    assert abs(
        with_fee.metrics.total_pnl_rupees - zero_fee.metrics.total_pnl_rupees - expected_delta
    ) < 1e-6
