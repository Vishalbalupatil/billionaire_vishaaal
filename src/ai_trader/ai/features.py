"""Feature engineering pipeline for the ML model.

Transforms raw candle data + options data into a feature matrix that the
ensemble model consumes.  Every feature is computed as a pure function of
``pandas.DataFrame`` input so the same pipeline works for live and backtest.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd(series: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    fast = _ema(series, 12)
    slow = _ema(series, 26)
    macd_line = fast - slow
    signal_line = _ema(macd_line, 9)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _bollinger_bands(series: pd.Series, period: int = 20, std_dev: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    sma = series.rolling(period).mean()
    std = series.rolling(period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    return upper, sma, lower


def _supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.Series:
    atr = _atr(df, period)
    hl2 = (df["high"] + df["low"]) / 2
    upper_band = hl2 + multiplier * atr
    lower_band = hl2 - multiplier * atr

    supertrend = pd.Series(0.0, index=df.index)
    direction = pd.Series(1, index=df.index)

    for i in range(1, len(df)):
        if df["close"].iloc[i] > upper_band.iloc[i - 1]:
            direction.iloc[i] = 1
        elif df["close"].iloc[i] < lower_band.iloc[i - 1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i - 1]
            if direction.iloc[i] == 1 and lower_band.iloc[i] < lower_band.iloc[i - 1]:
                lower_band.iloc[i] = lower_band.iloc[i - 1]
            if direction.iloc[i] == -1 and upper_band.iloc[i] > upper_band.iloc[i - 1]:
                upper_band.iloc[i] = upper_band.iloc[i - 1]

        supertrend.iloc[i] = lower_band.iloc[i] if direction.iloc[i] == 1 else upper_band.iloc[i]

    return direction


def _vwap(df: pd.DataFrame) -> pd.Series:
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cumulative_tp_vol = (typical_price * df["volume"]).cumsum()
    cumulative_vol = df["volume"].cumsum().replace(0, np.nan)
    return cumulative_tp_vol / cumulative_vol


def build_features(candles_df: pd.DataFrame, vix: float = 15.0, pcr: float = 1.0) -> pd.DataFrame:
    """Build full feature matrix from OHLCV candle DataFrame.

    Parameters
    ----------
    candles_df : pd.DataFrame
        Must contain columns: open, high, low, close, volume.
    vix : float
        India VIX value (injected from market data).
    pcr : float
        Put-Call Ratio from options chain.

    Returns
    -------
    pd.DataFrame with one row per candle containing all features.
    """
    df = candles_df.copy()
    close = df["close"]

    # Trend indicators
    df["ema_9"] = _ema(close, 9)
    df["ema_21"] = _ema(close, 21)
    df["ema_50"] = _ema(close, 50)
    df["ema_200"] = _ema(close, 200)
    df["ema_crossover_9_21"] = (df["ema_9"] - df["ema_21"]) / close
    df["ema_crossover_21_50"] = (df["ema_21"] - df["ema_50"]) / close
    df["price_vs_ema200"] = (close - df["ema_200"]) / close

    # Momentum
    df["rsi_14"] = _rsi(close, 14)
    df["rsi_7"] = _rsi(close, 7)
    macd_line, signal_line, histogram = _macd(close)
    df["macd"] = macd_line
    df["macd_signal"] = signal_line
    df["macd_histogram"] = histogram
    df["momentum_5"] = close.pct_change(5)
    df["momentum_10"] = close.pct_change(10)

    # Volatility
    df["atr_14"] = _atr(df, 14)
    df["atr_pct"] = df["atr_14"] / close
    bb_upper, bb_mid, bb_lower = _bollinger_bands(close)
    df["bb_upper"] = bb_upper
    df["bb_lower"] = bb_lower
    df["bb_width"] = (bb_upper - bb_lower) / bb_mid
    df["bb_position"] = (close - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)

    # Volume
    df["volume_sma_20"] = df["volume"].rolling(20).mean()
    df["volume_ratio"] = df["volume"] / df["volume_sma_20"].replace(0, np.nan)
    if df["volume"].sum() > 0:
        df["vwap"] = _vwap(df)
        df["price_vs_vwap"] = (close - df["vwap"]) / close
    else:
        df["vwap"] = close
        df["price_vs_vwap"] = 0.0

    # SuperTrend direction
    df["supertrend_dir"] = _supertrend(df)

    # Candle patterns
    body = (close - df["open"]).abs()
    full_range = (df["high"] - df["low"]).replace(0, np.nan)
    df["body_ratio"] = body / full_range
    df["upper_shadow"] = (df["high"] - pd.concat([close, df["open"]], axis=1).max(axis=1)) / full_range
    df["lower_shadow"] = (pd.concat([close, df["open"]], axis=1).min(axis=1) - df["low"]) / full_range
    df["is_bullish_candle"] = (close > df["open"]).astype(int)

    # Volatility regime
    df["vix"] = vix
    df["vix_high"] = int(vix > 20)
    df["vix_extreme"] = int(vix > 25)

    # Options flow
    df["pcr"] = pcr
    df["pcr_bullish"] = int(pcr > 1.2)
    df["pcr_bearish"] = int(pcr < 0.7)

    # Returns & volatility features
    df["return_1"] = close.pct_change(1)
    df["return_5"] = close.pct_change(5)
    df["realized_vol_10"] = df["return_1"].rolling(10).std() * np.sqrt(252)
    df["realized_vol_20"] = df["return_1"].rolling(20).std() * np.sqrt(252)

    # Gap features
    df["gap_pct"] = (df["open"] - df["close"].shift()) / df["close"].shift()

    return df


FEATURE_COLUMNS = [
    "ema_crossover_9_21", "ema_crossover_21_50", "price_vs_ema200",
    "rsi_14", "rsi_7", "macd", "macd_signal", "macd_histogram",
    "momentum_5", "momentum_10",
    "atr_pct", "bb_width", "bb_position",
    "volume_ratio", "price_vs_vwap",
    "supertrend_dir", "body_ratio", "upper_shadow", "lower_shadow",
    "is_bullish_candle",
    "vix", "vix_high", "vix_extreme",
    "pcr", "pcr_bullish", "pcr_bearish",
    "return_1", "return_5", "realized_vol_10", "realized_vol_20",
    "gap_pct",
]
