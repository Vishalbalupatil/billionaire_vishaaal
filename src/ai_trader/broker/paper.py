"""Paper trading broker — simulates order execution in memory.

Used in paper mode for testing strategies without real money.
Fills are simulated at market price with a configurable slippage model.
"""

from __future__ import annotations

import logging
import uuid

from ai_trader.broker.base import BrokerClient
from ai_trader.models.domain import (
    Instrument,
    Order,
    OrderRequest,
    OrderStatus,
    Position,
    Side,
)

log = logging.getLogger(__name__)


class PaperBroker(BrokerClient):
    name = "paper"

    def __init__(self, initial_capital: float = 100_000.0, slippage_bps: float = 5.0) -> None:
        self._capital = initial_capital
        self._initial_capital = initial_capital
        self._slippage_bps = slippage_bps
        self._positions: dict[str, Position] = {}
        self._orders: list[Order] = []
        self._last_prices: dict[str, float] = {}

    @property
    def capital(self) -> float:
        return self._capital

    @property
    def pnl(self) -> float:
        return self._capital - self._initial_capital

    def set_price(self, tradingsymbol: str, price: float) -> None:
        self._last_prices[tradingsymbol] = price

    def login_url(self) -> str:
        return "paper://login"

    def generate_session(self, request_token: str) -> str:
        return "paper_access_token"

    def instruments(self, exchange: str | None = None) -> list[Instrument]:
        return []

    def historical_data(self, instrument_token: int, from_dt: object, to_dt: object, interval: str = "minute") -> list[dict]:
        return []

    def quote(self, symbols: list[str]) -> dict[str, dict]:
        return {s: {"last_price": self._last_prices.get(s, 0)} for s in symbols}

    def ltp(self, symbols: list[str]) -> dict[str, float]:
        return {s: self._last_prices.get(s, 0) for s in symbols}

    def margins(self) -> dict:
        return {
            "equity": {"available": {"live_balance": self._capital}},
            "commodity": {"available": {"live_balance": 0}},
        }

    def positions(self) -> list[Position]:
        result: list[Position] = []
        for sym, pos in self._positions.items():
            ltp = self._last_prices.get(sym, pos.avg_price)
            result.append(pos.model_copy(update={"ltp": ltp, "pnl": (ltp - pos.avg_price) * pos.quantity}))
        return result

    def place_order(self, request: OrderRequest) -> Order:
        order_id = f"paper_{uuid.uuid4().hex[:12]}"
        symbol = request.instrument.tradingsymbol

        fill_price = self._last_prices.get(symbol, request.limit_price or 0)
        if fill_price <= 0:
            return Order(
                order_id=order_id,
                request=request,
                status=OrderStatus.REJECTED,
                message="No price available for paper fill",
                broker="paper",
            )

        # Apply slippage
        slippage = fill_price * (self._slippage_bps / 10_000)
        if request.side == Side.BUY:
            fill_price += slippage
        else:
            fill_price -= slippage

        # Update position
        existing = self._positions.get(symbol)
        if existing:
            if request.side == Side.BUY:
                new_qty = existing.quantity + request.quantity
                if new_qty != 0:
                    new_avg = (existing.avg_price * existing.quantity + fill_price * request.quantity) / new_qty
                else:
                    new_avg = 0
                    realized = (fill_price - existing.avg_price) * request.quantity
                    self._capital += realized
            else:
                new_qty = existing.quantity - request.quantity
                realized = (fill_price - existing.avg_price) * request.quantity
                self._capital += realized
                new_avg = existing.avg_price if new_qty != 0 else 0

            if new_qty == 0:
                del self._positions[symbol]
            else:
                self._positions[symbol] = existing.model_copy(update={"quantity": new_qty, "avg_price": round(new_avg, 2)})
        else:
            qty = request.quantity if request.side == Side.BUY else -request.quantity
            self._positions[symbol] = Position(
                instrument=request.instrument,
                quantity=qty,
                avg_price=round(fill_price, 2),
            )

        order = Order(
            order_id=order_id,
            request=request,
            status=OrderStatus.COMPLETE,
            filled_qty=request.quantity,
            avg_price=round(fill_price, 2),
            broker="paper",
        )
        self._orders.append(order)
        log.info("Paper fill: %s %s %d @ %.2f", request.side.value, symbol, request.quantity, fill_price)
        return order

    def cancel_order(self, order_id: str) -> bool:
        for order in self._orders:
            if order.order_id == order_id and order.status == OrderStatus.PENDING:
                order.status = OrderStatus.CANCELLED
                return True
        return False

    def orders(self) -> list[Order]:
        return list(self._orders)
