"""Top-level runtime / dependency container.

Responsible for wiring: config -> db -> broker -> marketdata -> strategies ->
risk -> execution -> alerts, and exposing the composed object graph.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from billionaire.alerts.notifier import Alerter
from billionaire.broker.base import BrokerClient
from billionaire.config import AppMode, Settings, get_settings
from billionaire.execution.order_manager import OrderManager
from billionaire.execution.paper_broker import PaperBroker
from billionaire.marketdata.candle_builder import CandleBuilder
from billionaire.marketdata.instruments import InstrumentMaster
from billionaire.marketdata.websocket_manager import WebSocketManager
from billionaire.portfolio.position_manager import PositionManager
from billionaire.risk.risk_manager import RiskManager
from billionaire.storage import Database, get_database
from billionaire.strategy.examples import EXAMPLE_STRATEGIES
from billionaire.strategy.signal_engine import SignalEngine

log = logging.getLogger(__name__)


@dataclass
class Runtime:
    settings: Settings
    db: Database
    alerter: Alerter
    risk: RiskManager
    paper_broker: PaperBroker
    live_broker: BrokerClient | None
    orders: OrderManager
    portfolio: PositionManager
    signal_engine: SignalEngine
    candle_builder: CandleBuilder
    ws: WebSocketManager | None
    instruments: InstrumentMaster | None


_runtime: Runtime | None = None
_lock = threading.RLock()


def _build_live_broker(settings: Settings) -> BrokerClient | None:
    if not (settings.kite_api_key and settings.kite_access_token):
        return None
    try:
        from billionaire.broker.zerodha_client import ZerodhaClient

        return ZerodhaClient()
    except (RuntimeError, ImportError) as e:
        log.warning("Zerodha client unavailable: %s", e)
        return None


def build_runtime() -> Runtime:
    settings = get_settings()
    db = get_database()
    alerter = Alerter.from_settings()
    risk = RiskManager(settings)
    paper = PaperBroker()
    live = _build_live_broker(settings)
    orders = OrderManager(risk=risk, live_broker=live, paper_broker=paper, settings=settings)
    broker_for_portfolio: BrokerClient = (
        live if live and settings.app_mode == AppMode.LIVE else paper
    )
    portfolio = PositionManager(broker_for_portfolio)

    # Strategies
    engine = SignalEngine([cls() for cls in EXAMPLE_STRATEGIES])

    # Candle builder -> paper broker on each tick
    cb = CandleBuilder()

    # Optional websocket (only if creds present)
    ws: WebSocketManager | None = None
    instruments: InstrumentMaster | None = None
    if live is not None:
        ws = WebSocketManager(on_tick=lambda t: (cb.on_tick(t), paper.on_ltp(t.instrument_token, t.ltp)))
        instruments = InstrumentMaster(live)

    return Runtime(
        settings=settings,
        db=db,
        alerter=alerter,
        risk=risk,
        paper_broker=paper,
        live_broker=live,
        orders=orders,
        portfolio=portfolio,
        signal_engine=engine,
        candle_builder=cb,
        ws=ws,
        instruments=instruments,
    )


def get_runtime() -> Runtime:
    global _runtime
    with _lock:
        if _runtime is None:
            _runtime = build_runtime()
        return _runtime
