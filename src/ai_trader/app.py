"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
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
        if settings.live_unlock_phrase != "I_ACCEPT_RISK":
            log.warning(
                "LIVE mode requested but unlock phrase not set — falling back to PAPER. "
                "Set LIVE_UNLOCK_PHRASE=I_ACCEPT_RISK to enable live trading."
            )
            broker = PaperBroker(initial_capital=settings.max_capital)
        else:
            from ai_trader.broker.zerodha import ZerodhaClient
            broker = ZerodhaClient()
    else:
        broker = PaperBroker(initial_capital=settings.max_capital)

    # Initialize components
    risk_manager = RiskManager()
    engine = StrategyEngine(broker=broker, risk_manager=risk_manager)

    from ai_trader.strategy.auto_trader import AutoTrader
    auto_trader = AutoTrader(broker=broker, risk_manager=risk_manager)

    db = Database()
    db.connect()

    # Initialize market feed for live data
    from ai_trader.market_data.feed import MarketFeed
    feed = MarketFeed()

    # Wire up API dependencies
    set_dependencies(engine=engine, risk=risk_manager, broker=broker, db=db, auto_trader=auto_trader)

    log.info("AI Trader ready — mode=%s capital=₹%.0f", settings.trading_mode.value, settings.max_capital)

    # Start background auto-trading loop with market feed
    loop_task = asyncio.create_task(_auto_trade_loop(auto_trader, broker, feed))

    # Start WebSocket feed in a thread if live with access token
    feed_thread = None
    if settings.trading_mode == TradingMode.LIVE and settings.kite_access_token:
        import threading
        feed_thread = threading.Thread(target=_start_feed, args=(feed, broker), daemon=True)
        feed_thread.start()

    yield

    loop_task.cancel()
    feed.stop()
    db.close()
    log.info("AI Trader shutdown")


def _start_feed(feed: object, broker: object) -> None:
    """Start the WebSocket feed and subscribe to Nifty 50 tokens."""
    try:
        # Get Nifty 50 instrument tokens
        instruments = broker.instruments("NSE")  # type: ignore[attr-defined]
        nifty_tokens = [i.instrument_token for i in instruments[:50] if i.instrument_token]
        if nifty_tokens:
            feed.set_tokens(nifty_tokens)  # type: ignore[attr-defined]
            log.info("Subscribing to %d instrument tokens", len(nifty_tokens))
        feed.start()  # type: ignore[attr-defined]
    except Exception:
        log.exception("Failed to start market feed")


async def _auto_trade_loop(auto_trader: object, broker: object, feed: object) -> None:
    """Background loop that calls evaluate_and_trade every 60 seconds."""
    import pandas as pd

    from ai_trader.execution.scheduler import is_market_open

    log.info("Auto-trading background loop started")
    while True:
        try:
            if is_market_open():
                market_data: dict[str, pd.DataFrame] = {}

                # Try to build DataFrames from live candle data
                try:
                    candle_builder = feed.candle_builder  # type: ignore[attr-defined]
                    for (token, tf), buf in candle_builder._completed.items():
                        if tf != "5m" or not buf:
                            continue
                        candles = list(buf)
                        if len(candles) < 5:
                            continue
                        # Find tradingsymbol for this token
                        symbol = _token_symbol_map.get(token)
                        if symbol and symbol not in market_data:
                            market_data[symbol] = pd.DataFrame([{
                                "open": c.open, "high": c.high, "low": c.low,
                                "close": c.close, "volume": c.volume,
                            } for c in candles])
                except Exception:
                    pass  # No live data yet — scanner runs with empty dict

                # Also try historical data for live broker
                if not market_data and hasattr(broker, "_kite"):
                    try:
                        market_data = _fetch_historical_data(broker)  # type: ignore[arg-type]
                    except Exception:
                        log.debug("Historical data fetch failed, using empty market data")

                auto_trader.evaluate_and_trade(market_data)  # type: ignore[attr-defined]
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            log.info("Auto-trading loop stopped")
            break
        except Exception:
            log.exception("Error in auto-trading loop")
            await asyncio.sleep(60)


# Map instrument_token → tradingsymbol (populated on first historical fetch)
_token_symbol_map: dict[int, str] = {}

# Top Nifty 50 symbols for scanning
_NIFTY50_SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
    "LT", "AXISBANK", "BAJFINANCE", "ASIANPAINT", "MARUTI",
    "HCLTECH", "TITAN", "SUNPHARMA", "TATAMOTORS", "WIPRO",
    "ULTRACEMCO", "NESTLEIND", "POWERGRID", "NTPC", "TECHM",
    "TATASTEEL", "M&M", "ONGC", "JSWSTEEL", "BAJAJFINSV",
    "ADANIENT", "ADANIPORTS", "DIVISLAB", "DRREDDY", "CIPLA",
    "EICHERMOT", "GRASIM", "HEROMOTOCO", "HINDALCO", "INDUSINDBK",
    "COALINDIA", "BPCL", "BRITANNIA", "SBILIFE", "HDFCLIFE",
    "APOLLOHOSP", "TATACONSUM", "BAJAJ-AUTO", "LTIM", "SHRIRAMFIN",
]


def _fetch_historical_data(broker: object) -> dict:
    """Fetch recent 5m candle data from Kite historical API for Nifty 50."""
    from datetime import datetime, timedelta

    import pandas as pd

    market_data: dict[str, pd.DataFrame] = {}
    try:
        instruments = broker.instruments("NSE")  # type: ignore[attr-defined]
        symbol_map = {i.tradingsymbol: i for i in instruments}

        now = datetime.now()
        from_dt = now - timedelta(days=5)

        for sym in _NIFTY50_SYMBOLS[:20]:  # Limit to top 20 to avoid rate limits
            inst = symbol_map.get(sym)
            if not inst:
                continue
            _token_symbol_map[inst.instrument_token] = sym
            try:
                data = broker.historical_data(  # type: ignore[attr-defined]
                    inst.instrument_token, from_dt, now, "5minute"
                )
                if data:
                    df = pd.DataFrame(data)
                    if not df.empty and "close" in df.columns:
                        market_data[sym] = df
            except Exception:
                continue
    except Exception:
        log.debug("Failed to fetch historical data")
    return market_data


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

    # Kite callback route — Zerodha redirects here after login
    @app.get("/kite/callback")
    def kite_callback(request_token: str | None = None, status: str | None = None) -> RedirectResponse:
        from ai_trader.api.routes import _broker
        if request_token and _broker and status == "success":
            try:
                _broker.generate_session(request_token)  # type: ignore[attr-defined]
                log.info("Session created via /kite/callback")
            except Exception as exc:
                log.error("Kite callback session error: %s", exc)
        # Redirect to dashboard
        return RedirectResponse(url="/")

    # Serve dashboard if built
    dashboard_dist = Path("ui/dashboard/dist")
    if dashboard_dist.exists():
        app.mount("/", StaticFiles(directory=str(dashboard_dist), html=True), name="dashboard")

    return app


app = create_app()
