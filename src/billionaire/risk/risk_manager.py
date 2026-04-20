"""Risk manager: all pre-trade checks, sizing, daily drawdown guard, cooldown
after loss streak, kill switch, and auto square-off.

All public methods are pure / side-effect-free except those prefixed with
``register_`` which update internal counters. They return structured
:class:`RiskDecision` objects so callers can log WHY an order was blocked."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import date, datetime, time

from billionaire.config import Settings, get_settings
from billionaire.models import Instrument, OrderRequest, Segment, Signal

log = logging.getLogger(__name__)


@dataclass
class RiskDecision:
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    suggested_qty: int = 0
    risk_rupees: float = 0.0

    def deny(self, reason: str) -> RiskDecision:
        self.allowed = False
        self.reasons.append(reason)
        return self


def _parse_time(s: str) -> time:
    hh, mm = s.split(":")
    return time(int(hh), int(mm))


class RiskManager:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._lock = threading.RLock()
        self._day: date = datetime.now().date()
        self._realised_pnl_today: float = 0.0
        self._trades_today: int = 0
        self._open_positions: int = 0
        self._last_losses: int = 0  # consecutive losses
        self._kill_switch: bool = False
        self._symbol_cooldown: dict[str, datetime] = {}

    # ---- state mutation ----
    def register_trade_closed(self, pnl: float, symbol: str) -> None:
        with self._lock:
            self._rollover_if_new_day()
            self._realised_pnl_today += pnl
            self._trades_today += 1
            if pnl < 0:
                self._last_losses += 1
                self._symbol_cooldown[symbol] = datetime.now()
            else:
                self._last_losses = 0

    def register_position_opened(self) -> None:
        with self._lock:
            self._open_positions += 1

    def register_position_closed(self) -> None:
        with self._lock:
            self._open_positions = max(0, self._open_positions - 1)

    def engage_kill_switch(self, reason: str = "manual") -> None:
        with self._lock:
            self._kill_switch = True
            log.warning("KILL SWITCH ENGAGED: %s", reason)

    def release_kill_switch(self) -> None:
        with self._lock:
            self._kill_switch = False

    def _rollover_if_new_day(self) -> None:
        today = datetime.now().date()
        if today != self._day:
            self._day = today
            self._realised_pnl_today = 0.0
            self._trades_today = 0
            self._last_losses = 0

    # ---- checks ----
    def _within_market_hours(self, now: datetime | None = None) -> bool:
        now = now or datetime.now()
        open_t = _parse_time(self.settings.market_open)
        close_t = _parse_time(self.settings.market_close)
        return open_t <= now.time() <= close_t

    def _past_square_off(self, now: datetime | None = None) -> bool:
        now = now or datetime.now()
        sq = _parse_time(self.settings.square_off_time)
        return now.time() >= sq

    def position_size(self, entry: float, stop_loss: float, instrument: Instrument | None = None) -> int:
        """Position size via capital-at-risk model."""
        risk_per_unit = abs(entry - stop_loss)
        if risk_per_unit <= 0:
            return 0
        cap = self.settings.account_capital
        risk_budget = cap * (self.settings.risk_per_trade_pct / 100.0)
        qty = int(risk_budget // risk_per_unit)
        if instrument and instrument.segment in (Segment.FUTURES, Segment.OPTIONS):
            # round to lot size
            lot = max(instrument.lot_size, 1)
            qty = (qty // lot) * lot
        return max(qty, 0)

    # ---- pre-trade gate ----
    def check_signal(self, signal: Signal, live: bool = False) -> RiskDecision:
        decision = RiskDecision(allowed=True)
        with self._lock:
            self._rollover_if_new_day()
            s = self.settings

            if self._kill_switch:
                return decision.deny("Kill switch is engaged.")

            if live and not s.live_trading_enabled:
                return decision.deny(
                    "Live trading requires APP_MODE=live AND LIVE_TRADING_UNLOCK=I_UNDERSTAND_THE_RISKS."
                )

            if not self._within_market_hours():
                decision.reasons.append("Outside configured market hours — order staged for paper only.")
                if live:
                    return decision.deny("Outside market hours")

            if self._past_square_off():
                if live:
                    return decision.deny("Past square-off time; new entries blocked.")
                decision.reasons.append("Past square-off time — size reduced.")

            if self._trades_today >= s.max_trades_per_day:
                return decision.deny(f"Daily trade cap {s.max_trades_per_day} reached.")

            if self._open_positions >= s.max_open_positions:
                return decision.deny(f"Max open positions {s.max_open_positions} reached.")

            if self._last_losses >= s.cooldown_after_losses:
                return decision.deny(
                    f"Cooldown: {self._last_losses} consecutive losing trades (threshold {s.cooldown_after_losses})."
                )

            max_loss = s.account_capital * (s.max_daily_loss_pct / 100.0)
            if -self._realised_pnl_today >= max_loss:
                return decision.deny(f"Daily drawdown cap hit ({-self._realised_pnl_today:.0f} / {max_loss:.0f}).")

            qty = signal.suggested_qty or self.position_size(signal.entry, signal.stop_loss, signal.instrument)
            if qty <= 0:
                return decision.deny("Position size computed as 0 (SL too wide for capital/risk budget).")

            decision.suggested_qty = qty
            decision.risk_rupees = qty * abs(signal.entry - signal.stop_loss)
            if decision.risk_rupees > s.account_capital * (s.risk_per_trade_pct / 100.0) * 1.05:
                return decision.deny("Computed risk exceeds per-trade budget (safety check).")

        return decision

    def check_order(self, req: OrderRequest, live: bool = False) -> RiskDecision:
        decision = RiskDecision(allowed=True)
        with self._lock:
            if self._kill_switch:
                return decision.deny("Kill switch is engaged.")
            if req.quantity <= 0:
                return decision.deny("Quantity must be positive.")
            if live and not self.settings.live_trading_enabled:
                return decision.deny("Live trading not unlocked.")
            if self._open_positions >= self.settings.max_open_positions:
                return decision.deny("Max open positions reached.")
        return decision

    # ---- status ----
    def status(self) -> dict:
        with self._lock:
            s = self.settings
            max_loss = s.account_capital * (s.max_daily_loss_pct / 100.0)
            return {
                "kill_switch": self._kill_switch,
                "open_positions": self._open_positions,
                "trades_today": self._trades_today,
                "realised_pnl_today": round(self._realised_pnl_today, 2),
                "daily_loss_budget": round(max_loss, 2),
                "consecutive_losses": self._last_losses,
                "within_market_hours": self._within_market_hours(),
                "past_square_off": self._past_square_off(),
                "live_trading_enabled": s.live_trading_enabled,
                "app_mode": s.app_mode.value,
            }
