"""Multi-timeframe trend analysis — identifies trend direction and
strength across multiple timeframes for a given symbol.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ai_trader.models.scanner import TrendAnalysis, TrendDirection
from ai_trader.strategy.indicators import atr, ema, rsi, supertrend

log = logging.getLogger(__name__)


def analyze_trend(df: pd.DataFrame, symbol: str) -> TrendAnalysis:
    """Analyze trend on a single timeframe DataFrame and produce a TrendAnalysis."""
    if len(df) < 50:
        return TrendAnalysis(symbol=symbol)

    close = df["close"]
    ltp = float(close.iloc[-1])

    ema_20 = float(ema(close, 20).iloc[-1])
    ema_50 = float(ema(close, 50).iloc[-1])
    ema_200_val = float(ema(close, 200).iloc[-1]) if len(df) >= 200 else float(ema(close, len(df)).iloc[-1])

    rsi_val = float(rsi(close).iloc[-1])
    if np.isnan(rsi_val):
        rsi_val = 50.0

    st = supertrend(df)
    st_signal = int(st.iloc[-1]) if not np.isnan(float(st.iloc[-1])) else 0

    adx_val = _compute_adx(df)

    # Determine trend direction
    direction = _classify_trend(ltp, ema_20, ema_50, ema_200_val, st_signal, adx_val, rsi_val)
    strength = _compute_strength(ltp, ema_20, ema_50, ema_200_val, adx_val, rsi_val)

    return TrendAnalysis(
        symbol=symbol,
        overall=direction,
        strength=round(strength, 1),
        ema_20=round(ema_20, 2),
        ema_50=round(ema_50, 2),
        ema_200=round(ema_200_val, 2),
        supertrend_signal=st_signal,
        adx=round(adx_val, 1),
        rsi=round(rsi_val, 1),
    )


def multi_timeframe_trend(
    data_by_tf: dict[str, pd.DataFrame],
    symbol: str,
) -> TrendAnalysis:
    """Combine trend analysis from multiple timeframes into one result.

    data_by_tf keys should be like "5m", "15m", "1h", "day".
    """
    base = TrendAnalysis(symbol=symbol)
    tf_map = {"5m": "trend_5m", "15m": "trend_15m", "1h": "trend_1h", "day": "trend_daily"}

    analyses: list[TrendAnalysis] = []
    for tf, attr in tf_map.items():
        df = data_by_tf.get(tf)
        if df is not None and len(df) >= 20:
            ta = analyze_trend(df, symbol)
            setattr(base, attr, ta.overall)
            analyses.append(ta)

    if not analyses:
        return base

    # Overall trend = weighted consensus (higher TF gets more weight)
    weights = {"5m": 1, "15m": 2, "1h": 3, "day": 4}
    score = 0.0
    total_weight = 0.0
    for tf, attr in tf_map.items():
        direction = getattr(base, attr)
        w = weights.get(tf, 1)
        total_weight += w
        score += w * _direction_score(direction)

    avg_score = score / total_weight if total_weight > 0 else 0
    base.overall = _score_to_direction(avg_score)
    base.strength = round(min(100, max(0, abs(avg_score) * 50 + 50)), 1)

    # Use latest analysis values for indicators
    latest = analyses[-1]
    base.ema_20 = latest.ema_20
    base.ema_50 = latest.ema_50
    base.ema_200 = latest.ema_200
    base.supertrend_signal = latest.supertrend_signal
    base.adx = latest.adx
    base.rsi = latest.rsi

    return base


def _classify_trend(
    ltp: float,
    ema20: float,
    ema50: float,
    ema200: float,
    st_signal: int,
    adx: float,
    rsi_val: float,
) -> TrendDirection:
    """Classify trend direction from indicators."""
    bullish_count = 0
    bearish_count = 0

    if ltp > ema20:
        bullish_count += 1
    else:
        bearish_count += 1

    if ema20 > ema50:
        bullish_count += 1
    else:
        bearish_count += 1

    if ltp > ema200:
        bullish_count += 1
    else:
        bearish_count += 1

    if st_signal > 0:
        bullish_count += 1
    elif st_signal < 0:
        bearish_count += 1

    if rsi_val > 60:
        bullish_count += 1
    elif rsi_val < 40:
        bearish_count += 1

    net = bullish_count - bearish_count

    if adx > 25:
        if net >= 3:
            return TrendDirection.STRONG_UP
        if net <= -3:
            return TrendDirection.STRONG_DOWN
    if net >= 2:
        return TrendDirection.UP
    if net <= -2:
        return TrendDirection.DOWN
    return TrendDirection.SIDEWAYS


def _compute_strength(
    ltp: float,
    ema20: float,
    ema50: float,
    ema200: float,
    adx: float,
    rsi_val: float,
) -> float:
    """Compute trend strength 0-100."""
    strength = 50.0

    # EMA alignment
    if ltp > ema20 > ema50 > ema200 or ltp < ema20 < ema50 < ema200:
        strength += 20
    elif ltp > ema20 > ema50 or ltp < ema20 < ema50:
        strength += 10

    # ADX component
    strength += min(20, adx * 0.5)

    # RSI extremes
    if rsi_val > 70 or rsi_val < 30:
        strength += 10

    return min(100, max(0, strength))


def _compute_adx(df: pd.DataFrame, period: int = 14) -> float:
    """Compute ADX (Average Directional Index)."""
    if len(df) < period * 2:
        return 0.0

    high = df["high"]
    low = df["low"]

    plus_dm = high.diff()
    minus_dm = -low.diff()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    atr_val = atr(df, period)
    atr_safe = atr_val.replace(0, np.nan)

    plus_di = 100 * (plus_dm.rolling(period).mean() / atr_safe)
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr_safe)

    dx = (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)) * 100
    adx_val = float(dx.rolling(period).mean().iloc[-1])

    return adx_val if not np.isnan(adx_val) else 0.0


def _direction_score(d: TrendDirection) -> float:
    """Map direction to numeric score for averaging."""
    return {
        TrendDirection.STRONG_UP: 2.0,
        TrendDirection.UP: 1.0,
        TrendDirection.SIDEWAYS: 0.0,
        TrendDirection.DOWN: -1.0,
        TrendDirection.STRONG_DOWN: -2.0,
    }.get(d, 0.0)


def _score_to_direction(score: float) -> TrendDirection:
    if score >= 1.5:
        return TrendDirection.STRONG_UP
    if score >= 0.5:
        return TrendDirection.UP
    if score <= -1.5:
        return TrendDirection.STRONG_DOWN
    if score <= -0.5:
        return TrendDirection.DOWN
    return TrendDirection.SIDEWAYS
