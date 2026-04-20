"""Equity intraday breakout: opening range break with VWAP filter."""

from __future__ import annotations

import numpy as np

from billionaire.models import SetupType, Signal, SignalDirection
from billionaire.strategy.base import BaseStrategy, StrategyContext


class EquityIntradayBreakout(BaseStrategy):
    name = "equity_intraday_breakout"
    description = "Break of first-N-bars opening range, close above/below VWAP."
    min_bars = 20

    def evaluate(self, ctx: StrategyContext) -> Signal | None:
        snap = ctx.indicators
        high = ctx.ohlcv.high
        low = ctx.ohlcv.low
        close = ctx.ohlcv.close
        n_open = int(self.params.get("opening_range_bars", 3))
        if len(close) < self.min_bars or len(close) < n_open + 2:
            return None

        orh = float(np.max(high[:n_open]))
        orl = float(np.min(low[:n_open]))
        last = float(close[-1])

        bullish = last > orh and not np.isnan(snap.vwap) and last >= snap.vwap
        bearish = last < orl and not np.isnan(snap.vwap) and last <= snap.vwap
        if not (bullish or bearish):
            return None

        direction = SignalDirection.BULLISH if bullish else SignalDirection.BEARISH
        atr_ = snap.atr if snap.atr and not np.isnan(snap.atr) else max(0.5, last * 0.004)
        entry = last
        sl = orh - 0.3 * atr_ if bearish else orl + 0.3 * atr_
        t1 = entry + 2 * atr_ if bullish else entry - 2 * atr_
        t2 = entry + 3.5 * atr_ if bullish else entry - 3.5 * atr_
        rr = abs(t1 - entry) / max(abs(entry - sl), 1e-9)

        return Signal(
            instrument=ctx.instrument,
            setup=SetupType.EQUITY_INTRADAY,
            direction=direction,
            entry=entry,
            stop_loss=sl,
            target1=t1,
            target2=t2,
            trailing_logic="1R trailing stop after T1 hit.",
            confidence=0.5,
            reasons=[
                f"ORH/ORL ({orh:.2f}/{orl:.2f}) broken",
                f"Price {('above' if bullish else 'below')} VWAP {snap.vwap:.2f}",
            ],
            invalidation=[
                "Close back inside opening range",
                "VWAP retake in the opposite direction",
            ],
            expected_rr=rr,
            strategy=self.name,
        )
