"""Order manager: orchestrates risk checks, broker calls, persistence, and alerts.

In analysis mode: nothing is placed — signals are logged and alerted only.
In paper mode  : PaperBroker is used regardless of credentials.
In live mode   : orders only go out if ``settings.live_trading_enabled`` is true
                 (explicit unlock), otherwise the manager refuses.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any

from billionaire.broker.base import BrokerClient
from billionaire.config import AppMode, Settings, get_settings
from billionaire.execution.paper_broker import PaperBroker
from billionaire.models import (
    Order,
    OrderRequest,
    OrderStatus,
    OrderType,
    ProductType,
    Segment,
    Side,
    Signal,
)
from billionaire.risk.risk_manager import RiskManager
from billionaire.storage import get_database

log = logging.getLogger(__name__)


class OrderManager:
    def __init__(
        self,
        risk: RiskManager,
        live_broker: BrokerClient | None = None,
        paper_broker: PaperBroker | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.risk = risk
        self.paper_broker = paper_broker or PaperBroker()
        self.live_broker = live_broker
        self._db = get_database()
        self._seen_signatures: set[str] = set()
        self._lock = threading.RLock()

    # ---- duplicate guard ----
    @staticmethod
    def _signature(sig: Signal) -> str:
        return f"{sig.strategy}|{sig.instrument.tradingsymbol}|{sig.direction.value}|{round(sig.entry,2)}|{round(sig.stop_loss,2)}"

    def _is_duplicate(self, sig: Signal) -> bool:
        key = self._signature(sig)
        with self._lock:
            if key in self._seen_signatures:
                return True
            self._seen_signatures.add(key)
        return False

    # ---- signal -> order ----
    def handle_signal(self, sig: Signal) -> dict[str, Any]:
        """Process a generated signal according to current app mode."""
        self._db.save_signal(sig)
        self._db.audit("signal", payload={"strategy": sig.strategy, "symbol": sig.instrument.tradingsymbol,
                                          "dir": sig.direction.value, "conf": sig.confidence})

        mode = self.settings.app_mode
        if mode == AppMode.ANALYSIS:
            log.info("[ANALYSIS] %s", sig.explain())
            return {"mode": "analysis", "placed": False, "signal": sig.model_dump()}

        if self._is_duplicate(sig):
            log.info("Duplicate signal suppressed: %s", self._signature(sig))
            return {"mode": mode.value, "placed": False, "reason": "duplicate"}

        # Always run risk checks, annotate size
        live = mode == AppMode.LIVE
        decision = self.risk.check_signal(sig, live=live)
        if not decision.allowed:
            log.warning("Risk blocked signal: %s", "; ".join(decision.reasons))
            return {"mode": mode.value, "placed": False, "reason": decision.reasons, "signal": sig.model_dump()}

        sig.suggested_qty = decision.suggested_qty
        sig.risk_rupees = decision.risk_rupees

        req = self._build_entry_request(sig)
        order = self._place(req, live=live)

        return {
            "mode": mode.value,
            "placed": order is not None and order.status not in (OrderStatus.REJECTED,),
            "order": order.model_dump() if order else None,
            "signal": sig.model_dump(),
            "risk": decision.reasons,
        }

    def _build_entry_request(self, sig: Signal) -> OrderRequest:
        product = ProductType.MIS
        if sig.instrument.segment == Segment.OPTIONS:
            product = ProductType.NRML
        side = Side.BUY  # BUY for long, BUY on CE/PE for option long; SELL handled below
        if sig.direction.value == "BEARISH" and sig.instrument.segment == Segment.EQUITY:
            side = Side.SELL  # intraday short
        return OrderRequest(
            instrument=sig.instrument,
            side=side,
            quantity=sig.suggested_qty,
            order_type=OrderType.MARKET,
            product=product,
            tag=sig.strategy[:20],
        )

    def _place(self, req: OrderRequest, live: bool) -> Order | None:
        broker = self.live_broker if live and self.live_broker else self.paper_broker
        if live and broker is self.paper_broker:
            log.warning("Live requested but no live broker configured — falling back to paper.")
        try:
            order = broker.place_order(req)
        except (RuntimeError, ValueError, KeyError) as e:  # pragma: no cover
            log.exception("broker place_order failed: %s", e)
            order = Order(order_id="FAILED", request=req, status=OrderStatus.REJECTED, message=str(e), broker=broker.name)
        self._db.save_order(order)
        self._db.audit("order", payload={"order_id": order.order_id, "broker": order.broker, "status": order.status.value})
        if order.status == OrderStatus.COMPLETE:
            self.risk.register_position_opened()
        return order

    # ---- direct order APIs (manual close / emergency) ----
    def place_manual(self, req: OrderRequest) -> Order:
        live = self.settings.app_mode == AppMode.LIVE
        decision = self.risk.check_order(req, live=live)
        if not decision.allowed:
            return Order(order_id="BLOCKED", request=req, status=OrderStatus.REJECTED,
                         message="; ".join(decision.reasons), broker="blocked")
        return self._place(req, live=live) or Order(
            order_id="UNKNOWN", request=req, status=OrderStatus.REJECTED, broker="unknown"
        )

    def cancel(self, order_id: str) -> Order:
        broker = self.live_broker or self.paper_broker
        res = broker.cancel_order(order_id)
        self._db.save_order(res)
        return res

    # ---- auto square-off ----
    def auto_square_off(self) -> list[Order]:
        """Force-close MIS positions at/after square-off time."""
        now = datetime.now().time()
        sq_time = datetime.strptime(self.settings.square_off_time, "%H:%M").time()
        if now < sq_time:
            return []
        broker = self.live_broker if self.settings.app_mode == AppMode.LIVE else self.paper_broker
        closed: list[Order] = []
        for pos in broker.positions():
            if pos.quantity == 0:
                continue
            side = Side.SELL if pos.quantity > 0 else Side.BUY
            req = OrderRequest(
                instrument=pos.instrument,
                side=side,
                quantity=abs(pos.quantity),
                order_type=OrderType.MARKET,
                product=pos.product,
                tag="SQUARE_OFF",
            )
            closed.append(broker.place_order(req))
        return closed
