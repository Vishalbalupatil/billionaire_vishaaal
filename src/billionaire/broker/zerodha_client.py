"""Zerodha Kite Connect client wrapper.

Depends on the official ``kiteconnect`` SDK. Kept deliberately thin so that
mapping/adaptation logic lives in one place and tests can monkey-patch the
underlying SDK calls.

Authentication flow (daily):
    1. Open ``kite.login_url()`` in a browser, complete 2FA.
    2. Kite redirects with ``request_token=...``.
    3. Call :meth:`ZerodhaClient.generate_session(request_token)` which returns
       the ``access_token``. Store it in ``KITE_ACCESS_TOKEN`` env var for the
       day.
"""

from __future__ import annotations

import logging
from typing import Any

from billionaire.broker.base import BrokerClient
from billionaire.config import get_settings
from billionaire.models import (
    Exchange,
    Instrument,
    Order,
    OrderRequest,
    OrderStatus,
    Position,
    ProductType,
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
        except ImportError as e:  # pragma: no cover - dep is declared
            raise RuntimeError(
                "kiteconnect not installed. Run: pip install kiteconnect"
            ) from e

        self._settings = settings
        self._kite = KiteConnect(api_key=settings.kite_api_key)
        if settings.kite_access_token:
            self._kite.set_access_token(settings.kite_access_token)

    # ---- auth ----
    def login_url(self) -> str:
        return self._kite.login_url()

    def generate_session(self, request_token: str) -> str:
        """Exchange a request_token for an access_token. Returns access_token."""
        data = self._kite.generate_session(request_token, api_secret=self._settings.kite_api_secret)
        token = data["access_token"]
        self._kite.set_access_token(token)
        log.info("Kite session generated for user %s", data.get("user_id"))
        return token

    # ---- mapping helpers ----
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

    # ---- reference data ----
    def instruments(self, exchange: str | None = None) -> list[Instrument]:
        data = self._kite.instruments(exchange) if exchange else self._kite.instruments()
        return [self._to_instrument(d) for d in data]

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
                out.append(
                    Position(
                        instrument=Instrument(
                            instrument_token=int(p.get("instrument_token") or 0),
                            tradingsymbol=p["tradingsymbol"],
                            exchange=Exchange(p.get("exchange", "NSE")),
                            segment=Segment.EQUITY,
                        ),
                        quantity=int(p["quantity"]),
                        avg_price=float(p.get("average_price") or 0),
                        ltp=float(p.get("last_price") or 0),
                        product=ProductType(p.get("product", "MIS")),
                    )
                )
        return out

    def holdings(self) -> list[dict[str, Any]]:
        return list(self._kite.holdings())

    # ---- orders ----
    def place_order(self, req: OrderRequest) -> Order:
        variety = self._kite.VARIETY_REGULAR
        kite_params = {
            "variety": variety,
            "tradingsymbol": req.instrument.tradingsymbol,
            "exchange": req.instrument.exchange.value,
            "transaction_type": (
                self._kite.TRANSACTION_TYPE_BUY if req.side == Side.BUY else self._kite.TRANSACTION_TYPE_SELL
            ),
            "quantity": req.quantity,
            "product": req.product.value,
            "order_type": req.order_type.value.replace("-", "_"),
            "tag": req.tag[:20] if req.tag else None,
        }
        if req.limit_price is not None:
            kite_params["price"] = req.limit_price
        if req.trigger_price is not None:
            kite_params["trigger_price"] = req.trigger_price

        order_id = self._kite.place_order(**kite_params)
        log.info("Zerodha order placed: %s (%s %s x%d)", order_id, req.side.value, req.instrument.tradingsymbol, req.quantity)
        return Order(order_id=str(order_id), request=req, status=OrderStatus.OPEN, broker=self.name)

    def modify_order(self, order_id: str, **changes: Any) -> Order:
        self._kite.modify_order(variety=self._kite.VARIETY_REGULAR, order_id=order_id, **changes)
        hist = self.order_history(order_id)
        last = hist[-1] if hist else {}
        return Order(
            order_id=order_id,
            request=changes.get("request"),  # type: ignore[arg-type]
            status=OrderStatus(last.get("status", "OPEN")),
            message=last.get("status_message", ""),
            broker=self.name,
        )

    def cancel_order(self, order_id: str) -> Order:
        self._kite.cancel_order(variety=self._kite.VARIETY_REGULAR, order_id=order_id)
        return Order(
            order_id=order_id,
            request=None,  # type: ignore[arg-type]
            status=OrderStatus.CANCELLED,
            broker=self.name,
        )

    def order_history(self, order_id: str) -> list[dict[str, Any]]:
        return list(self._kite.order_history(order_id))

    def trades(self) -> list[dict[str, Any]]:
        return list(self._kite.trades())
