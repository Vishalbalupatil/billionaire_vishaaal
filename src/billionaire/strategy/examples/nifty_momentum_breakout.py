"""Nifty momentum breakout: break of N-bar high with volume + EMA stack."""

from __future__ import annotations

import numpy as np

from billionaire.models import MarketRegime, SetupType, Signal, SignalDirection
from billionaire.strategy.base import BaseStrategy, StrategyContext


class NiftyMomentumBreakout(BaseStrategy):
    name = "nifty_momentum_breakout"
    description = "Break of 20-bar high on Nifty with volume confirmation and EMA trend stack."
    min_bars = 60

    def evaluate(self, ctx: StrategyContext) -> Signal | None:
        h, c, v = ctx.ohlcv.high, ctx.ohlcv.close, ctx.ohlcv.volume
        snap = ctx.indicators
        lookback = int(self.params.get("lookback", 20))
        if len(c) < lookback + 5:
            return None

        prior_high = float(np.max(h[-lookback - 1 : -1]))
        last_close = float(c[-1])
        last_vol = float(v[-1]) if len(v) else 0
        avg_vol = float(np.nanmean(v[-lookback - 1 : -1])) if len(v) > lookback else 1.0

        if ctx.regime not in (MarketRegime.TRENDING_UP, MarketRegime.RANGE):
            return None
        if last_close <= prior_high * 1.0005:
            return None
        if snap.ema_fast < snap.ema_slow:
            return None
        if avg_vol > 0 and last_vol < 1.2 * avg_vol:
            return None

        atr_ = snap.atr if snap.atr and not np.isnan(snap.atr) else max(1.0, last_close * 0.002)
        entry = last_close
        sl = prior_high - 0.5 * atr_
        t1 = entry + 1.5 * atr_
        t2 = entry + 3.0 * atr_
        risk = entry - sl
        rr = (t1 - entry) / max(risk, 1e-9)

        return Signal(
            instrument=ctx.instrument,
            setup=SetupType.MOMENTUM_BREAKOUT,
            direction=SignalDirection.BULLISH,
            entry=entry,
            stop_loss=sl,
            target1=t1,
            target2=t2,
            trailing_logic="Trail SL to breakeven at T1, then 0.75x ATR chandelier.",
            confidence=0.55,
            reasons=[
                f"Close {last_close:.2f} > prior {lookback}-bar high {prior_high:.2f}",
                f"Volume {last_vol:.0f} > 1.2x avg {avg_vol:.0f}",
                f"EMA stack bullish (fast {snap.ema_fast:.2f} > slow {snap.ema_slow:.2f})",
            ],
            invalidation=[
                f"Close back below {prior_high:.2f} within 2 bars",
                "MACD histogram flips negative",
            ],
            expected_rr=rr,
            strategy=self.name,
        )
