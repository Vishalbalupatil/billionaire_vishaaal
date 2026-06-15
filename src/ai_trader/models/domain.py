"""Core domain models used across the platform."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Exchange(StrEnum):
    NSE = "NSE"
    BSE = "BSE"
    NFO = "NFO"
    BFO = "BFO"
    MCX = "MCX"


class Segment(StrEnum):
    EQUITY = "EQUITY"
    FUTURES = "FUTURES"
    OPTIONS = "OPTIONS"
    INDEX = "INDEX"


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SL_M = "SL-M"


class ProductType(StrEnum):
    MIS = "MIS"
    CNC = "CNC"
    NRML = "NRML"


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    COMPLETE = "COMPLETE"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class SignalDirection(StrEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class MarketRegime(StrEnum):
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGE_BOUND = "RANGE_BOUND"
    VOLATILE = "VOLATILE"
    QUIET = "QUIET"
    UNKNOWN = "UNKNOWN"


class Instrument(BaseModel):
    instrument_token: int
    tradingsymbol: str
    name: str = ""
    exchange: Exchange = Exchange.NSE
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
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    oi: int = 0
    ts: datetime


class Signal(BaseModel):
    instrument: Instrument
    direction: SignalDirection
    entry: float
    stop_loss: float
    target1: float
    target2: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    regime: MarketRegime = MarketRegime.UNKNOWN
    reasons: list[str] = Field(default_factory=list)
    strategy_name: str = ""
    suggested_qty: int = 0
    risk_rupees: float = 0.0
    expected_rr: float = 0.0
    ts: datetime = Field(default_factory=datetime.utcnow)


class OrderRequest(BaseModel):
    instrument: Instrument
    side: Side
    quantity: int
    order_type: OrderType = OrderType.MARKET
    product: ProductType = ProductType.NRML
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
    product: ProductType = ProductType.NRML
    pnl: float = 0.0

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
