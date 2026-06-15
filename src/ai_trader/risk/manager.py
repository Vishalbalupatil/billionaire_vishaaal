"""Risk management engine.

Enforces:
- Per-trade risk limits
- Daily loss limit with kill switch
- Portfolio Greeks limits (delta, gamma)
- Max open positions
- Square-off before market close
"""

from __future__ import annotations

import logging
from datetime import datetime

from ai_trader.config import get_settings
from ai_trader.models.domain import Position, Signal
from ai_trader.models.options import Greeks, OptionStrategy

log = logging.getLogger(__name__)


class RiskManager:
    """Central risk management engine."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._daily_pnl: float = 0.0
        self._kill_switch: bool = False
        self._trade_count: int = 0
        self._session_start = datetime.utcnow()

    @property
    def kill_switch_active(self) -> bool:
        return self._kill_switch

    @property
    def daily_pnl(self) -> float:
        return self._daily_pnl

    def activate_kill_switch(self, reason: str = "") -> None:
        self._kill_switch = True
        log.critical("KILL SWITCH ACTIVATED: %s", reason)

    def deactivate_kill_switch(self) -> None:
        self._kill_switch = False
        log.info("Kill switch deactivated")

    def update_daily_pnl(self, pnl: float) -> None:
        self._daily_pnl = pnl
        max_loss = self._settings.max_capital * (self._settings.max_daily_loss_pct / 100)
        if pnl < -max_loss:
            self.activate_kill_switch(
                f"Daily loss limit breached: ₹{pnl:.2f} < -₹{max_loss:.2f}"
            )

    def can_trade(self) -> tuple[bool, str]:
        """Check if trading is allowed."""
        if self._kill_switch:
            return False, "Kill switch is active"

        # Check daily loss
        max_loss = self._settings.max_capital * (self._settings.max_daily_loss_pct / 100)
        if self._daily_pnl < -max_loss:
            return False, f"Daily loss limit breached: ₹{self._daily_pnl:.2f}"

        return True, "OK"

    def validate_signal(self, signal: Signal, open_positions: list[Position]) -> tuple[bool, str]:
        """Validate a trade signal against risk rules."""
        can, reason = self.can_trade()
        if not can:
            return False, reason

        # Max open positions
        if len(open_positions) >= self._settings.max_open_positions:
            return False, f"Max open positions ({self._settings.max_open_positions}) reached"

        # Per-trade risk check
        max_risk = self._settings.max_capital * (self._settings.risk_per_trade_pct / 100)
        if signal.risk_rupees > max_risk:
            return False, f"Risk ₹{signal.risk_rupees:.2f} exceeds max ₹{max_risk:.2f}"

        # Confidence threshold
        if signal.confidence < self._settings.min_signal_confidence:
            return False, f"Confidence {signal.confidence:.2f} below threshold"

        return True, "OK"

    def validate_options_strategy(
        self,
        strategy: OptionStrategy,
        portfolio_greeks: Greeks,
    ) -> tuple[bool, str]:
        """Validate an options strategy against portfolio risk limits."""
        can, reason = self.can_trade()
        if not can:
            return False, reason

        # Portfolio delta limit
        new_delta = abs(portfolio_greeks.delta + strategy.net_greeks.delta)
        if new_delta > self._settings.max_portfolio_delta:
            return False, f"Portfolio delta {new_delta:.2f} would exceed limit {self._settings.max_portfolio_delta}"

        # Portfolio gamma limit
        new_gamma = abs(portfolio_greeks.gamma + strategy.net_greeks.gamma)
        if new_gamma > self._settings.max_portfolio_gamma:
            return False, f"Portfolio gamma {new_gamma:.4f} would exceed limit {self._settings.max_portfolio_gamma}"

        # Max loss check
        if strategy.max_loss > self._settings.max_capital * (self._settings.risk_per_trade_pct / 100):
            return False, f"Strategy max loss ₹{strategy.max_loss:.2f} exceeds per-trade risk"

        return True, "OK"

    def should_square_off(self) -> bool:
        """Check if we should auto square-off (approaching market close)."""
        now = datetime.utcnow()
        # Approximate IST = UTC + 5:30
        ist_hour = (now.hour + 5) % 24
        ist_minute = now.minute + 30
        if ist_minute >= 60:
            ist_hour += 1
            ist_minute -= 60

        sq_parts = self._settings.square_off_time.split(":")
        sq_hour, sq_minute = int(sq_parts[0]), int(sq_parts[1])

        return ist_hour > sq_hour or (ist_hour == sq_hour and ist_minute >= sq_minute)

    def reset_daily(self) -> None:
        """Reset daily counters (call at start of each trading day)."""
        self._daily_pnl = 0.0
        self._trade_count = 0
        self._kill_switch = False
        self._session_start = datetime.utcnow()
        log.info("Daily risk counters reset")
