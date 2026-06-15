"""Equity scanner — scans NSE stocks for momentum, breakout, reversal,
and volume surge setups. Produces ranked ScanResult objects that the
auto-trader can act upon.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ai_trader.models.scanner import ScanResult, ScanType
from ai_trader.strategy.indicators import atr, bollinger_bands, ema, macd, rsi, vwap

log = logging.getLogger(__name__)

# Nifty 50 constituents (representative subset for scanning)
NIFTY50_SYMBOLS: list[str] = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
    "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "HCLTECH",
    "BAJFINANCE", "WIPRO", "SUNPHARMA", "TITAN", "ULTRACEMCO",
    "ONGC", "NTPC", "POWERGRID", "TATAMOTORS", "NESTLEIND",
    "M&M", "TATASTEEL", "JSWSTEEL", "INDUSINDBK", "TECHM",
    "ADANIENT", "ADANIPORTS", "BAJAJFINSV", "BPCL", "COALINDIA",
    "DIVISLAB", "DRREDDY", "EICHERMOT", "GRASIM", "CIPLA",
    "BRITANNIA", "HEROMOTOCO", "HINDALCO", "APOLLOHOSP", "LTIM",
    "SBILIFE", "HDFCLIFE", "TATACONSUM", "UPL", "BAJAJ-AUTO",
]


def scan_momentum(df: pd.DataFrame, symbol: str) -> ScanResult | None:
    """Detect momentum setups: RSI + MACD + EMA alignment."""
    if len(df) < 50:
        return None

    close = df["close"]
    rsi_val = float(rsi(close).iloc[-1])
    macd_line, signal_line, hist = macd(close)
    ema_20 = float(ema(close, 20).iloc[-1])
    ema_50 = float(ema(close, 50).iloc[-1])
    ltp = float(close.iloc[-1])
    atr_val = float(atr(df).iloc[-1]) if len(df) >= 14 else ltp * 0.015

    if np.isnan(rsi_val) or np.isnan(atr_val):
        return None

    score = 0.0
    reasons: list[str] = []

    # Bullish momentum
    bullish = True
    if rsi_val > 55 and rsi_val < 80:
        score += 25
        reasons.append(f"RSI={rsi_val:.1f} (bullish zone)")
    else:
        bullish = False

    macd_val = float(macd_line.iloc[-1])
    signal_val = float(signal_line.iloc[-1])
    if not np.isnan(macd_val) and not np.isnan(signal_val) and macd_val > signal_val:
        score += 20
        reasons.append("MACD above signal")
    else:
        bullish = False

    if ltp > ema_20 > ema_50:
        score += 25
        reasons.append("Price > EMA20 > EMA50")
    else:
        bullish = False

    hist_val = float(hist.iloc[-1]) if not np.isnan(float(hist.iloc[-1])) else 0
    if hist_val > 0:
        score += 10
        reasons.append("MACD histogram positive")

    # Volume confirmation
    vol_ratio = _volume_ratio(df)
    if vol_ratio > 1.5:
        score += 20
        reasons.append(f"Volume {vol_ratio:.1f}x avg")

    if not bullish or score < 50:
        return None

    entry = ltp
    sl = entry - 1.5 * atr_val
    target = entry + 2.5 * atr_val
    rr = (target - entry) / (entry - sl) if entry > sl else 0

    return ScanResult(
        symbol=symbol,
        ltp=round(ltp, 2),
        change_pct=_change_pct(df),
        scan_type=ScanType.MOMENTUM,
        score=min(100, score),
        reasons=reasons,
        entry=round(entry, 2),
        stop_loss=round(sl, 2),
        target=round(target, 2),
        risk_reward=round(rr, 2),
        volume_ratio=round(vol_ratio, 2),
    )


def scan_breakout(df: pd.DataFrame, symbol: str) -> ScanResult | None:
    """Detect breakout setups: price breaking above resistance with volume."""
    if len(df) < 50:
        return None

    close = df["close"]
    high = df["high"]
    ltp = float(close.iloc[-1])
    atr_val = float(atr(df).iloc[-1]) if len(df) >= 14 else ltp * 0.015

    if np.isnan(atr_val):
        return None

    # 20-day high breakout
    lookback_high = float(high.iloc[-21:-1].max()) if len(df) > 21 else float(high.iloc[:-1].max())
    bb_upper, bb_mid, bb_lower = bollinger_bands(close)

    score = 0.0
    reasons: list[str] = []

    # Breaking above recent high
    if ltp > lookback_high:
        score += 30
        reasons.append(f"Breaking 20-bar high ({lookback_high:.2f})")

    # Breaking above upper Bollinger Band
    bb_up_val = float(bb_upper.iloc[-1])
    if not np.isnan(bb_up_val) and ltp > bb_up_val:
        score += 20
        reasons.append("Above upper Bollinger Band")

    # Volume surge
    vol_ratio = _volume_ratio(df)
    if vol_ratio > 2.0:
        score += 25
        reasons.append(f"Volume surge {vol_ratio:.1f}x")
    elif vol_ratio > 1.5:
        score += 15
        reasons.append(f"Volume {vol_ratio:.1f}x avg")

    # VWAP confirmation
    vwap_val = float(vwap(df).iloc[-1])
    if not np.isnan(vwap_val) and ltp > vwap_val:
        score += 15
        reasons.append("Above VWAP")

    # RSI not overbought
    rsi_val = float(rsi(close).iloc[-1])
    if not np.isnan(rsi_val) and rsi_val < 75:
        score += 10
        reasons.append(f"RSI={rsi_val:.1f} (room to run)")

    if score < 50:
        return None

    entry = ltp
    sl = lookback_high - 0.5 * atr_val
    target = entry + 3 * atr_val
    rr = (target - entry) / (entry - sl) if entry > sl else 0

    return ScanResult(
        symbol=symbol,
        ltp=round(ltp, 2),
        change_pct=_change_pct(df),
        scan_type=ScanType.BREAKOUT,
        score=min(100, score),
        reasons=reasons,
        entry=round(entry, 2),
        stop_loss=round(sl, 2),
        target=round(target, 2),
        risk_reward=round(rr, 2),
        volume_ratio=round(vol_ratio, 2),
    )


def scan_volume_surge(df: pd.DataFrame, symbol: str) -> ScanResult | None:
    """Detect unusual volume activity indicating institutional interest."""
    if len(df) < 30:
        return None

    close = df["close"]
    ltp = float(close.iloc[-1])
    vol_ratio = _volume_ratio(df)
    atr_val = float(atr(df).iloc[-1]) if len(df) >= 14 else ltp * 0.015

    if np.isnan(atr_val) or vol_ratio < 2.0:
        return None

    score = 0.0
    reasons: list[str] = []

    # Volume is the primary criterion
    if vol_ratio > 3.0:
        score += 40
        reasons.append(f"Extreme volume {vol_ratio:.1f}x avg")
    else:
        score += 25
        reasons.append(f"High volume {vol_ratio:.1f}x avg")

    # Direction of move
    change = _change_pct(df)
    if change > 1.0:
        score += 20
        reasons.append(f"Up {change:.1f}%")
        bullish = True
    elif change < -1.0:
        score += 20
        reasons.append(f"Down {change:.1f}%")
        bullish = False
    else:
        return None  # Volume without direction is noise

    # EMA trend confirmation
    ema_20 = float(ema(close, 20).iloc[-1])
    if (bullish and ltp > ema_20) or (not bullish and ltp < ema_20):
        score += 15
        reasons.append("EMA20 trend aligned")

    if score < 50:
        return None

    if bullish:
        entry = ltp
        sl = entry - 1.5 * atr_val
        target = entry + 2 * atr_val
    else:
        entry = ltp
        sl = entry + 1.5 * atr_val
        target = entry - 2 * atr_val

    rr = abs(target - entry) / abs(entry - sl) if abs(entry - sl) > 0 else 0

    return ScanResult(
        symbol=symbol,
        ltp=round(ltp, 2),
        change_pct=round(change, 2),
        scan_type=ScanType.VOLUME_SURGE,
        score=min(100, score),
        reasons=reasons,
        entry=round(entry, 2),
        stop_loss=round(sl, 2),
        target=round(target, 2),
        risk_reward=round(rr, 2),
        volume_ratio=round(vol_ratio, 2),
    )


def scan_stock(df: pd.DataFrame, symbol: str) -> list[ScanResult]:
    """Run all scans on a single stock and return qualifying results."""
    results: list[ScanResult] = []
    for scanner in [scan_momentum, scan_breakout, scan_volume_surge]:
        try:
            result = scanner(df, symbol)
            if result:
                results.append(result)
        except Exception as exc:
            log.debug("Scanner error on %s: %s", symbol, exc)
    return results


def rank_results(results: list[ScanResult], top_n: int = 10) -> list[ScanResult]:
    """Rank scan results by score and return top N."""
    return sorted(results, key=lambda r: r.score, reverse=True)[:top_n]


def _volume_ratio(df: pd.DataFrame) -> float:
    """Current volume / 20-bar average volume."""
    if "volume" not in df.columns or len(df) < 20:
        return 1.0
    avg_vol = float(df["volume"].iloc[-21:-1].mean())
    cur_vol = float(df["volume"].iloc[-1])
    return cur_vol / avg_vol if avg_vol > 0 else 1.0


def _change_pct(df: pd.DataFrame) -> float:
    """Percent change from previous close."""
    if len(df) < 2:
        return 0.0
    prev = float(df["close"].iloc[-2])
    cur = float(df["close"].iloc[-1])
    return ((cur - prev) / prev * 100) if prev > 0 else 0.0
