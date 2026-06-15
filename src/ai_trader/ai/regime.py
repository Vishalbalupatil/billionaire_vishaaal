"""Market regime detection using technical indicators.

Classifies the current market into one of: TRENDING_UP, TRENDING_DOWN,
RANGE_BOUND, VOLATILE, QUIET.  Used by the strategy selector to pick the
optimal options strategy for current conditions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ai_trader.models.domain import MarketRegime


def detect_regime(
    candles_df: pd.DataFrame,
    vix: float = 15.0,
    lookback: int = 20,
) -> MarketRegime:
    """Detect market regime from recent candle data.

    Uses a combination of:
    - ADX (trend strength)
    - EMA slope direction
    - Bollinger Band width (volatility)
    - VIX level
    """
    if len(candles_df) < lookback + 14:
        return MarketRegime.UNKNOWN

    close = candles_df["close"].iloc[-lookback - 14:]

    # ADX calculation
    adx = _calculate_adx(candles_df.iloc[-lookback - 14:])

    # EMA 20 slope
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema_slope = (ema20.iloc[-1] - ema20.iloc[-5]) / ema20.iloc[-5] * 100

    # Bollinger Band width
    sma = close.rolling(20).mean()
    std = close.rolling(20).std()
    bb_width = ((2 * std) / sma).iloc[-1] if sma.iloc[-1] != 0 else 0

    # High VIX = volatile
    if vix > 25:
        if abs(ema_slope) > 0.5:
            return MarketRegime.TRENDING_UP if ema_slope > 0 else MarketRegime.TRENDING_DOWN
        return MarketRegime.VOLATILE

    # Strong trend
    if adx > 25:
        return MarketRegime.TRENDING_UP if ema_slope > 0 else MarketRegime.TRENDING_DOWN

    # Narrow bands = quiet
    if bb_width < 0.03 and vix < 14:
        return MarketRegime.QUIET

    # Wide bands but no trend = range
    if adx < 20:
        return MarketRegime.RANGE_BOUND

    # Default
    if ema_slope > 0.2:
        return MarketRegime.TRENDING_UP
    elif ema_slope < -0.2:
        return MarketRegime.TRENDING_DOWN

    return MarketRegime.RANGE_BOUND


def _calculate_adx(df: pd.DataFrame, period: int = 14) -> float:
    """Calculate ADX (Average Directional Index)."""
    if len(df) < period + 1:
        return 0.0

    high = df["high"].values
    low = df["low"].values
    close = df["close"].values

    plus_dm = np.zeros(len(df))
    minus_dm = np.zeros(len(df))
    tr = np.zeros(len(df))

    for i in range(1, len(df)):
        h_diff = high[i] - high[i - 1]
        l_diff = low[i - 1] - low[i]

        plus_dm[i] = h_diff if (h_diff > l_diff and h_diff > 0) else 0
        minus_dm[i] = l_diff if (l_diff > h_diff and l_diff > 0) else 0

        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )

    # Smoothed averages
    atr = pd.Series(tr).rolling(period).mean().values
    smooth_plus = pd.Series(plus_dm).rolling(period).mean().values
    smooth_minus = pd.Series(minus_dm).rolling(period).mean().values

    # Directional indicators
    with np.errstate(divide="ignore", invalid="ignore"):
        plus_di = np.where(atr > 0, 100 * smooth_plus / atr, 0)
        minus_di = np.where(atr > 0, 100 * smooth_minus / atr, 0)

        di_sum = plus_di + minus_di
        dx = np.where(di_sum > 0, 100 * np.abs(plus_di - minus_di) / di_sum, 0)

    adx_series = pd.Series(dx).rolling(period).mean()
    last_adx = adx_series.iloc[-1]
    return float(last_adx) if not np.isnan(last_adx) else 0.0
