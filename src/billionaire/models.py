"""Typed domain models used across the platform."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Exchange(str, Enum):
    NSE = "NSE"
    BSE = "BSE"
    NFO = "NFO"
    BFO = "BFO"
    MCX = "MCX"


class Segment(str, Enum):
    EQUITY = "EQUITY"
    FUTURES = "FUTURES"
    OPTIONS = "OPTIONS"
    INDEX = "INDEX"


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SL_M = "SL-M"


class ProductType(str, Enum):
    MIS = "MIS"  # intraday
    CNC = "CNC"  # delivery
    NRML = "NRML"  # carry


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    COMPLETE = "COMPLETE"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class SignalDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class SetupType(str, Enum):
    MOMENTUM_BREAKOUT = "MOMENTUM_BREAKOUT"
    REVERSAL = "REVERSAL"
    TREND_CONTINUATION = "TREND_CONTINUATION"
    MEAN_REVERSION = "MEAN_REVERSION"
    RANGE_FADE = "RANGE_FADE"
    OPTION_BUYING = "OPTION_BUYING"
    OPTION_SELLING_CANDIDATE = "OPTION_SELLING_CANDIDATE"
    FUTURES_SCALP = "FUTURES_SCALP"
    EQUITY_INTRADAY = "EQUITY_INTRADAY"
    SWING_CANDIDATE = "SWING_CANDIDATE"


class MarketRegime(str, Enum):
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGE = "RANGE"
    VOLATILE = "VOLATILE"
    QUIET = "QUIET"
    UNKNOWN = "UNKNOWN"


class Instrument(BaseModel):
    instrument_token: int
    tradingsymbol: str
    name: str = ""
    exchange: Exchange
    segment: Segment = Segment.EQUITY
    lot_size: int = 1
    tick_size: float = 0.05
    expiry: str | None = None
    strike: float | None = None
    option_type: Literal["CE", "PE"] | None = None


class Tick(BaseModel):
    instrument_token: int
    ltp: float
    volume: int = 0
    oi: int = 0
    bid: float = 0.0
    ask: float = 0.0
    ts: datetime = Field(default_factory=datetime.utcnow)


class Candle(BaseModel):
    instrument_token: int
    timeframe: str  # "1m", "3m", "5m", "15m", "1h"
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    oi: int = 0
    ts: datetime


class Signal(BaseModel):
    instrument: Instrument
    setup: SetupType
    direction: SignalDirection
    entry: float
    stop_loss: float
    target1: float
    target2: float | None = None
    trailing_logic: str = "ATR x 1.0 once target1 hit"
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = []
    invalidation: list[str] = []
    regime: MarketRegime = MarketRegime.UNKNOWN
    suggested_qty: int = 0
    risk_rupees: float = 0.0
    expected_rr: float = 0.0
    strategy: str
    ts: datetime = Field(default_factory=datetime.utcnow)

    def explain(self) -> str:
        rr = f"{self.expected_rr:.2f}R" if self.expected_rr else "n/a"
        reasons = "; ".join(self.reasons) if self.reasons else "—"
        inv = "; ".join(self.invalidation) if self.invalidation else "—"
        return (
            f"[{self.strategy}] {self.direction.value} {self.setup.value} on "
            f"{self.instrument.tradingsymbol} @ {self.entry} "
            f"(SL {self.stop_loss}, T1 {self.target1}, RR {rr}, "
            f"confidence {self.confidence:.2f}, regime {self.regime.value}). "
            f"Why: {reasons}. Invalidation: {inv}."
        )


class OrderRequest(BaseModel):
    instrument: Instrument
    side: Side
    quantity: int
    order_type: OrderType = OrderType.MARKET
    product: ProductType = ProductType.MIS
    limit_price: float | None = None
    trigger_price: float | None = None
    tag: str = ""


class Order(BaseModel):
    order_id: str
    request: OrderRequest
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: int = 0
    avg_price: float = 0.0
    message: str = ""
    broker: str = "paper"
    ts: datetime = Field(default_factory=datetime.utcnow)


class Position(BaseModel):
    instrument: Instrument
    quantity: int
    avg_price: float
    ltp: float = 0.0
    product: ProductType = ProductType.MIS

    @property
    def unrealized_pnl(self) -> float:
        return (self.ltp - self.avg_price) * self.quantity


class Trade(BaseModel):
    trade_id: str
    order_id: str
    instrument: Instrument
    side: Side
    quantity: int
    price: float
    ts: datetime = Field(default_factory=datetime.utcnow)
    pnl: float = 0.0
