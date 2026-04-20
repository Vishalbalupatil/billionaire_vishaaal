"""In-memory paper broker: fills MARKET orders at last-known LTP, respects SL/SL-M
triggers, computes brokerage and slippage. Used in paper mode & backtesting."""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime
from typing import Any

from billionaire.broker.base import BrokerClient
from billionaire.models import (
    Instrument,
    Order,
    OrderRequest,
    OrderStatus,
    OrderType,
    Position,
    ProductType,
    Side,
    Trade,
)

log = logging.getLogger(__name__)

# Simple brokerage model (rupees per executed order leg). Tweak per broker plan.
FLAT_BROKERAGE = 20.0
SLIPPAGE_PCT = 0.0005  # 5 bps


class PaperBroker(BrokerClient):
    name = "paper"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._orders: dict[str, Order] = {}
        self._trades: list[Trade] = []
        self._positions: dict[str, Position] = {}  # by tradingsymbol
        self._ltp: dict[int, float] = {}

    # ---- market data feed (called from websocket or backtest) ----
    def on_ltp(self, token: int, price: float) -> None:
        with self._lock:
            self._ltp[token] = float(price)
            self._process_pending(token, price)
            # update position marks
            for pos in self._positions.values():
                if pos.instrument.instrument_token == token:
                    pos.ltp = float(price)

    def _process_pending(self, token: int, price: float) -> None:
        for _oid, order in list(self._orders.items()):
            if order.status != OrderStatus.OPEN:
                continue
            if order.request.instrument.instrument_token != token:
                continue
            ot = order.request.order_type
            trig = order.request.trigger_price or 0.0
            limit = order.request.limit_price or 0.0
            side = order.request.side
            if ot == OrderType.SL_M:
                if (side == Side.BUY and price >= trig) or (side == Side.SELL and price <= trig):
                    self._fill(order, price)
            elif ot == OrderType.SL:
                if (side == Side.BUY and price >= trig and price <= limit) or (
                    side == Side.SELL and price <= trig and price >= limit
                ):
                    self._fill(order, limit or price)
            elif ot == OrderType.LIMIT and (
                (side == Side.BUY and price <= limit) or (side == Side.SELL and price >= limit)
            ):
                self._fill(order, limit)

    # ---- API surface ----
    def instruments(self, exchange: str | None = None) -> list[Instrument]:
        return []

    def quote(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        return {s: {"last_price": 0.0} for s in symbols}

    def ltp(self, symbols: list[str]) -> dict[str, float]:
        return dict.fromkeys(symbols, 0.0)

    def margins(self) -> dict[str, Any]:
        return {"equity": {"available": {"cash": 1_000_000.0}}}

    def positions(self) -> list[Position]:
        with self._lock:
            return list(self._positions.values())

    def holdings(self) -> list[dict[str, Any]]:
        return []

    def order_history(self, order_id: str) -> list[dict[str, Any]]:
        with self._lock:
            o = self._orders.get(order_id)
            return [o.model_dump()] if o else []

    def trades(self) -> list[dict[str, Any]]:
        with self._lock:
            return [t.model_dump() for t in self._trades]

    def place_order(self, req: OrderRequest) -> Order:
        order_id = f"PAPER-{uuid.uuid4().hex[:10].upper()}"
        order = Order(order_id=order_id, request=req, status=OrderStatus.OPEN, broker=self.name)
        with self._lock:
            self._orders[order_id] = order
            # immediate fill for MARKET orders
            if req.order_type == OrderType.MARKET:
                px = self._ltp.get(req.instrument.instrument_token)
                if px is None:
                    # accept at limit_price if provided, else stay open
                    if req.limit_price:
                        self._fill(order, req.limit_price)
                    else:
                        order.message = "MARKET order queued — waiting for LTP."
                else:
                    self._fill(order, px)
        log.info("[PAPER] placed %s %s x%d (%s)", req.side.value, req.instrument.tradingsymbol, req.quantity, order_id)
        return order

    def modify_order(self, order_id: str, **changes: Any) -> Order:
        with self._lock:
            order = self._orders[order_id]
            if "limit_price" in changes:
                order.request.limit_price = changes["limit_price"]
            if "trigger_price" in changes:
                order.request.trigger_price = changes["trigger_price"]
            if "quantity" in changes:
                order.request.quantity = changes["quantity"]
            return order

    def cancel_order(self, order_id: str) -> Order:
        with self._lock:
            order = self._orders.get(order_id)
            if order and order.status == OrderStatus.OPEN:
                order.status = OrderStatus.CANCELLED
                order.message = "Cancelled by user"
            return order or Order(order_id=order_id, request=None, status=OrderStatus.CANCELLED, broker=self.name)  # type: ignore[arg-type]

    # ---- internal ----
    def _apply_slippage(self, side: Side, price: float) -> float:
        return price * (1 + SLIPPAGE_PCT) if side == Side.BUY else price * (1 - SLIPPAGE_PCT)

    def _fill(self, order: Order, price: float) -> None:
        fill_price = round(self._apply_slippage(order.request.side, price), 2)
        order.status = OrderStatus.COMPLETE
        order.filled_qty = order.request.quantity
        order.avg_price = fill_price
        order.ts = datetime.utcnow()

        # update position
        sym = order.request.instrument.tradingsymbol
        qty = order.request.quantity if order.request.side == Side.BUY else -order.request.quantity
        pos = self._positions.get(sym)
        if pos is None:
            self._positions[sym] = Position(
                instrument=order.request.instrument,
                quantity=qty,
                avg_price=fill_price,
                ltp=fill_price,
                product=order.request.product or ProductType.MIS,
            )
        else:
            new_qty = pos.quantity + qty
            if pos.quantity * qty >= 0 and new_qty != 0:
                # averaging
                pos.avg_price = (pos.avg_price * pos.quantity + fill_price * qty) / new_qty
            pos.quantity = new_qty
            if pos.quantity == 0:
                del self._positions[sym]

        trade = Trade(
            trade_id=f"T-{uuid.uuid4().hex[:8].upper()}",
            order_id=order.order_id,
            instrument=order.request.instrument,
            side=order.request.side,
            quantity=order.request.quantity,
            price=fill_price,
        )
        self._trades.append(trade)
        log.info(
            "[PAPER] filled %s %s x%d @ %.2f (brokerage ~%.0f)",
            order.request.side.value,
            sym,
            order.request.quantity,
            fill_price,
            FLAT_BROKERAGE,
        )
