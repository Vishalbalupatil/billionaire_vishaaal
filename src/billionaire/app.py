"""FastAPI entrypoint. Boots the runtime, registers routes, and exposes a
WebSocket endpoint for the dashboard to stream live status updates."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from billionaire import __version__
from billionaire.api.routes import build_router
from billionaire.config import get_settings
from billionaire.logging_setup import setup_logging
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
