"""Technical indicators computed on candle DataFrames.

These are standalone functions used by the strategy engine and backtester.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    fast = ema(series, 12)
    slow = ema(series, 26)
    macd_line = fast - slow
    signal_line = ema(macd_line, 9)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = sma(series, period)
    std = series.rolling(period).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return upper, mid, lower


def vwap(df: pd.DataFrame) -> pd.Series:
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cumulative_tp_vol = (typical_price * df["volume"]).cumsum()
    cumulative_vol = df["volume"].cumsum().replace(0, np.nan)
    return cumulative_tp_vol / cumulative_vol


def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.Series:
    atr_val = atr(df, period)
    hl2 = (df["high"] + df["low"]) / 2
    upper_band = hl2 + multiplier * atr_val
    lower_band = hl2 - multiplier * atr_val

    direction = pd.Series(1, index=df.index)
    for i in range(1, len(df)):
        if df["close"].iloc[i] > upper_band.iloc[i - 1]:
            direction.iloc[i] = 1
        elif df["close"].iloc[i] < lower_band.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]
    return direction


def pivot_points(high: float, low: float, close: float) -> dict[str, float]:
    """Standard pivot points from previous day HLC."""
    pp = (high + low + close) / 3
    return {
        "pp": round(pp, 2),
        "r1": round(2 * pp - low, 2),
        "r2": round(pp + (high - low), 2),
        "r3": round(high + 2 * (pp - low), 2),
        "s1": round(2 * pp - high, 2),
        "s2": round(pp - (high - low), 2),
        "s3": round(low - 2 * (high - pp), 2),
    }
