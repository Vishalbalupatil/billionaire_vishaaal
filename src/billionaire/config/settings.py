"""Centralised, typed configuration loaded from environment variables (.env).

No credentials are ever hardcoded in source. Secrets come from env only.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppMode(str, Enum):
    ANALYSIS = "analysis"
    PAPER = "paper"
    LIVE = "live"


class Settings(BaseSettings):
    """Application settings. All values are overridable via env vars or .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Mode
    app_mode: AppMode = AppMode.ANALYSIS
    live_trading_unlock: str = ""

    # Zerodha
    kite_api_key: str = ""
    kite_api_secret: str = ""
    kite_access_token: str = ""
    kite_user_id: str = ""

    # Capital / risk
    account_capital: float = 100_000.0
    risk_per_trade_pct: float = 0.75
    max_daily_loss_pct: float = 2.0
    max_open_positions: int = 5
    max_trades_per_day: int = 10
    cooldown_after_losses: int = 2

    # Market hours (IST)
    market_open: str = "09:15"
    market_close: str = "15:30"
    square_off_time: str = "15:20"

    # Forecasting
    seed_history_on_boot: bool = True
    seed_history_lookback_minutes: int = 240

    # Storage
    database_url: str = "sqlite:///./data/billionaire.db"

    # API / Dashboard
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    dashboard_origin: str = "http://localhost:5173"

    # Alerts
    alerts_console: bool = True
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_to: str = ""

    # Logging
    log_level: str = "INFO"
    log_dir: str = "./logs"

    # Paths
    project_root: Path = Field(default_factory=lambda: Path.cwd())

    @field_validator("log_level")
    @classmethod
    def _upper_level(cls, v: str) -> str:
        return v.upper()

    # Computed helpers
    @property
    def live_trading_enabled(self) -> bool:
        """Live trading requires BOTH mode=live AND the explicit unlock phrase."""
        return self.app_mode == AppMode.LIVE and self.live_trading_unlock == "I_UNDERSTAND_THE_RISKS"

    @property
    def paper_trading(self) -> bool:
        return self.app_mode == AppMode.PAPER

    @property
    def analysis_only(self) -> bool:
        return self.app_mode == AppMode.ANALYSIS


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
