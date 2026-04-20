"""Pure-NumPy technical indicator engine.

No third-party TA library dependency (keeps installs lean and portable).
All functions take a 1-D ``numpy.ndarray`` of floats and return a same-length
array — NaN-padded at the head until there is enough history.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def ema(values: np.ndarray, period: int) -> np.ndarray:
    if len(values) == 0:
        return values.copy()
    alpha = 2.0 / (period + 1)
    out = np.full_like(values, np.nan, dtype=float)
    # seed with SMA of first `period`
    if len(values) >= period:
        out[period - 1] = float(np.mean(values[:period]))
        for i in range(period, len(values)):
            out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


def sma(values: np.ndarray, period: int) -> np.ndarray:
    if len(values) < period:
        return np.full_like(values, np.nan, dtype=float)
    out = np.full_like(values, np.nan, dtype=float)
    cumsum = np.cumsum(np.insert(values, 0, 0.0))
    out[period - 1 :] = (cumsum[period:] - cumsum[:-period]) / period
    return out


def rsi(values: np.ndarray, period: int = 14) -> np.ndarray:
    out = np.full_like(values, np.nan, dtype=float)
    if len(values) <= period:
        return out
    deltas = np.diff(values)
    gains = np.clip(deltas, 0, None)
    losses = -np.clip(deltas, None, 0)
    avg_gain = float(np.mean(gains[:period]))
    avg_loss = float(np.mean(losses[:period]))
    for i in range(period, len(values)):
        if i > period:
            avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
        if avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100 - (100 / (1 + rs))
    return out


def macd(
    values: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ema_fast = ema(values, fast)
    ema_slow = ema(values, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(np.nan_to_num(macd_line, nan=0.0), signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    if len(close) == 0:
        return close.copy()
    prev_close = np.concatenate(([close[0]], close[:-1]))
    tr = np.maximum.reduce([high - low, np.abs(high - prev_close), np.abs(low - prev_close)])
    out = np.full_like(close, np.nan, dtype=float)
    if len(close) >= period:
        out[period - 1] = float(np.mean(tr[:period]))
        for i in range(period, len(close)):
            out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def vwap(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray
) -> np.ndarray:
    typical = (high + low + close) / 3.0
    pv = typical * volume
    cum_pv = np.cumsum(pv)
    cum_v = np.cumsum(volume)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(cum_v > 0, cum_pv / cum_v, np.nan)
    return out


def bollinger(values: np.ndarray, period: int = 20, mult: float = 2.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mid = sma(values, period)
    out_up = np.full_like(values, np.nan, dtype=float)
    out_dn = np.full_like(values, np.nan, dtype=float)
    for i in range(period - 1, len(values)):
        window = values[i - period + 1 : i + 1]
        std = float(np.std(window))
        out_up[i] = mid[i] + mult * std
        out_dn[i] = mid[i] - mult * std
    return out_up, mid, out_dn


def supertrend(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 10, mult: float = 3.0
) -> tuple[np.ndarray, np.ndarray]:
    """Returns (supertrend_line, direction) where direction is +1 bullish, -1 bearish."""
    atr_ = atr(high, low, close, period)
    hl2 = (high + low) / 2.0
    upper = hl2 + mult * atr_
    lower = hl2 - mult * atr_
    st = np.full_like(close, np.nan, dtype=float)
    direction = np.zeros_like(close, dtype=int)
    for i in range(len(close)):
        if np.isnan(atr_[i]):
            continue
        if i == 0 or np.isnan(st[i - 1]):
            st[i] = lower[i]
            direction[i] = 1
            continue
        prev = st[i - 1]
        if direction[i - 1] == 1:
            st[i] = max(lower[i], prev)
            if close[i] < st[i]:
                direction[i] = -1
                st[i] = upper[i]
            else:
                direction[i] = 1
        else:
            st[i] = min(upper[i], prev)
            if close[i] > st[i]:
                direction[i] = 1
                st[i] = lower[i]
            else:
                direction[i] = -1
    return st, direction


@dataclass
class CandlePattern:
    name: str
    bullish: bool
    strength: float  # 0..1


def detect_candle_patterns(
    open_: np.ndarray, high: np.ndarray, low: np.ndarray, close: np.ndarray
) -> list[CandlePattern]:
    """Detect common single/double-candle patterns on the most recent bar(s)."""
    patterns: list[CandlePattern] = []
    n = len(close)
    if n < 2:
        return patterns

    o, h, lo, c = open_[-1], high[-1], low[-1], close[-1]
    po, ph, pl, pc = open_[-2], high[-2], low[-2], close[-2]
    body = abs(c - o)
    prev_body = abs(pc - po)
    upper = h - max(c, o)
    lower = min(c, o) - lo
    rng = max(h - lo, 1e-9)

    # Bullish engulfing
    if pc < po and c > o and c > po and o < pc and body > prev_body:
        patterns.append(CandlePattern("bullish_engulfing", True, min(1.0, body / (prev_body + 1e-9) / 2)))

    # Bearish engulfing
    if pc > po and c < o and c < po and o > pc and body > prev_body:
        patterns.append(CandlePattern("bearish_engulfing", False, min(1.0, body / (prev_body + 1e-9) / 2)))

    # Hammer (bullish): small body near top, long lower shadow
    if lower > 2 * body and upper < body and c >= o:
        patterns.append(CandlePattern("hammer", True, min(1.0, lower / rng)))

    # Shooting star (bearish): small body near bottom, long upper shadow
    if upper > 2 * body and lower < body and c <= o:
        patterns.append(CandlePattern("shooting_star", False, min(1.0, upper / rng)))

    # Doji: tiny body
    if body < 0.1 * rng:
        patterns.append(CandlePattern("doji", True, 0.3))

    # Inside bar
    if h < ph and lo > pl:
        patterns.append(CandlePattern("inside_bar", True, 0.4))

    return patterns


@dataclass
class IndicatorSnapshot:
    ema_fast: float
    ema_slow: float
    ema_trend: float
    rsi: float
    macd: float
    macd_signal: float
    macd_hist: float
    atr: float
    vwap: float
    bb_upper: float
    bb_lower: float
    st_dir: int
    patterns: list[CandlePattern]


class IndicatorEngine:
    """High-level facade. Given OHLCV arrays, compute a compact snapshot of
    everything a signal engine might need."""

    def __init__(
        self,
        ema_fast: int = 9,
        ema_slow: int = 21,
        ema_trend: int = 50,
        rsi_period: int = 14,
        atr_period: int = 14,
    ) -> None:
        self.ema_fast_p = ema_fast
        self.ema_slow_p = ema_slow
        self.ema_trend_p = ema_trend
        self.rsi_period = rsi_period
        self.atr_period = atr_period

    @staticmethod
    def _last(arr: np.ndarray) -> float:
        if len(arr) == 0:
            return float("nan")
        v = arr[-1]
        return float(v) if not np.isnan(v) else float("nan")

    def snapshot(
        self,
        open_: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        volume: np.ndarray,
    ) -> IndicatorSnapshot:
        ef = ema(close, self.ema_fast_p)
        es = ema(close, self.ema_slow_p)
        et = ema(close, self.ema_trend_p)
        r = rsi(close, self.rsi_period)
        m, s, h = macd(close)
        a = atr(high, low, close, self.atr_period)
        v = vwap(high, low, close, volume)
        bu, _, bl = bollinger(close)
        _, dir_ = supertrend(high, low, close)
        return IndicatorSnapshot(
            ema_fast=self._last(ef),
            ema_slow=self._last(es),
            ema_trend=self._last(et),
            rsi=self._last(r),
            macd=self._last(m),
            macd_signal=self._last(s),
            macd_hist=self._last(h),
            atr=self._last(a),
            vwap=self._last(v),
            bb_upper=self._last(bu),
            bb_lower=self._last(bl),
            st_dir=int(dir_[-1]) if len(dir_) else 0,
            patterns=detect_candle_patterns(open_, high, low, close),
        )
