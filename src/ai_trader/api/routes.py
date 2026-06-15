"""REST API endpoints for the AI trading platform."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai_trader.config import get_settings
from ai_trader.execution.scheduler import session_info

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

# These will be set by the app on startup
_engine = None
_risk = None
_broker = None
_db = None
_auto_trader = None


def set_dependencies(
    engine: Any,
    risk: Any,
    broker: Any,
    db: Any,
    auto_trader: Any = None,
) -> None:
    global _engine, _risk, _broker, _db, _auto_trader
    _engine = engine
    _risk = risk
    _broker = broker
    _db = db
    _auto_trader = auto_trader


# --- System ---


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "mode": settings.trading_mode.value,
        "session": session_info(),
    }


@router.get("/config")
def config() -> dict:
    settings = get_settings()
    return {
        "trading_mode": settings.trading_mode.value,
        "max_capital": settings.max_capital,
        "risk_per_trade_pct": settings.risk_per_trade_pct,
        "max_daily_loss_pct": settings.max_daily_loss_pct,
        "max_open_positions": settings.max_open_positions,
        "min_signal_confidence": settings.min_signal_confidence,
        "default_lot_size": settings.default_lot_size,
    }


# --- Risk ---


@router.get("/risk")
def risk_status() -> dict:
    if not _risk:
        raise HTTPException(503, "Risk manager not initialized")
    return {
        "kill_switch": _risk.kill_switch_active,
        "daily_pnl": _risk.daily_pnl,
        "can_trade": _risk.can_trade()[0],
        "reason": _risk.can_trade()[1],
        "should_square_off": _risk.should_square_off(),
    }


class KillSwitchRequest(BaseModel):
    active: bool
    reason: str = ""


@router.post("/risk/kill-switch")
def toggle_kill_switch(req: KillSwitchRequest) -> dict:
    if not _risk:
        raise HTTPException(503, "Risk manager not initialized")
    if req.active:
        _risk.activate_kill_switch(req.reason)
    else:
        _risk.deactivate_kill_switch()
    return {"kill_switch": _risk.kill_switch_active}


# --- Signals ---


@router.get("/signals")
def get_signals() -> list[dict]:
    if not _engine:
        return []
    return [s.model_dump() for s in _engine.signals[-50:]]


@router.get("/signals/latest")
def latest_signal() -> dict | None:
    if not _engine or not _engine.signals:
        return None
    return _engine.signals[-1].model_dump()


# --- Strategies ---


@router.get("/strategies")
def get_strategies() -> list[dict]:
    if not _engine:
        return []
    return [s.model_dump() for s in _engine.strategies[-20:]]


# --- Positions ---


@router.get("/positions")
def get_positions() -> list[dict]:
    if not _broker:
        return []
    try:
        return [p.model_dump() for p in _broker.positions()]
    except Exception as exc:
        log.error("Failed to fetch positions: %s", exc)
        return []


@router.get("/positions/options")
def get_options_positions() -> list[dict]:
    if not _engine:
        return []
    return [p.model_dump() for p in _engine.active_positions]


# --- Orders ---


@router.get("/orders")
def get_orders() -> list[dict]:
    if not _broker:
        return []
    try:
        return [o.model_dump() for o in _broker.orders()]
    except Exception:
        return []


# --- Account ---


@router.get("/account/margins")
def get_margins() -> dict:
    if not _broker:
        return {}
    try:
        return _broker.margins()
    except Exception as exc:
        log.error("Failed to fetch margins: %s", exc)
        return {}


# --- Auth ---


@router.get("/auth/login-url")
def login_url() -> dict:
    if not _broker:
        raise HTTPException(503, "Broker not initialized")
    return {"url": _broker.login_url()}


class SessionRequest(BaseModel):
    request_token: str


@router.post("/auth/session")
def create_session(req: SessionRequest) -> dict:
    if not _broker:
        raise HTTPException(503, "Broker not initialized")
    try:
        token = _broker.generate_session(req.request_token)
        return {"access_token": token}
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc


# --- Database stats ---


@router.get("/stats")
def trade_stats() -> dict:
    if not _db:
        return {}
    return _db.get_trade_stats()


@router.get("/stats/daily-pnl")
def daily_pnl(days: int = 30) -> list[dict]:
    if not _db:
        return []
    return _db.get_daily_pnl(days)


@router.get("/stats/signals")
def signal_history(limit: int = 50) -> list[dict]:
    if not _db:
        return []
    return _db.get_recent_signals(limit)


# =============================================================================
# Scanner & Auto-Trader endpoints
# =============================================================================


@router.get("/scanner/results")
def scanner_results() -> list[dict]:
    """Get latest equity scan results (ranked)."""
    if not _auto_trader:
        return []
    return [r.model_dump() for r in _auto_trader.scan_results]


@router.get("/scanner/patterns")
def scanner_patterns() -> list[dict]:
    """Get detected chart patterns."""
    if not _auto_trader:
        return []
    return [p.model_dump() for p in _auto_trader.patterns]


@router.get("/scanner/trends")
def scanner_trends() -> dict[str, dict]:
    """Get trend analysis for scanned symbols."""
    if not _auto_trader:
        return {}
    return {sym: t.model_dump() for sym, t in _auto_trader.trends.items()}


@router.get("/auto-trader/status")
def auto_trader_status() -> dict:
    """Get auto-trader status overview."""
    if not _auto_trader:
        return {"active": False}
    return {
        "active": True,
        "active_trades": _auto_trader.active_trades,
        "scan_results_count": len(_auto_trader.scan_results),
        "patterns_count": len(_auto_trader.patterns),
        "trends_count": len(_auto_trader.trends),
    }


@router.get("/auto-trader/trades")
def auto_trader_active_trades() -> dict:
    """Get currently active auto-trades."""
    if not _auto_trader:
        return {}
    return _auto_trader.active_trades


@router.get("/auto-trader/log")
def auto_trader_log(limit: int = 50) -> list[dict]:
    """Get auto-trader activity log."""
    if not _auto_trader:
        return []
    return [entry.model_dump() for entry in _auto_trader.trade_log[-limit:]]
