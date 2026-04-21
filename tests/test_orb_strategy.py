"""Unit tests for the pure-logic ORB strategy primitives."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from billionaire.strategy.orb import (
    Bar,
    BreakSide,
    find_first_break,
    find_opening_range,
    run_day,
    simulate_exit,
)


def _make_day_bars(
    *,
    or_high: float,
    or_low: float,
    trajectory: list[tuple[float, float, float, float]],
    base_date: datetime | None = None,
) -> list[Bar]:
    """Build a full trading day of 5m bars. ``trajectory`` is a list of
    (open, high, low, close) tuples for bars starting at 09:20 IST."""
    base = base_date or datetime(2024, 1, 2, 9, 15)
    bars: list[Bar] = [
        Bar(ts=base, open=or_low, high=or_high, low=or_low, close=(or_high + or_low) / 2)
    ]
    t = base + timedelta(minutes=5)
    for (o, h, lo, c) in trajectory:
        bars.append(Bar(ts=t, open=o, high=h, low=lo, close=c))
        t += timedelta(minutes=5)
    return bars


def test_find_opening_range_picks_first_0915_bar() -> None:
    bars = _make_day_bars(
        or_high=100.0, or_low=99.0,
        trajectory=[(99.5, 101.0, 99.5, 100.8)],
    )
    orr = find_opening_range(bars)
    assert orr is not None
    assert orr.high == 100.0
    assert orr.low == 99.0
    assert orr.ts.time() == time(9, 15)


def test_find_opening_range_returns_none_without_0915_bar() -> None:
    # Simulate a half-day where 09:15 bar is missing.
    bars = [
        Bar(ts=datetime(2024, 1, 2, 10, 0), open=100, high=101, low=99, close=100.5),
    ]
    assert find_opening_range(bars) is None


def test_long_break_takes_entry_at_orh() -> None:
    bars = _make_day_bars(
        or_high=100.0, or_low=99.0,
        trajectory=[
            (99.5, 99.9, 99.4, 99.8),     # inside range
            (99.8, 100.2, 99.7, 100.1),   # breaks ORH
        ],
    )
    orr = find_opening_range(bars)
    assert orr is not None
    br = find_first_break(orr, bars[1:], rr=2.0)
    assert br is not None
    assert br.side == BreakSide.LONG
    assert br.entry_price == 100.0  # entry at ORH, not bar close
    assert br.stop_price == 99.0
    assert br.target_price == 100.0 + 2.0 * (100.0 - 99.0)


def test_short_break_takes_entry_at_orl() -> None:
    bars = _make_day_bars(
        or_high=100.0, or_low=99.0,
        trajectory=[
            (99.5, 99.6, 99.1, 99.2),     # inside range
            (99.2, 99.3, 98.5, 98.7),     # breaks ORL
        ],
    )
    orr = find_opening_range(bars)
    assert orr is not None
    br = find_first_break(orr, bars[1:], rr=2.0)
    assert br is not None
    assert br.side == BreakSide.SHORT
    assert br.entry_price == 99.0
    assert br.stop_price == 100.0
    assert br.target_price == 99.0 - 2.0 * (100.0 - 99.0)


def test_no_break_returns_none() -> None:
    bars = _make_day_bars(
        or_high=100.0, or_low=99.0,
        trajectory=[
            (99.5, 99.9, 99.1, 99.5),
            (99.5, 99.95, 99.2, 99.4),
            (99.4, 99.8, 99.1, 99.3),
        ],
    )
    orr = find_opening_range(bars)
    assert orr is not None
    br = find_first_break(orr, bars[1:])
    assert br is None


def test_simultaneous_break_picks_side_closer_to_open() -> None:
    # Bar spans both ends of OR; open is closer to ORL → should go SHORT.
    bars = _make_day_bars(
        or_high=100.0, or_low=99.0,
        trajectory=[
            (99.1, 100.5, 98.5, 99.2),  # open 99.1 is closer to 99.0 than to 100.0
        ],
    )
    orr = find_opening_range(bars)
    assert orr is not None
    br = find_first_break(orr, bars[1:])
    assert br is not None
    assert br.side == BreakSide.SHORT


def test_exit_hits_stop_before_target_in_same_bar() -> None:
    # Long entry at 100, stop at 99, target at 102. A bar that spans 98 to 103
    # should be recorded as a STOP hit (pessimistic fill convention).
    bars = _make_day_bars(
        or_high=100.0, or_low=99.0,
        trajectory=[
            (99.8, 100.2, 99.7, 100.1),          # break bar (fills long at 100)
            (100.1, 103.0, 98.0, 101.0),         # wide bar — ambiguous fill
        ],
    )
    trade = run_day(bars)
    assert trade is not None
    assert trade.side == BreakSide.LONG
    assert trade.exit.reason == "stop"
    # Stop is at ORL = 99, so P&L = -1 point.
    assert trade.futures_pnl_points == -1.0


def test_exit_hits_target_cleanly() -> None:
    bars = _make_day_bars(
        or_high=100.0, or_low=99.0,
        trajectory=[
            (99.8, 100.2, 99.7, 100.1),  # break bar
            (100.1, 102.5, 100.0, 102.3),  # hits target (102.0) cleanly
        ],
    )
    trade = run_day(bars)
    assert trade is not None
    assert trade.exit.reason == "target"
    assert trade.futures_pnl_points == 2.0  # 100 → 102
    # With default rr=2.0, a target hit is +2R.
    assert trade.r_multiple == 2.0


def test_exit_squares_off_at_eod() -> None:
    # Long break at 10:00; no stop/target hit all day; 15:15 bar squares off.
    bars = [
        Bar(ts=datetime(2024, 1, 2, 9, 15), open=99.0, high=100.0, low=99.0, close=99.5),
    ]
    # Add bars through the day that stay in a narrow band above ORH.
    t = datetime(2024, 1, 2, 9, 20)
    # Break bar:
    bars.append(Bar(ts=t, open=99.8, high=100.2, low=99.7, close=100.1))
    t += timedelta(minutes=5)
    # Fill bars up to just before 15:15 IST that stay between 100.0 and 101.5
    # (no stop, no target since target is 102.0 from the +2R default).
    while t < datetime(2024, 1, 2, 15, 15):
        bars.append(Bar(ts=t, open=100.5, high=101.0, low=100.0, close=100.8))
        t += timedelta(minutes=5)
    # The 15:15 bar is the square-off trigger. Open is the fill.
    bars.append(Bar(ts=t, open=100.9, high=101.0, low=100.7, close=100.8))

    trade = run_day(bars)
    assert trade is not None
    assert trade.exit.reason == "eod"
    assert trade.exit.price == 100.9
    # P&L = 100.9 - 100 = 0.9
    assert abs(trade.futures_pnl_points - 0.9) < 1e-9


def test_doji_opening_range_returns_none() -> None:
    # ORH == ORL — no valid range, no trade.
    bars = [
        Bar(ts=datetime(2024, 1, 2, 9, 15), open=100.0, high=100.0, low=100.0, close=100.0),
        Bar(ts=datetime(2024, 1, 2, 9, 20), open=100.0, high=101.0, low=99.0, close=100.5),
    ]
    trade = run_day(bars)
    assert trade is None


def test_simulate_exit_runs_out_of_bars_closes_at_last_bar() -> None:
    from billionaire.strategy.orb import ORBBreak
    br = ORBBreak(
        side=BreakSide.LONG,
        ts=datetime(2024, 1, 2, 10, 0),
        entry_price=100.0, stop_price=99.0, target_price=102.0,
        bar_high=100.2, bar_low=99.7, bar_close=100.1,
    )
    bars_after = [
        Bar(ts=datetime(2024, 1, 2, 11, 0), open=100.5, high=100.8, low=100.2, close=100.6),
    ]
    exit = simulate_exit(br, bars_after)
    # No stop/target hit, and no bar at or past 15:15 → fallback is "eod" at last close.
    assert exit.reason == "eod"
    assert exit.price == 100.6
