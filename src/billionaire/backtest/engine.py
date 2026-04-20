"""Bar-by-bar backtest engine that re-uses the live SignalEngine and PaperBroker.

Pipeline: for each bar i:
    1. Build OHLCV window [0..i]
    2. Mark-to-market any open positions (PaperBroker.on_ltp)
    3. Run SignalEngine on the window — pick top signal above threshold
    4. If no open position for this instrument, place MARKET order via paper broker
    5. Manage open position: SL / target / trailing logic evaluated on the bar

Results: per-trade P&L, aggregate metrics, equity curve.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np

from billionaire.backtest.metrics import PerformanceMetrics, performance_metrics
from billionaire.execution.paper_broker import PaperBroker
from billionaire.models import (
    Instrument,
    OrderRequest,
    OrderType,
    ProductType,
    Side,
    Signal,
    SignalDirection,
)
from billionaire.strategy.base import OHLCV
from billionaire.strategy.signal_engine import SignalEngine

log = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    symbol: str
    strategy: str
    direction: str
    entry: float
    exit: float
    qty: int
    pnl: float
    bars_held: int
    reason: str
    entry_ts: str
    exit_ts: str


@dataclass
class BacktestResult:
    trades: list[BacktestTrade] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    metrics: PerformanceMetrics | None = None
    per_strategy: dict[str, PerformanceMetrics] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trades": [t.__dict__ for t in self.trades],
            "equity_curve": self.equity_curve,
            "metrics": self.metrics.__dict__ if self.metrics else {},
            "per_strategy": {k: v.__dict__ for k, v in self.per_strategy.items()},
        }


class BacktestEngine:
    def __init__(
        self,
        engine: SignalEngine,
        warmup_bars: int = 60,
        confidence_threshold: float = 0.45,
        qty: int = 1,
    ) -> None:
        self.engine = engine
        self.warmup_bars = warmup_bars
        self.confidence_threshold = confidence_threshold
        self.qty = qty

    def run(self, instrument: Instrument, timeframe: str, ohlcv: OHLCV, timestamps: list[datetime] | None = None) -> BacktestResult:
        result = BacktestResult()
        broker = PaperBroker()
        pnls: list[float] = []
        open_trade: dict[str, Any] | None = None
        equity = 0.0

        n = len(ohlcv.close)
        for i in range(self.warmup_bars, n):
            window = OHLCV(
                open=ohlcv.open[: i + 1],
                high=ohlcv.high[: i + 1],
                low=ohlcv.low[: i + 1],
                close=ohlcv.close[: i + 1],
                volume=ohlcv.volume[: i + 1],
            )
            price = float(ohlcv.close[i])
            bar_high = float(ohlcv.high[i])
            bar_low = float(ohlcv.low[i])
            ts = timestamps[i] if timestamps and i < len(timestamps) else datetime.utcnow()
            broker.on_ltp(instrument.instrument_token, price)

            # 1) manage open trade
            if open_trade is not None:
                open_trade["bars_held"] += 1
                direction = open_trade["direction"]
                sl = open_trade["sl"]
                t1 = open_trade["t1"]
                t2 = open_trade["t2"]
                exit_price = None
                exit_reason = ""
                if direction == "BULLISH":
                    if bar_low <= sl:
                        exit_price, exit_reason = sl, "stop"
                    elif bar_high >= (t2 or 1e18):
                        exit_price, exit_reason = t2, "target2"
                    elif bar_high >= t1 and not open_trade.get("t1_hit"):
                        open_trade["t1_hit"] = True
                        open_trade["sl"] = open_trade["entry"]  # move to BE
                else:
                    if bar_high >= sl:
                        exit_price, exit_reason = sl, "stop"
                    elif bar_low <= (t2 or -1e18):
                        exit_price, exit_reason = t2, "target2"
                    elif bar_low <= t1 and not open_trade.get("t1_hit"):
                        open_trade["t1_hit"] = True
                        open_trade["sl"] = open_trade["entry"]

                # force exit at end of series
                if exit_price is None and i == n - 1:
                    exit_price, exit_reason = price, "eos"

                if exit_price is not None:
                    qty = open_trade["qty"]
                    sign = 1 if direction == "BULLISH" else -1
                    pnl = (exit_price - open_trade["entry"]) * qty * sign
                    pnls.append(pnl)
                    equity += pnl
                    result.trades.append(
                        BacktestTrade(
                            symbol=instrument.tradingsymbol,
                            strategy=open_trade["strategy"],
                            direction=direction,
                            entry=open_trade["entry"],
                            exit=exit_price,
                            qty=qty,
                            pnl=round(pnl, 2),
                            bars_held=open_trade["bars_held"],
                            reason=exit_reason,
                            entry_ts=open_trade["entry_ts"],
                            exit_ts=ts.isoformat(),
                        )
                    )
                    result.equity_curve.append(round(equity, 2))
                    open_trade = None

            # 2) look for new signal if flat
            if open_trade is None:
                signals: list[Signal] = self.engine.run(instrument=instrument, timeframe=timeframe, ohlcv=window)
                if signals and signals[0].confidence >= self.confidence_threshold:
                    sig = signals[0]
                    side = Side.BUY if sig.direction == SignalDirection.BULLISH else Side.SELL
                    broker.place_order(
                        OrderRequest(
                            instrument=instrument,
                            side=side,
                            quantity=self.qty,
                            order_type=OrderType.MARKET,
                            product=ProductType.MIS,
                            tag=sig.strategy[:20],
                        )
                    )
                    open_trade = {
                        "strategy": sig.strategy,
                        "direction": sig.direction.value,
                        "entry": price,
                        "sl": sig.stop_loss,
                        "t1": sig.target1,
                        "t2": sig.target2,
                        "qty": self.qty,
                        "bars_held": 0,
                        "entry_ts": ts.isoformat(),
                    }

        result.metrics = performance_metrics(pnls)
        # per-strategy breakdown
        by_strat: dict[str, list[float]] = {}
        for t in result.trades:
            by_strat.setdefault(t.strategy, []).append(t.pnl)
        result.per_strategy = {k: performance_metrics(v) for k, v in by_strat.items()}
        return result

    @staticmethod
    def synthetic_ohlcv(n: int = 500, seed: int = 7) -> OHLCV:
        """Generate a synthetic OHLCV series for smoke-testing strategies."""
        rng = np.random.default_rng(seed)
        drift = 0.0002
        vol = 0.012
        rets = rng.normal(drift, vol, size=n)
        close = 1000 * np.exp(np.cumsum(rets))
        open_ = np.concatenate(([close[0]], close[:-1]))
        noise_h = np.abs(rng.normal(0, vol / 2, size=n)) * close
        noise_l = np.abs(rng.normal(0, vol / 2, size=n)) * close
        high = np.maximum(open_, close) + noise_h
        low = np.minimum(open_, close) - noise_l
        volume = rng.integers(10_000, 200_000, size=n)
        return OHLCV(open=open_, high=high, low=low, close=close, volume=volume.astype(float))
