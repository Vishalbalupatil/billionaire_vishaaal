"""Walk-forward Opening Range Breakout backtester with combined
futures + options P&L.

Data contract (caller-supplied):
    * ``futures_bars``: 5-minute OHLCV bars of the front-month NIFTY future,
      chronological, naive IST timestamps. Covers 09:15-15:30 IST on every
      trading day in the backtest window.
    * ``spot_bars``: 5-minute OHLCV bars of the NIFTY 50 index, same grid.
      Used for ATM strike selection at the moment of break.
    * ``vix_bars``: 5-minute OHLCV bars of India VIX, same grid. Used as the
      Black-Scholes sigma input for the options leg.
    * ``expiry_schedule``: optional mapping date → last-Thursday expiry for
      each trading day. Defaults to last-Thursday-of-month (see
      :func:`billionaire.strategy.options_pricing.current_month_expiry`).

Output: :class:`ORBBacktestResult` with per-trade records, equity curve,
headline metrics. The result dataclass is JSON-serialisable via
:meth:`ORBBacktestResult.to_dict` so it can be persisted or shipped over
the API with no further work.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time
from typing import Any

from billionaire.strategy.options_pricing import (
    BSInputs,
    OptionType,
    atm_strike,
    current_month_expiry,
    price_call,
    price_put,
    vix_to_sigma,
    years_to_expiry,
)
from billionaire.strategy.orb import (
    Bar,
    BreakSide,
    ORBTrade,
    run_day,
)

log = logging.getLogger(__name__)

DEFAULT_SQUARE_OFF = time(15, 15)


@dataclass
class ORBBacktestTrade:
    """One day's trade with both futures and options legs priced."""

    date: str
    side: str  # "LONG" | "SHORT"
    # Opening range
    or_high: float
    or_low: float
    or_ts: str
    # Break
    entry_ts: str
    entry_price: float
    stop_price: float
    target_price: float
    # Exit
    exit_ts: str
    exit_price: float
    exit_reason: str  # "stop" | "target" | "eod"
    # Futures leg
    futures_pnl_points: float
    futures_pnl_pct: float
    futures_pnl_rupees: float  # points * lot_size
    # Options leg (BS-simulated)
    option_type: str  # "CE" | "PE"
    option_strike: int
    option_entry_premium: float
    option_exit_premium: float
    option_pnl_points: float  # per contract, premium delta
    option_pnl_rupees: float  # premium delta * lot_size
    vix_at_entry: float
    days_to_expiry: float  # in years, at entry
    # Combined
    combined_pnl_rupees: float
    r_multiple: float
    bars_held: int


@dataclass
class ORBMetrics:
    """Headline performance stats."""

    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    no_trade_days: int = 0
    win_rate_pct: float = 0.0
    avg_r_multiple: float = 0.0
    best_trade_rupees: float = 0.0
    worst_trade_rupees: float = 0.0
    total_pnl_rupees: float = 0.0
    futures_pnl_rupees: float = 0.0
    options_pnl_rupees: float = 0.0
    max_drawdown_rupees: float = 0.0
    sharpe_ratio: float = 0.0  # daily, annualised sqrt(252)


@dataclass
class ORBBacktestResult:
    trades: list[ORBBacktestTrade] = field(default_factory=list)
    equity_curve_combined: list[dict[str, Any]] = field(default_factory=list)
    equity_curve_futures: list[dict[str, Any]] = field(default_factory=list)
    equity_curve_options: list[dict[str, Any]] = field(default_factory=list)
    metrics: ORBMetrics = field(default_factory=ORBMetrics)
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trades": [asdict(t) for t in self.trades],
            "equity_curve_combined": self.equity_curve_combined,
            "equity_curve_futures": self.equity_curve_futures,
            "equity_curve_options": self.equity_curve_options,
            "metrics": asdict(self.metrics),
            "params": self.params,
        }


def _bars_by_day(bars: list[Bar]) -> dict[date, list[Bar]]:
    out: dict[date, list[Bar]] = defaultdict(list)
    for b in bars:
        out[b.ts.date()].append(b)
    return out


def _nearest_bar(bars: list[Bar], ts: datetime) -> Bar | None:
    """Find the bar whose timestamp is the largest <= ts. O(n) — acceptable
    since per-day bar counts are ~75."""
    best: Bar | None = None
    for b in bars:
        if b.ts <= ts:
            best = b
        else:
            break
    return best


def _max_drawdown(equity_curve: list[float]) -> float:
    peak = -float("inf")
    max_dd = 0.0
    for v in equity_curve:
        if v > peak:
            peak = v
        dd = peak - v
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _sharpe(daily_pnl: list[float], risk_free_rate: float = 0.0) -> float:
    """Annualised Sharpe from daily P&L. Zero-safe."""
    n = len(daily_pnl)
    if n < 2:
        return 0.0
    mean = sum(daily_pnl) / n
    var = sum((x - mean) ** 2 for x in daily_pnl) / (n - 1)
    std = var**0.5
    if std == 0:
        return 0.0
    # Annualise by sqrt(252) — standard assumption of 252 trading days.
    daily_sharpe = (mean - risk_free_rate) / std
    return daily_sharpe * (252.0**0.5)


def run_backtest(
    *,
    futures_bars: list[Bar],
    spot_bars: list[Bar],
    vix_bars: list[Bar],
    rr: float = 2.0,
    square_off_time: time = DEFAULT_SQUARE_OFF,
    futures_lot_size: int = 75,
    options_lot_size: int = 75,
    risk_free_rate: float = 0.075,
    dividend_yield: float = 0.013,
    fees_per_leg_rupees: float = 40.0,
) -> ORBBacktestResult:
    """Run the ORB strategy day-by-day across the provided bars.

    ``futures_lot_size``, ``options_lot_size`` default to 75 — NSE's current
    NIFTY lot size as of 2024-10. The fees figure (₹40 per leg) is a
    defensible intraday-broker approximation: Zerodha charges flat ₹20 +
    STT/stamp duty/GST which approximately stack to ~₹40 per executed leg
    on a ~₹15 lakh notional.
    """
    fut_by_day = _bars_by_day(futures_bars)
    spot_by_day = _bars_by_day(spot_bars)
    vix_by_day = _bars_by_day(vix_bars)

    trades: list[ORBBacktestTrade] = []
    equity_combined: list[dict[str, Any]] = []
    equity_futures: list[dict[str, Any]] = []
    equity_options: list[dict[str, Any]] = []

    cum_combined = 0.0
    cum_futures = 0.0
    cum_options = 0.0
    daily_pnl: list[float] = []
    no_trade_days = 0

    for trading_day in sorted(fut_by_day.keys()):
        day_bars = fut_by_day[trading_day]
        spot_day = spot_by_day.get(trading_day, [])
        vix_day = vix_by_day.get(trading_day, [])

        # Run the ORB on futures bars (futures is the tradable leg).
        orb_trade: ORBTrade | None = run_day(
            day_bars, rr=rr, square_off_time=square_off_time
        )
        if orb_trade is None:
            no_trade_days += 1
            equity_combined.append({"date": trading_day.isoformat(), "equity": cum_combined})
            equity_futures.append({"date": trading_day.isoformat(), "equity": cum_futures})
            equity_options.append({"date": trading_day.isoformat(), "equity": cum_options})
            daily_pnl.append(0.0)
            continue

        # --- Options leg: price ATM call/put at entry and exit using BS. ---
        entry_ts = orb_trade.break_.ts
        exit_ts = orb_trade.exit.ts

        spot_at_entry = _nearest_bar(spot_day, entry_ts)
        spot_at_exit = _nearest_bar(spot_day, exit_ts)
        vix_at_entry = _nearest_bar(vix_day, entry_ts)
        vix_at_exit = _nearest_bar(vix_day, exit_ts)

        # If any of spot/VIX is missing (data gap on that day), degrade
        # gracefully: futures-only trade, zero options P&L.
        if not (spot_at_entry and spot_at_exit and vix_at_entry and vix_at_exit):
            option_type = OptionType.CALL if orb_trade.side == BreakSide.LONG else OptionType.PUT
            strike = 0
            entry_premium = 0.0
            exit_premium = 0.0
            options_points = 0.0
            vix_value = 0.0
            tte_years = 0.0
        else:
            option_type = (
                OptionType.CALL
                if orb_trade.side == BreakSide.LONG
                else OptionType.PUT
            )
            strike = atm_strike(spot_at_entry.close)
            expiry = current_month_expiry(entry_ts)
            tte_entry = years_to_expiry(entry_ts, expiry)
            tte_exit = years_to_expiry(exit_ts, expiry)
            sigma_entry = vix_to_sigma(vix_at_entry.close)
            sigma_exit = vix_to_sigma(vix_at_exit.close)

            inp_entry = BSInputs(
                S=spot_at_entry.close, K=strike, T=tte_entry,
                sigma=sigma_entry, r=risk_free_rate, q=dividend_yield,
            )
            inp_exit = BSInputs(
                S=spot_at_exit.close, K=strike, T=tte_exit,
                sigma=sigma_exit, r=risk_free_rate, q=dividend_yield,
            )
            if option_type == OptionType.CALL:
                entry_premium = price_call(inp_entry).premium
                exit_premium = price_call(inp_exit).premium
            else:
                entry_premium = price_put(inp_entry).premium
                exit_premium = price_put(inp_exit).premium
            options_points = exit_premium - entry_premium
            vix_value = vix_at_entry.close
            tte_years = tte_entry

        # --- P&L aggregation per trade ---
        futures_pnl_rupees = (
            orb_trade.futures_pnl_points * futures_lot_size - fees_per_leg_rupees * 2
        )
        options_pnl_rupees = (
            options_points * options_lot_size - fees_per_leg_rupees * 2
        )
        combined_pnl_rupees = futures_pnl_rupees + options_pnl_rupees

        trades.append(
            ORBBacktestTrade(
                date=orb_trade.date,
                side=orb_trade.side.value,
                or_high=orb_trade.break_.stop_price
                if orb_trade.side == BreakSide.SHORT
                else orb_trade.break_.entry_price,
                or_low=orb_trade.break_.entry_price
                if orb_trade.side == BreakSide.SHORT
                else orb_trade.break_.stop_price,
                or_ts=(
                    entry_ts.replace(hour=9, minute=15, second=0, microsecond=0)
                    .isoformat()
                ),
                entry_ts=entry_ts.isoformat(),
                entry_price=orb_trade.break_.entry_price,
                stop_price=orb_trade.break_.stop_price,
                target_price=orb_trade.break_.target_price,
                exit_ts=exit_ts.isoformat(),
                exit_price=orb_trade.exit.price,
                exit_reason=orb_trade.exit.reason,
                futures_pnl_points=orb_trade.futures_pnl_points,
                futures_pnl_pct=orb_trade.futures_pnl_pct,
                futures_pnl_rupees=futures_pnl_rupees,
                option_type=option_type.value,
                option_strike=strike,
                option_entry_premium=entry_premium,
                option_exit_premium=exit_premium,
                option_pnl_points=options_points,
                option_pnl_rupees=options_pnl_rupees,
                vix_at_entry=vix_value,
                days_to_expiry=tte_years * 365.0,
                combined_pnl_rupees=combined_pnl_rupees,
                r_multiple=orb_trade.r_multiple,
                bars_held=orb_trade.bars_held,
            )
        )

        cum_combined += combined_pnl_rupees
        cum_futures += futures_pnl_rupees
        cum_options += options_pnl_rupees
        daily_pnl.append(combined_pnl_rupees)

        equity_combined.append({"date": trading_day.isoformat(), "equity": cum_combined})
        equity_futures.append({"date": trading_day.isoformat(), "equity": cum_futures})
        equity_options.append({"date": trading_day.isoformat(), "equity": cum_options})

    # ---- Aggregate metrics ----
    metrics = ORBMetrics()
    metrics.total_trades = len(trades)
    metrics.no_trade_days = no_trade_days
    if trades:
        wins = [t for t in trades if t.combined_pnl_rupees > 0]
        losses = [t for t in trades if t.combined_pnl_rupees <= 0]
        metrics.wins = len(wins)
        metrics.losses = len(losses)
        metrics.win_rate_pct = 100.0 * len(wins) / len(trades)
        metrics.avg_r_multiple = sum(t.r_multiple for t in trades) / len(trades)
        metrics.best_trade_rupees = max(t.combined_pnl_rupees for t in trades)
        metrics.worst_trade_rupees = min(t.combined_pnl_rupees for t in trades)
        metrics.total_pnl_rupees = sum(t.combined_pnl_rupees for t in trades)
        metrics.futures_pnl_rupees = sum(t.futures_pnl_rupees for t in trades)
        metrics.options_pnl_rupees = sum(t.option_pnl_rupees for t in trades)
        metrics.max_drawdown_rupees = _max_drawdown(
            [pt["equity"] for pt in equity_combined]
        )
        metrics.sharpe_ratio = _sharpe(daily_pnl)

    params = {
        "rr": rr,
        "square_off_time": square_off_time.isoformat(),
        "futures_lot_size": futures_lot_size,
        "options_lot_size": options_lot_size,
        "risk_free_rate": risk_free_rate,
        "dividend_yield": dividend_yield,
        "fees_per_leg_rupees": fees_per_leg_rupees,
    }

    return ORBBacktestResult(
        trades=trades,
        equity_curve_combined=equity_combined,
        equity_curve_futures=equity_futures,
        equity_curve_options=equity_options,
        metrics=metrics,
        params=params,
    )


def bars_from_cache(
    cache: Any,
    *,
    token: int,
    timeframe: str,
    from_ts: datetime,
    to_ts: datetime,
) -> list[Bar]:
    """Thin adapter: pull :class:`CachedBar` rows and convert to strategy
    :class:`~billionaire.strategy.orb.Bar`."""
    rows = cache.get_bars(token, timeframe, from_ts, to_ts)
    return [
        Bar(
            ts=r.ts,
            open=r.open,
            high=r.high,
            low=r.low,
            close=r.close,
            volume=r.volume,
        )
        for r in rows
    ]
