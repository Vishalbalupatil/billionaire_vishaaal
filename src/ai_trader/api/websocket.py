"""WebSocket endpoint for real-time data streaming to the dashboard."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)
ws_router = APIRouter()

# Connected clients
_clients: list[WebSocket] = []


@ws_router.websocket("/ws/live")
async def live_feed(ws: WebSocket) -> None:
    """WebSocket endpoint for live market data, signals, and P&L updates."""
    await ws.accept()
    _clients.append(ws)
    log.info("WebSocket client connected (%d total)", len(_clients))
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        _clients.remove(ws)
        log.info("WebSocket client disconnected (%d remaining)", len(_clients))
    except Exception as exc:
        log.error("WebSocket error: %s", exc)
        if ws in _clients:
            _clients.remove(ws)


async def broadcast(event_type: str, data: dict[str, Any]) -> None:
    """Broadcast an event to all connected WebSocket clients."""
    if not _clients:
        return
    message = json.dumps({"type": event_type, "data": data})
    disconnected: list[WebSocket] = []
    for client in _clients:
        try:
            await client.send_text(message)
        except Exception:
            disconnected.append(client)
    for client in disconnected:
        _clients.remove(client)
