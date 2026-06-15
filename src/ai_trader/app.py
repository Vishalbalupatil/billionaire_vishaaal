"""FastAPI application entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ai_trader.api.routes import router, set_dependencies
from ai_trader.api.websocket import ws_router
from ai_trader.broker.paper import PaperBroker
from ai_trader.config import TradingMode, get_settings
from ai_trader.risk.manager import RiskManager
from ai_trader.storage.database import Database
from ai_trader.strategy.engine import StrategyEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    log.info("Starting AI Trader in %s mode", settings.trading_mode.value)

    # Initialize broker
    if settings.trading_mode == TradingMode.LIVE:
        from ai_trader.broker.zerodha import ZerodhaClient
        broker = ZerodhaClient()
    else:
        broker = PaperBroker(initial_capital=settings.max_capital)

    # Initialize components
    risk_manager = RiskManager()
    engine = StrategyEngine(broker=broker, risk_manager=risk_manager)
    db = Database()
    db.connect()

    # Wire up API dependencies
    set_dependencies(engine=engine, risk=risk_manager, broker=broker, db=db)

    log.info("AI Trader ready — mode=%s capital=₹%.0f", settings.trading_mode.value, settings.max_capital)

    yield

    db.close()
    log.info("AI Trader shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Trader — Nifty 50 Options",
        description="AI-powered trading platform for Indian markets",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    app.include_router(ws_router)

    # Serve dashboard if built
    dashboard_dist = Path("ui/dashboard/dist")
    if dashboard_dist.exists():
        app.mount("/", StaticFiles(directory=str(dashboard_dist), html=True), name="dashboard")

    return app


app = create_app()
