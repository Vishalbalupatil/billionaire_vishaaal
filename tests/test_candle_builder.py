from datetime import datetime, timedelta

from billionaire.marketdata.candle_builder import CandleBuilder
from billionaire.models import Tick


def _tick(price: float, ts: datetime, token: int = 1, volume: int = 10) -> Tick:
    return Tick(instrument_token=token, ltp=price, volume=volume, ts=ts)


def test_candle_rollover_emits_completed_bar():
    cb = CandleBuilder(timeframes=["1m"])
    start = datetime(2025, 1, 1, 9, 15, 0)
    # ticks within first minute
    cb.on_tick(_tick(100, start))
    cb.on_tick(_tick(101, start + timedelta(seconds=30)))
    # tick in next minute -> rollover
    completed = cb.on_tick(_tick(102, start + timedelta(seconds=61)))
    assert len(completed) == 1
    c = completed[0]
    assert c.open == 100 and c.close == 101 and c.high == 101 and c.low == 100
    assert c.timeframe == "1m"


def test_current_candle_live_view():
    cb = CandleBuilder(timeframes=["1m"])
    start = datetime(2025, 1, 1, 9, 15, 0)
    cb.on_tick(_tick(100, start))
    cb.on_tick(_tick(99, start + timedelta(seconds=15)))
    cur = cb.current_candle(1, "1m")
    assert cur is not None
    assert cur.low == 99 and cur.high == 100


def test_multiple_timeframes():
    cb = CandleBuilder(timeframes=["1m", "5m"])
    start = datetime(2025, 1, 1, 9, 15, 0)
    for i in range(10):
        cb.on_tick(_tick(100 + i, start + timedelta(seconds=i * 30)))
    # After 5 minutes, the 5m candle should still be forming or just closed once
    cur5 = cb.current_candle(1, "5m")
    cur1 = cb.current_candle(1, "1m")
    assert cur5 is not None
    assert cur1 is not None
