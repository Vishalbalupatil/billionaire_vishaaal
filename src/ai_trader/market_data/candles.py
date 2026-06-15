"""Candle builder — aggregates ticks into OHLCV bars."""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from datetime import datetime

from ai_trader.models.domain import Candle, Tick

log = logging.getLogger(__name__)

TIMEFRAME_MINUTES = {
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "15m": 15,
    "1h": 60,
}

MAX_CANDLES_PER_KEY = 240


class CandleBuilder:
    """Builds candles from a tick stream for multiple timeframes."""

    def __init__(self, timeframes: list[str] | None = None) -> None:
        self._timeframes = timeframes or ["1m", "5m", "15m"]
        self._buffers: dict[int, dict[str, _CandleAccumulator]] = defaultdict(
            lambda: {tf: _CandleAccumulator(tf) for tf in self._timeframes}
        )
        self._completed: dict[tuple[int, str], deque[Candle]] = defaultdict(
            lambda: deque(maxlen=MAX_CANDLES_PER_KEY)
        )

    def on_tick(self, tick: Tick) -> list[Candle]:
        """Process a tick and return any completed candles."""
        completed: list[Candle] = []
        for _tf, acc in self._buffers[tick.instrument_token].items():
            result = acc.add(tick)
            if result:
                completed.append(result)
                self._completed[(tick.instrument_token, acc.timeframe)].append(result)
        return completed

    def get_candles(self, instrument_token: int, timeframe: str, count: int = 100) -> list[Candle]:
        """Get recent completed candles for an instrument/timeframe."""
        buf = self._completed.get((instrument_token, timeframe))
        if not buf:
            return []
        items = list(buf)
        return items[-count:]


class _CandleAccumulator:
    def __init__(self, timeframe: str) -> None:
        self.timeframe = timeframe
        self._minutes = TIMEFRAME_MINUTES.get(timeframe, 1)
        self._current: Candle | None = None
        self._period_start: datetime | None = None

    def _bucket_start(self, ts: datetime) -> datetime:
        minutes = ts.hour * 60 + ts.minute
        bucket = (minutes // self._minutes) * self._minutes
        return ts.replace(hour=bucket // 60, minute=bucket % 60, second=0, microsecond=0)

    def add(self, tick: Tick) -> Candle | None:
        bucket = self._bucket_start(tick.ts)

        if self._current is None or bucket != self._period_start:
            completed = self._current
            self._current = Candle(
                instrument_token=tick.instrument_token,
                timeframe=self.timeframe,
                open=tick.ltp,
                high=tick.ltp,
                low=tick.ltp,
                close=tick.ltp,
                volume=tick.volume,
                oi=tick.oi,
                ts=bucket,
            )
            self._period_start = bucket
            return completed

        self._current = self._current.model_copy(update={
            "high": max(self._current.high, tick.ltp),
            "low": min(self._current.low, tick.ltp),
            "close": tick.ltp,
            "volume": self._current.volume + tick.volume,
            "oi": tick.oi,
        })
        return None
