"""Chart pattern recognition — detects classical chart patterns
from OHLCV data using pivot point analysis and geometric matching.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ai_trader.models.scanner import ChartPattern, PatternBias, PatternType
from ai_trader.strategy.indicators import atr

log = logging.getLogger(__name__)


def detect_patterns(df: pd.DataFrame, symbol: str) -> list[ChartPattern]:
    """Run all pattern detectors on a DataFrame."""
    if len(df) < 50:
        return []
    patterns: list[ChartPattern] = []
    for detector in [
        _detect_double_top,
        _detect_double_bottom,
        _detect_head_and_shoulders,
        _detect_inverse_head_and_shoulders,
        _detect_ascending_triangle,
        _detect_descending_triangle,
        _detect_bull_flag,
        _detect_bear_flag,
    ]:
        try:
            result = detector(df, symbol)
            if result:
                patterns.append(result)
        except Exception as exc:
            log.debug("Pattern detection error on %s: %s", symbol, exc)
    return patterns


def _find_pivots(series: pd.Series, window: int = 5) -> tuple[list[int], list[int]]:
    """Find local maxima (pivot highs) and minima (pivot lows)."""
    highs: list[int] = []
    lows: list[int] = []
    for i in range(window, len(series) - window):
        if series.iloc[i] == max(series.iloc[i - window:i + window + 1]):
            highs.append(i)
        if series.iloc[i] == min(series.iloc[i - window:i + window + 1]):
            lows.append(i)
    return highs, lows


def _atr_val(df: pd.DataFrame) -> float:
    val = float(atr(df).iloc[-1]) if len(df) >= 14 else float(df["close"].iloc[-1]) * 0.015
    return val if not np.isnan(val) else float(df["close"].iloc[-1]) * 0.015


def _detect_double_top(df: pd.DataFrame, symbol: str) -> ChartPattern | None:
    """Double top: two peaks at similar levels with a trough between."""
    highs, lows = _find_pivots(df["high"], window=5)
    if len(highs) < 2 or len(lows) < 1:
        return None

    # Take the two most recent pivot highs
    h1_idx, h2_idx = highs[-2], highs[-1]
    h1 = float(df["high"].iloc[h1_idx])
    h2 = float(df["high"].iloc[h2_idx])
    ltp = float(df["close"].iloc[-1])

    # Peaks should be within 1.5% of each other
    if abs(h1 - h2) / h1 > 0.015:
        return None

    # Find the trough between
    between_lows = [i for i in lows if h1_idx < i < h2_idx]
    if not between_lows:
        return None

    neckline = float(df["low"].iloc[between_lows[0]])

    # Price should be near or breaking neckline
    if ltp > h2 * 0.98:
        return None  # Still near top, hasn't reversed

    atr_v = _atr_val(df)
    target = neckline - (h1 - neckline)  # Measured move down

    return ChartPattern(
        symbol=symbol,
        pattern=PatternType.DOUBLE_TOP,
        bias=PatternBias.BEARISH,
        confidence=0.70,
        entry_zone=round(neckline, 2),
        stop_loss=round(max(h1, h2) + 0.5 * atr_v, 2),
        target=round(target, 2),
        pattern_start_idx=h1_idx,
        pattern_end_idx=h2_idx,
        description=f"Double top at {h1:.0f}/{h2:.0f}, neckline {neckline:.0f}",
    )


def _detect_double_bottom(df: pd.DataFrame, symbol: str) -> ChartPattern | None:
    """Double bottom: two troughs at similar levels."""
    _, lows = _find_pivots(df["low"], window=5)
    highs_list, _ = _find_pivots(df["high"], window=5)
    if len(lows) < 2 or len(highs_list) < 1:
        return None

    l1_idx, l2_idx = lows[-2], lows[-1]
    l1 = float(df["low"].iloc[l1_idx])
    l2 = float(df["low"].iloc[l2_idx])
    ltp = float(df["close"].iloc[-1])

    if abs(l1 - l2) / l1 > 0.015:
        return None

    between_highs = [i for i in highs_list if l1_idx < i < l2_idx]
    if not between_highs:
        return None

    neckline = float(df["high"].iloc[between_highs[0]])

    if ltp < l2 * 1.02:
        return None

    atr_v = _atr_val(df)
    target = neckline + (neckline - l1)

    return ChartPattern(
        symbol=symbol,
        pattern=PatternType.DOUBLE_BOTTOM,
        bias=PatternBias.BULLISH,
        confidence=0.70,
        entry_zone=round(neckline, 2),
        stop_loss=round(min(l1, l2) - 0.5 * atr_v, 2),
        target=round(target, 2),
        pattern_start_idx=l1_idx,
        pattern_end_idx=l2_idx,
        description=f"Double bottom at {l1:.0f}/{l2:.0f}, neckline {neckline:.0f}",
    )


def _detect_head_and_shoulders(df: pd.DataFrame, symbol: str) -> ChartPattern | None:
    """Head & shoulders: left shoulder, higher head, right shoulder."""
    highs, lows = _find_pivots(df["high"], window=5)
    if len(highs) < 3:
        return None

    ls_idx, h_idx, rs_idx = highs[-3], highs[-2], highs[-1]
    ls = float(df["high"].iloc[ls_idx])
    head = float(df["high"].iloc[h_idx])
    rs = float(df["high"].iloc[rs_idx])
    ltp = float(df["close"].iloc[-1])

    # Head should be highest
    if head <= ls or head <= rs:
        return None

    # Shoulders roughly equal (within 3%)
    if abs(ls - rs) / ls > 0.03:
        return None

    # Find neckline from troughs between shoulders
    between_lows = [i for i in lows if ls_idx < i < rs_idx]
    if not between_lows:
        return None

    neckline = min(float(df["low"].iloc[i]) for i in between_lows)
    atr_v = _atr_val(df)
    target = neckline - (head - neckline)

    if ltp > rs * 0.98:
        return None

    return ChartPattern(
        symbol=symbol,
        pattern=PatternType.HEAD_AND_SHOULDERS,
        bias=PatternBias.BEARISH,
        confidence=0.75,
        entry_zone=round(neckline, 2),
        stop_loss=round(rs + 0.5 * atr_v, 2),
        target=round(target, 2),
        pattern_start_idx=ls_idx,
        pattern_end_idx=rs_idx,
        description=f"H&S: LS={ls:.0f} H={head:.0f} RS={rs:.0f} NL={neckline:.0f}",
    )


def _detect_inverse_head_and_shoulders(df: pd.DataFrame, symbol: str) -> ChartPattern | None:
    """Inverse H&S: left shoulder low, lower head low, right shoulder low."""
    _, lows = _find_pivots(df["low"], window=5)
    highs_list, _ = _find_pivots(df["high"], window=5)
    if len(lows) < 3:
        return None

    ls_idx, h_idx, rs_idx = lows[-3], lows[-2], lows[-1]
    ls = float(df["low"].iloc[ls_idx])
    head = float(df["low"].iloc[h_idx])
    rs = float(df["low"].iloc[rs_idx])
    ltp = float(df["close"].iloc[-1])

    if head >= ls or head >= rs:
        return None

    if abs(ls - rs) / ls > 0.03:
        return None

    between_highs = [i for i in highs_list if ls_idx < i < rs_idx]
    if not between_highs:
        return None

    neckline = max(float(df["high"].iloc[i]) for i in between_highs)
    atr_v = _atr_val(df)
    target = neckline + (neckline - head)

    if ltp < rs * 1.02:
        return None

    return ChartPattern(
        symbol=symbol,
        pattern=PatternType.INVERSE_HEAD_AND_SHOULDERS,
        bias=PatternBias.BULLISH,
        confidence=0.75,
        entry_zone=round(neckline, 2),
        stop_loss=round(rs - 0.5 * atr_v, 2),
        target=round(target, 2),
        pattern_start_idx=ls_idx,
        pattern_end_idx=rs_idx,
        description=f"Inv H&S: LS={ls:.0f} H={head:.0f} RS={rs:.0f} NL={neckline:.0f}",
    )


def _detect_ascending_triangle(df: pd.DataFrame, symbol: str) -> ChartPattern | None:
    """Ascending triangle: flat resistance, rising support."""
    highs, lows = _find_pivots(df["high"], window=5)
    _, low_pivots = _find_pivots(df["low"], window=5)

    if len(highs) < 3 or len(low_pivots) < 3:
        return None

    # Check flat resistance (highs within 1%)
    recent_highs = [float(df["high"].iloc[i]) for i in highs[-3:]]
    h_range = (max(recent_highs) - min(recent_highs)) / max(recent_highs)
    if h_range > 0.01:
        return None

    # Check rising lows
    recent_lows = [float(df["low"].iloc[i]) for i in low_pivots[-3:]]
    if not (recent_lows[-1] > recent_lows[-2] > recent_lows[-3]):
        return None

    resistance = max(recent_highs)
    atr_v = _atr_val(df)
    target = resistance + (resistance - min(recent_lows))

    return ChartPattern(
        symbol=symbol,
        pattern=PatternType.ASCENDING_TRIANGLE,
        bias=PatternBias.BULLISH,
        confidence=0.65,
        entry_zone=round(resistance, 2),
        stop_loss=round(recent_lows[-1] - 0.5 * atr_v, 2),
        target=round(target, 2),
        pattern_start_idx=min(highs[-3], low_pivots[-3]),
        pattern_end_idx=max(highs[-1], low_pivots[-1]),
        description=f"Asc triangle: resistance {resistance:.0f}, rising lows",
    )


def _detect_descending_triangle(df: pd.DataFrame, symbol: str) -> ChartPattern | None:
    """Descending triangle: flat support, falling highs."""
    highs, _ = _find_pivots(df["high"], window=5)
    _, low_pivots = _find_pivots(df["low"], window=5)

    if len(highs) < 3 or len(low_pivots) < 3:
        return None

    # Check flat support
    recent_lows = [float(df["low"].iloc[i]) for i in low_pivots[-3:]]
    l_range = (max(recent_lows) - min(recent_lows)) / max(recent_lows) if max(recent_lows) > 0 else 1
    if l_range > 0.01:
        return None

    # Check falling highs
    recent_highs = [float(df["high"].iloc[i]) for i in highs[-3:]]
    if not (recent_highs[-1] < recent_highs[-2] < recent_highs[-3]):
        return None

    support = min(recent_lows)
    atr_v = _atr_val(df)
    target = support - (max(recent_highs) - support)

    return ChartPattern(
        symbol=symbol,
        pattern=PatternType.DESCENDING_TRIANGLE,
        bias=PatternBias.BEARISH,
        confidence=0.65,
        entry_zone=round(support, 2),
        stop_loss=round(recent_highs[-1] + 0.5 * atr_v, 2),
        target=round(target, 2),
        pattern_start_idx=min(highs[-3], low_pivots[-3]),
        pattern_end_idx=max(highs[-1], low_pivots[-1]),
        description=f"Desc triangle: support {support:.0f}, falling highs",
    )


def _detect_bull_flag(df: pd.DataFrame, symbol: str) -> ChartPattern | None:
    """Bull flag: strong up-move followed by a consolidation channel."""
    if len(df) < 40:
        return None

    close = df["close"]
    # Strong move in first portion, consolidation in last ~10 bars
    pole_start = float(close.iloc[-30])
    pole_end = float(close.iloc[-10])
    pole_gain = (pole_end - pole_start) / pole_start

    if pole_gain < 0.03:
        return None

    # Consolidation: low range in last 10 bars
    flag_range = (float(close.iloc[-10:].max()) - float(close.iloc[-10:].min())) / pole_end
    if flag_range > 0.02:
        return None

    ltp = float(close.iloc[-1])
    atr_v = _atr_val(df)
    target = ltp + (pole_end - pole_start)  # Measured move

    return ChartPattern(
        symbol=symbol,
        pattern=PatternType.BULL_FLAG,
        bias=PatternBias.BULLISH,
        confidence=0.65,
        entry_zone=round(ltp, 2),
        stop_loss=round(float(close.iloc[-10:].min()) - 0.5 * atr_v, 2),
        target=round(target, 2),
        pattern_start_idx=len(df) - 30,
        pattern_end_idx=len(df) - 1,
        description=f"Bull flag: pole {pole_gain * 100:.1f}%, flag range {flag_range * 100:.1f}%",
    )


def _detect_bear_flag(df: pd.DataFrame, symbol: str) -> ChartPattern | None:
    """Bear flag: strong down-move followed by consolidation."""
    if len(df) < 40:
        return None

    close = df["close"]
    pole_start = float(close.iloc[-30])
    pole_end = float(close.iloc[-10])
    pole_loss = (pole_start - pole_end) / pole_start

    if pole_loss < 0.03:
        return None

    flag_range = (float(close.iloc[-10:].max()) - float(close.iloc[-10:].min())) / pole_end
    if flag_range > 0.02:
        return None

    ltp = float(close.iloc[-1])
    atr_v = _atr_val(df)
    target = ltp - (pole_start - pole_end)

    return ChartPattern(
        symbol=symbol,
        pattern=PatternType.BEAR_FLAG,
        bias=PatternBias.BEARISH,
        confidence=0.65,
        entry_zone=round(ltp, 2),
        stop_loss=round(float(close.iloc[-10:].max()) + 0.5 * atr_v, 2),
        target=round(target, 2),
        pattern_start_idx=len(df) - 30,
        pattern_end_idx=len(df) - 1,
        description=f"Bear flag: pole {pole_loss * 100:.1f}%, flag range {flag_range * 100:.1f}%",
    )
