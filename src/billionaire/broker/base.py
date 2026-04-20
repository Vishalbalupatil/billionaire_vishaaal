"""Abstract broker interface. Any broker (Zerodha, paper, mock) must implement
this so the rest of the platform stays broker-agnostic."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from billionaire.models import Instrument, Order, OrderRequest, Position


class BrokerClient(ABC):
    name: str = "base"

    @abstractmethod
    def instruments(self, exchange: str | None = None) -> list[Instrument]: ...

    @abstractmethod
    def quote(self, symbols: list[str]) -> dict[str, dict[str, Any]]: ...

    @abstractmethod
    def ltp(self, symbols: list[str]) -> dict[str, float]: ...

    @abstractmethod
    def margins(self) -> dict[str, Any]: ...

    @abstractmethod
    def positions(self) -> list[Position]: ...

    @abstractmethod
    def holdings(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def place_order(self, req: OrderRequest) -> Order: ...

    @abstractmethod
    def modify_order(self, order_id: str, **changes: Any) -> Order: ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> Order: ...

    @abstractmethod
    def order_history(self, order_id: str) -> list[dict[str, Any]]: ...

    @abstractmethod
    def trades(self) -> list[dict[str, Any]]: ...
