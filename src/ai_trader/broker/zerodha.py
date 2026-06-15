"""Zerodha Kite Connect client implementation.

Authentication flow (daily):
1. Open ``login_url()`` in a browser, complete 2FA.
2. Kite redirects with ``request_token=...``.
3. Call ``generate_session(request_token)`` → stores ``access_token``.
"""

from __future__ import annotations

import logging
from typing import Any

from ai_trader.broker.base import BrokerClient
from ai_trader.config import get_settings
from ai_trader.models.domain import (
    Exchange,
    Instrument,
    Order,
    OrderRequest,
    OrderStatus,
    Position,
    Segment,
    Side,
)

log = logging.getLogger(__name__)


class ZerodhaClient(BrokerClient):
    name = "zerodha"

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.kite_api_key:
            raise RuntimeError("KITE_API_KEY is not configured")

        try:
            from kiteconnect import KiteConnect
        except ImportError as exc:
            raise RuntimeError("kiteconnect not installed. Run: pip install kiteconnect") from exc

        self._settings = settings
        self._kite = KiteConnect(api_key=settings.kite_api_key)
        if settings.kite_access_token:
            self._kite.set_access_token(settings.kite_access_token)

    def login_url(self) -> str:
        return str(self._kite.login_url())

    def generate_session(self, request_token: str) -> str:
        data = self._kite.generate_session(request_token, api_secret=self._settings.kite_api_secret)
        token: str = data["access_token"]
        self._kite.set_access_token(token)
        log.info("Kite session generated for user %s", data.get("user_id"))
        return token

    @staticmethod
    def _to_instrument(d: dict[str, Any]) -> Instrument:
        exch = (d.get("exchange") or "NSE").upper()
        seg = (d.get("segment") or "").upper()
        if "OPT" in seg:
            segment = Segment.OPTIONS
        elif "FUT" in seg or exch.endswith("NFO") or exch.endswith("BFO"):
            segment = Segment.FUTURES
        elif seg == "INDICES":
            segment = Segment.INDEX
        else:
            segment = Segment.EQUITY
        return Instrument(
            instrument_token=int(d["instrument_token"]),
            tradingsymbol=str(d["tradingsymbol"]),
            name=str(d.get("name") or ""),
            exchange=Exchange(exch) if exch in Exchange.__members__ else Exchange.NSE,
            segment=segment,
            lot_size=int(d.get("lot_size") or 1),
            tick_size=float(d.get("tick_size") or 0.05),
            expiry=str(d["expiry"]) if d.get("expiry") else None,
            strike=float(d["strike"]) if d.get("strike") else None,
            option_type=d.get("instrument_type") if d.get("instrument_type") in {"CE", "PE"} else None,
        )

    def instruments(self, exchange: str | None = None) -> list[Instrument]:
        data = self._kite.instruments(exchange) if exchange else self._kite.instruments()
        return [self._to_instrument(d) for d in data]

    def historical_data(
        self,
        instrument_token: int,
        from_dt: Any,
        to_dt: Any,
        interval: str = "minute",
    ) -> list[dict[str, Any]]:
        return list(self._kite.historical_data(instrument_token, from_dt, to_dt, interval))

    def quote(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        return dict(self._kite.quote(symbols))

    def ltp(self, symbols: list[str]) -> dict[str, float]:
        raw = self._kite.ltp(symbols)
        return {k: float(v["last_price"]) for k, v in raw.items()}

    def margins(self) -> dict[str, Any]:
        return dict(self._kite.margins())

    def positions(self) -> list[Position]:
        raw = self._kite.positions()
        out: list[Position] = []
        for bucket in ("net", "day"):
            for p in raw.get(bucket, []):
                inst = Instrument(
                    instrument_token=int(p.get("instrument_token") or 0),
                    tradingsymbol=str(p.get("tradingsymbol") or ""),
                    exchange=Exchange(p.get("exchange", "NSE")),
                )
                out.append(Position(
                    instrument=inst,
                    quantity=int(p.get("quantity") or 0),
                    avg_price=float(p.get("average_price") or 0),
                    ltp=float(p.get("last_price") or 0),
                    pnl=float(p.get("pnl") or 0),
                ))
        return out

    def place_order(self, request: OrderRequest) -> Order:
        params: dict[str, Any] = {
            "tradingsymbol": request.instrument.tradingsymbol,
            "exchange": request.instrument.exchange.value,
            "transaction_type": request.side.value,
            "quantity": request.quantity,
            "order_type": request.order_type.value,
            "product": request.product.value,
        }
        if request.limit_price is not None:
            params["price"] = request.limit_price
        if request.trigger_price is not None:
            params["trigger_price"] = request.trigger_price
        if request.tag:
            params["tag"] = request.tag

        order_id = self._kite.place_order(variety="regular", **params)
        log.info("Placed order %s: %s %s %d", order_id, request.side.value, request.instrument.tradingsymbol, request.quantity)
        return Order(
            order_id=str(order_id),
            request=request,
            status=OrderStatus.PENDING,
            broker="zerodha",
        )

    def cancel_order(self, order_id: str) -> bool:
        try:
            self._kite.cancel_order(variety="regular", order_id=order_id)
            return True
        except Exception as exc:
            log.error("Failed to cancel order %s: %s", order_id, exc)
            return False

    def orders(self) -> list[Order]:
        raw = self._kite.orders()
        result: list[Order] = []
        for o in raw:
            status_map = {
                "COMPLETE": OrderStatus.COMPLETE,
                "REJECTED": OrderStatus.REJECTED,
                "CANCELLED": OrderStatus.CANCELLED,
                "OPEN": OrderStatus.OPEN,
            }
            inst = Instrument(
                instrument_token=int(o.get("instrument_token") or 0),
                tradingsymbol=str(o.get("tradingsymbol") or ""),
                exchange=Exchange(o.get("exchange", "NSE")),
            )
            side = Side.BUY if o.get("transaction_type") == "BUY" else Side.SELL
            result.append(Order(
                order_id=str(o.get("order_id", "")),
                request=OrderRequest(instrument=inst, side=side, quantity=int(o.get("quantity") or 0)),
                status=status_map.get(o.get("status", ""), OrderStatus.PENDING),
                filled_qty=int(o.get("filled_quantity") or 0),
                avg_price=float(o.get("average_price") or 0),
                broker="zerodha",
            ))
        return result
