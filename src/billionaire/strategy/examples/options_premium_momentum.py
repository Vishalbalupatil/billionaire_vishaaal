"""Options premium momentum buy: when the underlying breaks out and ATM+1 OTM
option premium is accelerating, prefer buying the option leg."""

from __future__ import annotations

import numpy as np

from billionaire.models import SetupType, Signal, SignalDirection
from billionaire.strategy.base import BaseStrategy, StrategyContext


class OptionsPremiumMomentum(BaseStrategy):
    name = "options_premium_momentum"
    description = "Buy CE/PE when premium is accelerating WITH the underlying direction."
    min_bars = 40

    def evaluate(self, ctx: StrategyContext) -> Signal | None:
        snap = ctx.indicators
        close = ctx.ohlcv.close
        if len(close) < self.min_bars:
            return None

        # premium momentum = 5-bar slope positive and increasing
        slope5 = float(close[-1] - close[-5])
        slope10 = float(close[-1] - close[-10])
        if not (slope5 > 0 and slope5 > 0.6 * slope10):
            return None
        if snap.macd_hist <= 0 or snap.rsi < 55:
            return None

        last = float(close[-1])
        atr_ = snap.atr if snap.atr and not np.isnan(snap.atr) else max(0.5, last * 0.02)
        entry = last
        sl = entry - 1.0 * atr_
        t1 = entry + 1.5 * atr_
        t2 = entry + 3.0 * atr_
        rr = (t1 - entry) / max(entry - sl, 1e-9)

        return Signal(
            instrument=ctx.instrument,
            setup=SetupType.OPTION_BUYING,
            direction=SignalDirection.BULLISH,  # long premium = directional long on the leg
            entry=entry,
            stop_loss=sl,
            target1=t1,
            target2=t2,
            trailing_logic="Trail SL to 1R at T1; exit on theta-burn hour (last 45m).",
            confidence=0.5,
            reasons=[
                "Premium slope5 positive and accelerating vs slope10",
                f"MACD hist {snap.macd_hist:.3f} > 0, RSI {snap.rsi:.1f}",
            ],
            invalidation=[
                "Premium prints lower low within 3 bars",
                "Underlying reverses across ATM strike",
                "Intraday IV crush begins (pre-expiry 14:30+)",
            ],
            expected_rr=rr,
            strategy=self.name,
        )
