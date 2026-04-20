"""Tick -> candle aggregator supporting multiple timeframes per instrument.

Emits a completed :class:`Candle` via ``on_candle`` callback every time a bucket
rolls over. Also exposes ``current_candle()`` for the live (incomplete) candle,
which the UI and intra-bar strategies can use.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from billionaire.models import Candle, Tick

# Supported timeframes -> seconds
TIMEFRAMES: dict[str, int] = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
}


def _bucket_start(ts: datetime, seconds: int) -> datetime:
    ts_utc = ts.astimezone(timezone.utc) if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    epoch = int(ts_utc.timestamp())
    floored = epoch - (epoch % seconds)
    return datetime.fromtimestamp(floored, tz=timezone.utc).replace(tzinfo=None)


class _BucketState:
    __slots__ = ("open", "high", "low", "close", "volume", "oi", "start")

    def __init__(self, price: float, volume: int, oi: int, start: datetime) -> None:
        self.open = price
        self.high = price
        self.low = price
        self.close = price
        self.volume = volume
        self.oi = oi
        self.start = start

    def update(self, price: float, volume: int, oi: int) -> None:
        if price > self.high:
            self.high = price
        if price < self.low:
            self.low = price
        self.close = price
        self.volume += volume
        if oi:
            self.oi = oi


OnCandle = Callable[[Candle], None]


class CandleBuilder:
    """Per-(token, timeframe) rolling candle state.

    Callbacks fire on bucket rollover. Thread-safe.
    """

    def __init__(
        self,
        timeframes: list[str] | None = None,
        on_candle: OnCandle | None = None,
    ) -> None:
        tfs = timeframes or list(TIMEFRAMES.keys())
        for tf in tfs:
            if tf not in TIMEFRAMES:
                raise ValueError(f"Unsupported timeframe: {tf}")
        self._tfs: dict[str, int] = {tf: TIMEFRAMES[tf] for tf in tfs}
        self._state: dict[tuple[int, str], _BucketState] = {}
        self._lock = threading.RLock()
        self._callbacks: list[OnCandle] = []
        if on_candle:
            self._callbacks.append(on_candle)

    def subscribe(self, cb: OnCandle) -> None:
        self._callbacks.append(cb)

    def _emit(self, candle: Candle) -> None:
        for cb in list(self._callbacks):
            try:
                cb(candle)
            except (RuntimeError, ValueError) as e:  # pragma: no cover
                # Never let a buggy subscriber stop the pipeline.
                import logging
                logging.getLogger(__name__).exception("candle callback error: %s", e)

    def on_tick(self, tick: Tick) -> list[Candle]:
        """Feed a tick; return list of newly-completed candles (if any)."""
        completed: list[Candle] = []
        with self._lock:
            for tf, seconds in self._tfs.items():
                key = (tick.instrument_token, tf)
                start = _bucket_start(tick.ts, seconds)
                state = self._state.get(key)
                if state is None:
                    self._state[key] = _BucketState(tick.ltp, tick.volume, tick.oi, start)
                    continue
                if start > state.start:
                    # rollover: emit previous bucket
                    candle = Candle(
                        instrument_token=tick.instrument_token,
                        timeframe=tf,
                        open=state.open,
                        high=state.high,
                        low=state.low,
                        close=state.close,
                        volume=state.volume,
                        oi=state.oi,
                        ts=state.start,
                    )
                    completed.append(candle)
                    self._state[key] = _BucketState(tick.ltp, tick.volume, tick.oi, start)
                else:
                    state.update(tick.ltp, tick.volume, tick.oi)
        for c in completed:
            self._emit(c)
        return completed

    def current_candle(self, token: int, timeframe: str) -> Candle | None:
        with self._lock:
            state = self._state.get((token, timeframe))
            if state is None:
                return None
            return Candle(
                instrument_token=token,
                timeframe=timeframe,
                open=state.open,
                high=state.high,
                low=state.low,
                close=state.close,
                volume=state.volume,
                oi=state.oi,
                ts=state.start,
            )

    def flush_stale(self, now: datetime | None = None) -> list[Candle]:
        """Emit & clear candles whose window has fully elapsed.

        Useful when no ticks arrive for a while (low-volume symbol) so the
        last bar is still published.
        """
        completed: list[Candle] = []
        current = now or datetime.utcnow()
        with self._lock:
            for (token, tf), state in list(self._state.items()):
                seconds = self._tfs[tf]
                if current - state.start >= timedelta(seconds=seconds):
                    completed.append(
                        Candle(
                            instrument_token=token,
                            timeframe=tf,
                            open=state.open,
                            high=state.high,
                            low=state.low,
                            close=state.close,
                            volume=state.volume,
                            oi=state.oi,
                            ts=state.start,
                        )
                    )
                    del self._state[(token, tf)]
        for c in completed:
            self._emit(c)
        return completed
