"""FastAPI routes that power the dashboard."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from billionaire.config import AppMode
from billionaire.models import (
    Exchange,
    Instrument,
    MarketRegime,
    OrderRequest,
    OrderType,
    ProductType,
    Segment,
    SetupType,
    Side,
    Signal,
    SignalDirection,
)
from billionaire.runtime import get_runtime


class TickIn(BaseModel):
    instrument_token: int
    ltp: float
    volume: int = 0
    oi: int = 0


class ManualOrderIn(BaseModel):
    tradingsymbol: str
    exchange: str = "NSE"
    segment: str = "EQUITY"
    side: str  # "BUY" | "SELL"
    quantity: int
    order_type: str = "MARKET"
    product: str = "MIS"
    limit_price: float | None = None
    trigger_price: float | None = None
    instrument_token: int = 0
    tag: str = "manual"


class SimSignalIn(BaseModel):
    """Generate a synthetic signal (for demos / smoke tests)."""
    strategy: str = "nifty_momentum_breakout"
    symbol: str = "NIFTY"
    exchange: str = "NSE"
    direction: str = "BULLISH"
    entry: float
    stop_loss: float
    target1: float
    target2: float | None = None
    confidence: float = 0.6
    instrument_token: int = 0
    seed_ltp: bool = True


def build_router() -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, Any]:
        r = get_runtime()
        ws_health = r.ws.health() if r.ws else {"connected": False, "tokens_subscribed": 0}
        return {
            "status": "ok",
            "mode": r.settings.app_mode.value,
            "live_trading_enabled": r.settings.live_trading_enabled,
            "broker": "zerodha" if r.live_broker else "paper-only",
            "websocket": ws_health,
        }

    @router.get("/config")
    def config() -> dict[str, Any]:
        s = get_runtime().settings
        return {
            "app_mode": s.app_mode.value,
            "live_trading_enabled": s.live_trading_enabled,
            "account_capital": s.account_capital,
            "risk_per_trade_pct": s.risk_per_trade_pct,
            "max_daily_loss_pct": s.max_daily_loss_pct,
            "max_open_positions": s.max_open_positions,
            "max_trades_per_day": s.max_trades_per_day,
            "market_open": s.market_open,
            "market_close": s.market_close,
            "square_off_time": s.square_off_time,
        }

    @router.get("/risk")
    def risk_status() -> dict[str, Any]:
        return get_runtime().risk.status()

    @router.post("/risk/kill")
    def kill(reason: str = "manual") -> dict[str, Any]:
        get_runtime().risk.engage_kill_switch(reason)
        return {"kill_switch": True, "reason": reason}

    @router.post("/risk/release")
    def release_kill() -> dict[str, Any]:
        get_runtime().risk.release_kill_switch()
        return {"kill_switch": False}

    @router.get("/portfolio")
    def portfolio() -> dict[str, Any]:
        snap = get_runtime().portfolio.snapshot()
        return {
            "positions": [p.model_dump() for p in snap.positions],
            "unrealized_pnl": snap.unrealized_pnl,
            "realized_pnl": snap.realized_pnl,
            "gross_exposure": snap.gross_exposure,
            "net_exposure": snap.net_exposure,
            "count_long": snap.count_long,
            "count_short": snap.count_short,
        }

    @router.get("/signals")
    def signals(limit: int = 50) -> list[dict[str, Any]]:
        return get_runtime().db.recent_signals(limit=limit)

    @router.get("/orders")
    def orders(limit: int = 50) -> list[dict[str, Any]]:
        return get_runtime().db.recent_orders(limit=limit)

    @router.get("/trades")
    def trades(limit: int = 50) -> list[dict[str, Any]]:
        return get_runtime().db.recent_trades(limit=limit)

    @router.post("/tick")
    def ingest_tick(tick: TickIn) -> dict[str, Any]:
        """Accept an external tick (useful for demos / paper simulation)."""
        from datetime import datetime

        from billionaire.models import Tick

        t = Tick(
            instrument_token=tick.instrument_token,
            ltp=tick.ltp,
            volume=tick.volume,
            oi=tick.oi,
            ts=datetime.utcnow(),
        )
        r = get_runtime()
        r.candle_builder.on_tick(t)
        r.paper_broker.on_ltp(tick.instrument_token, tick.ltp)
        return {"ok": True}

    @router.post("/sim/signal")
    def sim_signal(s: SimSignalIn) -> dict[str, Any]:
        """Feed a hand-crafted signal to the order manager — demo/paper only."""
        inst = Instrument(
            instrument_token=s.instrument_token,
            tradingsymbol=s.symbol,
            exchange=Exchange(s.exchange),
            segment=Segment.INDEX if s.symbol.upper() in {"NIFTY", "BANKNIFTY"} else Segment.EQUITY,
        )
        sig = Signal(
            instrument=inst,
            setup=SetupType.MOMENTUM_BREAKOUT,
            direction=SignalDirection(s.direction),
            entry=s.entry,
            stop_loss=s.stop_loss,
            target1=s.target1,
            target2=s.target2,
            confidence=s.confidence,
            reasons=["Simulated signal for demo"],
            invalidation=["Hypothetical — for UI testing"],
            regime=MarketRegime.UNKNOWN,
            strategy=s.strategy,
        )
        r = get_runtime()
        if s.seed_ltp:
            # Seed the paper broker's LTP cache at the signal's entry price so
            # demo MARKET orders fill deterministically without a separate tick.
            r.paper_broker.on_ltp(s.instrument_token, s.entry)
        return r.orders.handle_signal(sig)

    @router.post("/orders/manual")
    def manual_order(o: ManualOrderIn) -> dict[str, Any]:
        r = get_runtime()
        if r.settings.app_mode == AppMode.ANALYSIS:
            raise HTTPException(400, "Analysis mode — order placement disabled.")
        inst = Instrument(
            instrument_token=o.instrument_token,
            tradingsymbol=o.tradingsymbol,
            exchange=Exchange(o.exchange),
            segment=Segment(o.segment),
        )
        req = OrderRequest(
            instrument=inst,
            side=Side(o.side),
            quantity=o.quantity,
            order_type=OrderType(o.order_type),
            product=ProductType(o.product),
            limit_price=o.limit_price,
            trigger_price=o.trigger_price,
            tag=o.tag,
        )
        order = r.orders.place_manual(req)
        return order.model_dump()

    @router.post("/orders/{order_id}/cancel")
    def cancel(order_id: str) -> dict[str, Any]:
        return get_runtime().orders.cancel(order_id).model_dump()

    @router.post("/square-off")
    def square_off() -> dict[str, Any]:
        closed = get_runtime().orders.auto_square_off()
        return {"closed": len(closed), "orders": [c.model_dump() for c in closed]}

    return router
