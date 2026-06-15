"""Options-specific domain models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Greeks(BaseModel):
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    iv: float = 0.0


class OptionChainRow(BaseModel):
    strike: float
    expiry: str
    ce_ltp: float = 0.0
    ce_oi: int = 0
    ce_volume: int = 0
    ce_iv: float = 0.0
    ce_greeks: Greeks = Field(default_factory=Greeks)
    pe_ltp: float = 0.0
    pe_oi: int = 0
    pe_volume: int = 0
    pe_iv: float = 0.0
    pe_greeks: Greeks = Field(default_factory=Greeks)
    pcr: float = 0.0


class OptionStrategyType(StrEnum):
    LONG_CALL = "LONG_CALL"
    LONG_PUT = "LONG_PUT"
    SHORT_CALL = "SHORT_CALL"
    SHORT_PUT = "SHORT_PUT"
    BULL_CALL_SPREAD = "BULL_CALL_SPREAD"
    BEAR_PUT_SPREAD = "BEAR_PUT_SPREAD"
    LONG_STRADDLE = "LONG_STRADDLE"
    SHORT_STRADDLE = "SHORT_STRADDLE"
    LONG_STRANGLE = "LONG_STRANGLE"
    SHORT_STRANGLE = "SHORT_STRANGLE"
    IRON_CONDOR = "IRON_CONDOR"
    IRON_BUTTERFLY = "IRON_BUTTERFLY"


class StrategyLeg(BaseModel):
    strike: float
    option_type: str  # "CE" or "PE"
    side: str  # "BUY" or "SELL"
    lots: int = 1
    premium: float = 0.0
    greeks: Greeks = Field(default_factory=Greeks)


class PayoffPoint(BaseModel):
    spot: float
    pnl: float


class OptionStrategy(BaseModel):
    strategy_type: OptionStrategyType
    legs: list[StrategyLeg] = Field(default_factory=list)
    net_premium: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0
    breakeven: list[float] = Field(default_factory=list)
    net_greeks: Greeks = Field(default_factory=Greeks)
    confidence: float = 0.0
    reason: str = ""
    payoff: list[PayoffPoint] = Field(default_factory=list)

    @property
    def risk_reward_ratio(self) -> float:
        if self.max_loss == 0:
            return 0.0
        return abs(self.max_profit / self.max_loss)


class OptionsPosition(BaseModel):
    strategy: OptionStrategy
    entry_spot: float
    current_spot: float = 0.0
    entry_time: str = ""
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    status: str = "OPEN"
