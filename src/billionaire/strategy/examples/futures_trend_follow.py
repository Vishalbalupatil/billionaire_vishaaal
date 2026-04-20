"""Futures trend-follow: Supertrend + EMA50 slope + pullback entry."""

from __future__ import annotations

import numpy as np

from billionaire.models import MarketRegime, SetupType, Signal, SignalDirection
from billionaire.strategy.base import BaseStrategy, StrategyContext


class FuturesTrendFollow(BaseStrategy):
    name = "futures_trend_follow"
    description = "Trend-follow futures using Supertrend direction and EMA50 as bias filter."
    min_bars = 80

    def evaluate(self, ctx: StrategyContext) -> Signal | None:
        snap = ctx.indicators
        close = ctx.ohlcv.close
        if len(close) < self.min_bars:
            return None
        if ctx.regime not in (MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN):
            return None
        if snap.st_dir == 0:
            return None

        last = float(close[-1])
        atr_ = snap.atr if snap.atr and not np.isnan(snap.atr) else max(1.0, last * 0.003)

        bullish = snap.st_dir == 1 and last > snap.ema_trend and ctx.regime == MarketRegime.TRENDING_UP
        bearish = snap.st_dir == -1 and last < snap.ema_trend and ctx.regime == MarketRegime.TRENDING_DOWN
        if not (bullish or bearish):
            return None

        direction = SignalDirection.BULLISH if bullish else SignalDirection.BEARISH
        entry = last
        sl = entry - 1.5 * atr_ if bullish else entry + 1.5 * atr_
        t1 = entry + 2.0 * atr_ if bullish else entry - 2.0 * atr_
        t2 = entry + 4.0 * atr_ if bullish else entry - 4.0 * atr_
        rr = abs(t1 - entry) / max(abs(entry - sl), 1e-9)

        return Signal(
            instrument=ctx.instrument,
            setup=SetupType.TREND_CONTINUATION,
            direction=direction,
            entry=entry,
            stop_loss=sl,
            target1=t1,
            target2=t2,
            trailing_logic="Chandelier: trail stop at close - 2x ATR (long) / + 2x ATR (short).",
            confidence=0.55,
            reasons=[
                f"Supertrend={'up' if bullish else 'down'}",
                f"Price {'above' if bullish else 'below'} EMA50 ({snap.ema_trend:.2f})",
                f"Regime={ctx.regime.value}",
            ],
            invalidation=[
                "Supertrend flips",
                "Close on opposite side of EMA50",
            ],
            expected_rr=rr,
            strategy=self.name,
        )
