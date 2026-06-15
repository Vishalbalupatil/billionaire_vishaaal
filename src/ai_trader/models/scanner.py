"""Models for equity scanner, chart patterns, and auto-trading."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ScanType(StrEnum):
    MOMENTUM = "MOMENTUM"
    BREAKOUT = "BREAKOUT"
    REVERSAL = "REVERSAL"
    VOLUME_SURGE = "VOLUME_SURGE"
    TREND_FOLLOWING = "TREND_FOLLOWING"


class PatternType(StrEnum):
    HEAD_AND_SHOULDERS = "HEAD_AND_SHOULDERS"
    INVERSE_HEAD_AND_SHOULDERS = "INVERSE_HEAD_AND_SHOULDERS"
    DOUBLE_TOP = "DOUBLE_TOP"
    DOUBLE_BOTTOM = "DOUBLE_BOTTOM"
    ASCENDING_TRIANGLE = "ASCENDING_TRIANGLE"
    DESCENDING_TRIANGLE = "DESCENDING_TRIANGLE"
    BULL_FLAG = "BULL_FLAG"
    BEAR_FLAG = "BEAR_FLAG"
    CUP_AND_HANDLE = "CUP_AND_HANDLE"
    RISING_WEDGE = "RISING_WEDGE"
    FALLING_WEDGE = "FALLING_WEDGE"


class PatternBias(StrEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class TrendDirection(StrEnum):
    STRONG_UP = "STRONG_UP"
    UP = "UP"
    SIDEWAYS = "SIDEWAYS"
    DOWN = "DOWN"
    STRONG_DOWN = "STRONG_DOWN"


class TimeFrame(StrEnum):
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    DAILY = "day"


class ScanResult(BaseModel):
    """Result from equity scanner for a single stock."""
    symbol: str
    exchange: str = "NSE"
    ltp: float
    change_pct: float = 0.0
    scan_type: ScanType
    score: float = Field(ge=0.0, le=100.0)
    reasons: list[str] = Field(default_factory=list)
    entry: float = 0.0
    stop_loss: float = 0.0
    target: float = 0.0
    risk_reward: float = 0.0
    volume_ratio: float = 1.0
    ts: datetime = Field(default_factory=datetime.utcnow)


class ChartPattern(BaseModel):
    """Detected chart pattern on a symbol."""
    symbol: str
    pattern: PatternType
    bias: PatternBias
    confidence: float = Field(ge=0.0, le=1.0)
    entry_zone: float = 0.0
    stop_loss: float = 0.0
    target: float = 0.0
    pattern_start_idx: int = 0
    pattern_end_idx: int = 0
    description: str = ""
    ts: datetime = Field(default_factory=datetime.utcnow)


class TrendAnalysis(BaseModel):
    """Multi-timeframe trend analysis for a symbol."""
    symbol: str
    trend_5m: TrendDirection = TrendDirection.SIDEWAYS
    trend_15m: TrendDirection = TrendDirection.SIDEWAYS
    trend_1h: TrendDirection = TrendDirection.SIDEWAYS
    trend_daily: TrendDirection = TrendDirection.SIDEWAYS
    overall: TrendDirection = TrendDirection.SIDEWAYS
    strength: float = Field(ge=0.0, le=100.0, default=50.0)
    ema_20: float = 0.0
    ema_50: float = 0.0
    ema_200: float = 0.0
    supertrend_signal: int = 0  # 1=bullish, -1=bearish
    adx: float = 0.0
    rsi: float = 50.0
    ts: datetime = Field(default_factory=datetime.utcnow)


class AutoTradeAction(StrEnum):
    SCAN = "SCAN"
    SIGNAL = "SIGNAL"
    ENTER = "ENTER"
    MONITOR = "MONITOR"
    EXIT = "EXIT"
    SKIP = "SKIP"


class AutoTradeLog(BaseModel):
    """Log entry for autonomous trading loop."""
    symbol: str
    action: AutoTradeAction
    details: str = ""
    pnl: float = 0.0
    ts: datetime = Field(default_factory=datetime.utcnow)
