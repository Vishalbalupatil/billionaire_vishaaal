"""Signal engine orchestrator.

Decides which strategies to run, classifies the market regime, scores each
candidate signal, filters by risk/reward, and returns a ranked list.

Scoring is deliberately explainable — no black-box ML. The layered score is:

    score = base_confidence
          + 0.15 if regime aligns with direction
          + 0.10 if indicator stack agrees (EMA/MACD/RSI/VWAP)
          + 0.05 if recent candle pattern supports direction
          - 0.20 if RR < 1.3
          - 0.10 if we're in a ``VOLATILE`` regime and using mean-reversion

Values clipped to [0, 1]. ML-ready: a learned scorer can be dropped in place
of `_score()` as long as it returns [0,1].
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from billionaire.models import MarketRegime, Signal, SignalDirection
from billionaire.strategy.base import OHLCV, BaseStrategy, StrategyContext, make_context

log = logging.getLogger(__name__)


@dataclass
class RegimeClassifier:
    trend_threshold: float = 0.6  # EMA alignment proportion
    vol_z_threshold: float = 1.5  # ATR z-score

    def classify(self, ohlcv: OHLCV) -> MarketRegime:
        close = ohlcv.close
        if len(close) < 50:
            return MarketRegime.UNKNOWN

        # trend via EMA20 vs EMA50 slope
        from billionaire.strategy.indicator_engine import atr, ema

        e20 = ema(close, 20)
        e50 = ema(close, 50)
        if np.isnan(e50[-1]):
            return MarketRegime.UNKNOWN

        slope20 = e20[-1] - e20[-10]
        above = float(np.nanmean((e20 > e50).astype(float)))

        atr_series = atr(ohlcv.high, ohlcv.low, ohlcv.close, 14)
        atr_now = atr_series[-1]
        atr_mean = float(np.nanmean(atr_series[-50:])) if len(atr_series) >= 50 else atr_now
        atr_std = float(np.nanstd(atr_series[-50:])) if len(atr_series) >= 50 else 1.0
        vol_z = (atr_now - atr_mean) / (atr_std + 1e-9)

        if vol_z > self.vol_z_threshold:
            return MarketRegime.VOLATILE
        if above > self.trend_threshold and slope20 > 0:
            return MarketRegime.TRENDING_UP
        if (1 - above) > self.trend_threshold and slope20 < 0:
            return MarketRegime.TRENDING_DOWN
        if abs(vol_z) < 0.5 and abs(slope20) < atr_now * 0.25:
            return MarketRegime.QUIET
        return MarketRegime.RANGE


class SignalEngine:
    def __init__(self, strategies: list[BaseStrategy] | None = None) -> None:
        self.strategies: list[BaseStrategy] = list(strategies or [])
        self.regime_clf = RegimeClassifier()

    def register(self, strategy: BaseStrategy) -> None:
        self.strategies.append(strategy)

    def classify_regime(self, ohlcv: OHLCV) -> MarketRegime:
        return self.regime_clf.classify(ohlcv)

    def run(
        self,
        *,
        instrument,
        timeframe: str,
        ohlcv: OHLCV,
        params: dict | None = None,
    ) -> list[Signal]:
        regime = self.classify_regime(ohlcv)
        ctx = make_context(instrument, timeframe, ohlcv, regime=regime, params=params)
        signals: list[Signal] = []
        for strat in self.strategies:
            try:
                if not strat.prepare(ctx):
                    continue
                sig = strat.evaluate(ctx)
                if sig is None:
                    continue
                sig.regime = regime
                sig.confidence = self._score(sig, ctx)
                signals.append(sig)
            except (RuntimeError, ValueError, KeyError) as e:
                log.exception("strategy %s failed: %s", strat.name, e)
        # Rank by confidence desc
        signals.sort(key=lambda s: s.confidence, reverse=True)
        return signals

    @staticmethod
    def _score(sig: Signal, ctx: StrategyContext) -> float:
        conf = max(0.0, min(1.0, sig.confidence or 0.5))
        snap = ctx.indicators
        # regime alignment
        if sig.direction == SignalDirection.BULLISH and ctx.regime == MarketRegime.TRENDING_UP or sig.direction == SignalDirection.BEARISH and ctx.regime == MarketRegime.TRENDING_DOWN:
            conf += 0.15
        # indicator stack
        stack_agree = 0
        if sig.direction == SignalDirection.BULLISH:
            if not np.isnan(snap.ema_fast) and not np.isnan(snap.ema_slow) and snap.ema_fast > snap.ema_slow:
                stack_agree += 1
            if snap.macd_hist > 0:
                stack_agree += 1
            if 40 <= snap.rsi <= 70:
                stack_agree += 1
            if not np.isnan(snap.vwap) and sig.entry >= snap.vwap:
                stack_agree += 1
        elif sig.direction == SignalDirection.BEARISH:
            if not np.isnan(snap.ema_fast) and not np.isnan(snap.ema_slow) and snap.ema_fast < snap.ema_slow:
                stack_agree += 1
            if snap.macd_hist < 0:
                stack_agree += 1
            if 30 <= snap.rsi <= 60:
                stack_agree += 1
            if not np.isnan(snap.vwap) and sig.entry <= snap.vwap:
                stack_agree += 1
        conf += 0.025 * stack_agree  # up to +0.10

        # candle patterns
        for p in snap.patterns:
            if (sig.direction == SignalDirection.BULLISH and p.bullish) or (
                sig.direction == SignalDirection.BEARISH and not p.bullish
            ):
                conf += 0.05 * p.strength
                break

        # RR filter
        if sig.expected_rr and sig.expected_rr < 1.3:
            conf -= 0.20

        # volatile regime penalty for mean-reversion
        if ctx.regime == MarketRegime.VOLATILE and sig.setup.value.startswith("MEAN"):
            conf -= 0.10

        return max(0.0, min(1.0, conf))
