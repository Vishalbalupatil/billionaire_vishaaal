"""Abstract broker interface. Both Zerodha and Paper brokers implement this."""

from __future__ import annotations

import abc
from typing import Any

from ai_trader.models.domain import Instrument, Order, OrderRequest, Position


class BrokerClient(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def login_url(self) -> str: ...

    @abc.abstractmethod
    def generate_session(self, request_token: str) -> str: ...

    @abc.abstractmethod
    def instruments(self, exchange: str | None = None) -> list[Instrument]: ...

    @abc.abstractmethod
    def historical_data(
        self,
        instrument_token: int,
        from_dt: Any,
        to_dt: Any,
        interval: str = "minute",
    ) -> list[dict[str, Any]]: ...

    @abc.abstractmethod
    def quote(self, symbols: list[str]) -> dict[str, dict[str, Any]]: ...

    @abc.abstractmethod
    def ltp(self, symbols: list[str]) -> dict[str, float]: ...

    @abc.abstractmethod
    def margins(self) -> dict[str, Any]: ...

    @abc.abstractmethod
    def positions(self) -> list[Position]: ...

    @abc.abstractmethod
    def place_order(self, request: OrderRequest) -> Order: ...

    @abc.abstractmethod
    def cancel_order(self, order_id: str) -> bool: ...

    @abc.abstractmethod
    def orders(self) -> list[Order]: ...

    def set_price(self, tradingsymbol: str, price: float) -> None:  # noqa: B027
        """Set simulated price (only used by paper broker)."""
