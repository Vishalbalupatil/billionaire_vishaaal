"""Position & P&L aggregator across brokers. Provides dashboard-friendly views."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from billionaire.broker.base import BrokerClient
from billionaire.models import Position


@dataclass
class PortfolioSnapshot:
    positions: list[Position]
    unrealized_pnl: float
    realized_pnl: float
    gross_exposure: float
    net_exposure: float
    count_long: int
    count_short: int


class PositionManager:
    def __init__(self, broker: BrokerClient) -> None:
        self._broker = broker
        self._realized: float = 0.0
        self._lock = threading.RLock()

    def mark_realized(self, pnl: float) -> None:
        with self._lock:
            self._realized += pnl

    def snapshot(self) -> PortfolioSnapshot:
        positions = self._broker.positions()
        up = sum(p.unrealized_pnl for p in positions)
        gross = sum(abs(p.quantity * p.ltp) for p in positions)
        net = sum(p.quantity * p.ltp for p in positions)
        longs = sum(1 for p in positions if p.quantity > 0)
        shorts = sum(1 for p in positions if p.quantity < 0)
        return PortfolioSnapshot(
            positions=list(positions),
            unrealized_pnl=round(up, 2),
            realized_pnl=round(self._realized, 2),
            gross_exposure=round(gross, 2),
            net_exposure=round(net, 2),
            count_long=longs,
            count_short=shorts,
        )
