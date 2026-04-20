"""Strategy base class & shared context object."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np

from billionaire.models import Instrument, MarketRegime, Signal
from billionaire.strategy.indicator_engine import IndicatorEngine, IndicatorSnapshot


@dataclass
class OHLCV:
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray

    def __len__(self) -> int:
        return len(self.close)


@dataclass
class StrategyContext:
    instrument: Instrument
    timeframe: str
    ohlcv: OHLCV
    indicators: IndicatorSnapshot
    regime: MarketRegime = MarketRegime.UNKNOWN
    params: dict = field(default_factory=dict)


class BaseStrategy(ABC):
    name: str = "base"
    description: str = ""
    min_bars: int = 60

    def __init__(self, params: dict | None = None) -> None:
        self.params: dict = dict(params or {})

    def prepare(self, ctx: StrategyContext) -> bool:
        """Return True if there's enough data to run."""
        return len(ctx.ohlcv) >= self.min_bars

    @abstractmethod
    def evaluate(self, ctx: StrategyContext) -> Signal | None: ...


def make_context(
    instrument: Instrument,
    timeframe: str,
    ohlcv: OHLCV,
    regime: MarketRegime = MarketRegime.UNKNOWN,
    params: dict | None = None,
    engine: IndicatorEngine | None = None,
) -> StrategyContext:
    eng = engine or IndicatorEngine()
    snap = eng.snapshot(ohlcv.open, ohlcv.high, ohlcv.low, ohlcv.close, ohlcv.volume)
    return StrategyContext(
        instrument=instrument,
        timeframe=timeframe,
        ohlcv=ohlcv,
        indicators=snap,
        regime=regime,
        params=dict(params or {}),
    )
