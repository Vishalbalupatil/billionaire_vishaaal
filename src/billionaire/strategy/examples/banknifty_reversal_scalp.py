"""Bank Nifty reversal scalp: extreme RSI + bullish/bearish candle pattern at S/R."""

from __future__ import annotations

import numpy as np

from billionaire.models import MarketRegime, SetupType, Signal, SignalDirection
from billionaire.strategy.base import BaseStrategy, StrategyContext


class BankNiftyReversalScalp(BaseStrategy):
    name = "banknifty_reversal_scalp"
    description = "Short-timeframe reversal scalp on Bank Nifty at extreme RSI with candle confirmation."
    min_bars = 40

    def evaluate(self, ctx: StrategyContext) -> Signal | None:
        snap = ctx.indicators
        close = ctx.ohlcv.close
        if len(close) < self.min_bars:
            return None
        if ctx.regime == MarketRegime.TRENDING_UP and snap.rsi < 60:
            return None
        if ctx.regime == MarketRegime.TRENDING_DOWN and snap.rsi > 40:
            return None

        last = float(close[-1])
        atr_ = snap.atr if snap.atr and not np.isnan(snap.atr) else max(1.0, last * 0.003)

        bullish = snap.rsi <= 28 and any(p.bullish for p in snap.patterns)
        bearish = snap.rsi >= 72 and any(not p.bullish for p in snap.patterns)
        if not (bullish or bearish):
            return None

        direction = SignalDirection.BULLISH if bullish else SignalDirection.BEARISH
        entry = last
        sl = entry - 1.2 * atr_ if bullish else entry + 1.2 * atr_
        t1 = entry + 1.5 * atr_ if bullish else entry - 1.5 * atr_
        t2 = entry + 2.5 * atr_ if bullish else entry - 2.5 * atr_
        rr = abs(t1 - entry) / max(abs(entry - sl), 1e-9)

        return Signal(
            instrument=ctx.instrument,
            setup=SetupType.REVERSAL,
            direction=direction,
            entry=entry,
            stop_loss=sl,
            target1=t1,
            target2=t2,
            trailing_logic="Move SL to entry at T1, exit full at T2 or EMA20 cross.",
            confidence=0.45,
            reasons=[
                f"RSI at {snap.rsi:.1f} — extreme",
                "Reversal candle pattern printed",
                f"Regime={ctx.regime.value}",
            ],
            invalidation=[
                "Next candle closes beyond SL",
                "RSI returns past 50 without follow-through",
            ],
            expected_rr=rr,
            strategy=self.name,
        )
