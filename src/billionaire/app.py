"""FastAPI entrypoint. Boots the runtime, registers routes, and exposes a
WebSocket endpoint for the dashboard to stream live status updates."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from billionaire import __version__
from billionaire.api.routes import build_router
from billionaire.config import get_settings
from billionaire.logging_setup import setup_logging
from billionaire.marketdata.history_seeder import seed_candle_history
from billionaire.marketdata.watchlist import load_watchlist_symbols, resolve_tokens
from billionaire.runtime import get_runtime

setup_logging()
log = logging.getLogger(__name__)

app = FastAPI(
    title="Billionaire Vishaaal",
    version=__version__,
    description=(
        "AI-assisted trading platform for Indian markets. "
        "DECISION-SUPPORT TOOL — NOT FINANCIAL ADVICE. Defaults to analysis mode."
    ),
)

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_settings.dashboard_origin, "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=JSONResponse)
def root() -> dict:
    return {
        "name": "billionaire-vishaaal",
        "version": __version__,
        "mode": _settings.app_mode.value,
        "warning": "Decision-support tool. No profits are guaranteed. Paper-trade first.",
    }


app.include_router(build_router(), prefix="/api")


@app.on_event("startup")
async def _startup() -> None:
    r = get_runtime()
    log.info("Startup: mode=%s, live=%s", r.settings.app_mode.value, r.settings.live_trading_enabled)
    if r.ws:
        started = r.ws.connect()
        log.info("WebSocket start: %s", started)

    # Without this, KiteTicker connects but never receives ticks because no
    # instrument tokens have been subscribed.
    if r.instruments and r.ws:
        await asyncio.to_thread(_load_and_subscribe_watchlist, r)


def _load_and_subscribe_watchlist(r) -> None:  # type: ignore[no-untyped-def]
    try:
        r.instruments.load()
    except Exception as e:  # pragma: no cover — network-dependent
        log.warning("Instrument master load failed: %s", e)
        return
    log.info("Instrument master: %d instruments cached", len(r.instruments))

    cfg_path = Path("config/config.yaml")
    symbols = load_watchlist_symbols(cfg_path)
    tokens, missing = resolve_tokens(symbols, r.instruments)
    log.info(
        "Watchlist: %d symbols configured -> %d tokens resolved (%d missing)",
        len(symbols), len(tokens), len(missing),
    )
    if missing:
        log.info("Unresolved watchlist symbols: %s", missing)
    if tokens:
        r.ws.set_tokens(tokens)
        log.info("Subscribed KiteTicker to %d tokens", len(tokens))

    if r.settings.seed_history_on_boot and r.live_broker is not None and tokens:
        _seed_forecast_history(r, tokens)


def _seed_forecast_history(r, tokens: list[int]) -> None:  # type: ignore[no-untyped-def]
    """Bootstrap the candle ring buffer from Kite REST so /api/forecast can
    return `source=live` immediately instead of waiting ~20 min for ticks."""
    if not hasattr(r.live_broker, "historical_data"):
        log.info("Live broker lacks historical_data(); skipping history seed.")
        return
    try:
        result = seed_candle_history(
            r.live_broker,
            r.candle_builder,
            tokens,
            lookback_minutes=r.settings.seed_history_lookback_minutes,
        )
    except Exception as e:  # pragma: no cover — defensive
        log.warning("History seed failed: %s", e)
        return
    log.info(
        "History seed: %d/%d tokens populated, %d candles loaded (errors=%d)",
        result.tokens_seeded, result.tokens_requested,
        result.candles_total, len(result.errors),
    )
    if result.errors:
        log.info("History seed errors: %s", result.errors)


@app.websocket("/ws")
async def ws_dashboard(ws: WebSocket) -> None:
    """Stream runtime status snapshots to the dashboard every second."""
    await ws.accept()
    try:
        while True:
            r = get_runtime()
            snap = r.portfolio.snapshot()
            payload = {
                "ts": asyncio.get_event_loop().time(),
                "mode": r.settings.app_mode.value,
                "risk": r.risk.status(),
                "portfolio": {
                    "unrealized_pnl": snap.unrealized_pnl,
                    "realized_pnl": snap.realized_pnl,
                    "gross_exposure": snap.gross_exposure,
                    "net_exposure": snap.net_exposure,
                    "positions": [p.model_dump() for p in snap.positions],
                },
                "ws": r.ws.health() if r.ws else {"connected": False, "tokens_subscribed": 0},
            }
            await ws.send_text(json.dumps(payload, default=str))
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return
    except Exception as e:  # pragma: no cover
        log.warning("dashboard ws error: %s", e)
