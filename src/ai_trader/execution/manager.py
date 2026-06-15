"""Order management — tracks orders, manages fill status, and handles retries."""

from __future__ import annotations

import logging

from ai_trader.broker.base import BrokerClient
from ai_trader.models.domain import Order, OrderRequest, OrderStatus

log = logging.getLogger(__name__)


class OrderManager:
    """Manages order lifecycle from placement to fill/rejection."""

    def __init__(self, broker: BrokerClient) -> None:
        self._broker = broker
        self._orders: list[Order] = []
        self._pending: dict[str, Order] = {}

    @property
    def orders(self) -> list[Order]:
        return list(self._orders)

    @property
    def pending_orders(self) -> list[Order]:
        return [o for o in self._orders if o.status in (OrderStatus.PENDING, OrderStatus.OPEN)]

    @property
    def filled_orders(self) -> list[Order]:
        return [o for o in self._orders if o.status == OrderStatus.COMPLETE]

    def place(self, request: OrderRequest) -> Order:
        order = self._broker.place_order(request)
        self._orders.append(order)
        if order.status in (OrderStatus.PENDING, OrderStatus.OPEN):
            self._pending[order.order_id] = order
        log.info(
            "Order %s: %s %s %d → %s",
            order.order_id, request.side.value, request.instrument.tradingsymbol,
            request.quantity, order.status.value,
        )
        return order

    def cancel(self, order_id: str) -> bool:
        result = self._broker.cancel_order(order_id)
        if result:
            self._pending.pop(order_id, None)
            for o in self._orders:
                if o.order_id == order_id:
                    o.status = OrderStatus.CANCELLED
        return result

    def cancel_all(self) -> int:
        """Cancel all pending orders."""
        cancelled = 0
        for order_id in list(self._pending.keys()):
            if self.cancel(order_id):
                cancelled += 1
        return cancelled

    def sync_from_broker(self) -> None:
        """Sync order status from broker."""
        try:
            broker_orders = self._broker.orders()
            broker_map = {o.order_id: o for o in broker_orders}
            for order in self._orders:
                if order.order_id in broker_map:
                    bo = broker_map[order.order_id]
                    order.status = bo.status
                    order.filled_qty = bo.filled_qty
                    order.avg_price = bo.avg_price
            self._pending = {
                oid: o for oid, o in self._pending.items()
                if o.status in (OrderStatus.PENDING, OrderStatus.OPEN)
            }
        except Exception as exc:
            log.error("Failed to sync orders: %s", exc)

    def daily_summary(self) -> dict:
        """Return daily order summary."""
        total = len(self._orders)
        filled = len(self.filled_orders)
        pending = len(self.pending_orders)
        rejected = len([o for o in self._orders if o.status == OrderStatus.REJECTED])
        return {
            "total": total,
            "filled": filled,
            "pending": pending,
            "rejected": rejected,
        }
