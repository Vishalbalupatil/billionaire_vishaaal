"""Typed application settings loaded from environment / .env file."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic_settings import BaseSettings


class TradingMode(StrEnum):
    ANALYSIS = "analysis"
    PAPER = "paper"
    LIVE = "live"


class Settings(BaseSettings):
    # Zerodha
    kite_api_key: str = ""
    kite_api_secret: str = ""
    kite_access_token: str = ""

    # Trading
    trading_mode: TradingMode = TradingMode.PAPER
    live_unlock_phrase: str = "I_ACCEPT_RISK"

    # Capital & Risk
    max_capital: float = 100_000.0
    risk_per_trade_pct: float = 2.0
    max_daily_loss_pct: float = 5.0
    max_open_positions: int = 5
    max_portfolio_delta: float = 500.0
    max_portfolio_gamma: float = 100.0

    # Options defaults
    default_lot_size: int = 25  # Nifty lot
    max_option_premium_pct: float = 3.0  # max % of capital per option leg

    # Market schedule (IST)
    market_open: str = "09:15"
    market_close: str = "15:30"
    square_off_time: str = "15:15"

    # AI model
    min_signal_confidence: float = 0.60
    lookback_candles: int = 100

    # Alerts
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
