"""Real-time market data feed via Kite WebSocket.

Manages the WebSocket connection, dispatches ticks to the candle builder,
and notifies subscribers.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from ai_trader.config import get_settings
from ai_trader.market_data.candles import CandleBuilder
from ai_trader.models.domain import Candle, Tick

log = logging.getLogger(__name__)

TickCallback = Callable[[Tick], None]
CandleCallback = Callable[[Candle], None]


class MarketFeed:
    """Wraps KiteTicker for live tick feed with candle building."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._candle_builder = CandleBuilder()
        self._tick_subscribers: list[TickCallback] = []
        self._candle_subscribers: list[CandleCallback] = []
        self._tokens: list[int] = []
        self._running = False
        self._ws: Any = None

    @property
    def candle_builder(self) -> CandleBuilder:
        return self._candle_builder

    def subscribe_ticks(self, callback: TickCallback) -> None:
        self._tick_subscribers.append(callback)

    def subscribe_candles(self, callback: CandleCallback) -> None:
        self._candle_subscribers.append(callback)

    def set_tokens(self, tokens: list[int]) -> None:
        self._tokens = tokens
        if self._ws and self._running:
            try:
                self._ws.subscribe(tokens)
                self._ws.set_mode(self._ws.MODE_FULL, tokens)
            except Exception as exc:
                log.warning("Failed to subscribe tokens: %s", exc)

    def start(self) -> None:
        """Start the WebSocket feed (blocking — run in a thread)."""
        if not self._settings.kite_api_key or not self._settings.kite_access_token:
            log.warning("Kite credentials not configured — feed not started")
            return

        try:
            from kiteconnect import KiteTicker
        except ImportError:
            log.error("kiteconnect not installed")
            return

        self._ws = KiteTicker(self._settings.kite_api_key, self._settings.kite_access_token)
        self._ws.on_ticks = self._on_ticks
        self._ws.on_connect = self._on_connect
        self._ws.on_close = self._on_close
        self._ws.on_error = self._on_error

        log.info("Starting Kite WebSocket feed...")
        self._running = True
        self._ws.connect(threaded=False)

    def stop(self) -> None:
        import contextlib

        self._running = False
        if self._ws:
            with contextlib.suppress(Exception):
                self._ws.close()

    def _on_connect(self, ws: Any, response: Any) -> None:
        log.info("WebSocket connected")
        if self._tokens:
            ws.subscribe(self._tokens)
            ws.set_mode(ws.MODE_FULL, self._tokens)
            log.info("Subscribed to %d tokens", len(self._tokens))

    def _on_ticks(self, ws: Any, ticks: list[dict[str, Any]]) -> None:
        for raw in ticks:
            tick = Tick(
                instrument_token=int(raw.get("instrument_token", 0)),
                ltp=float(raw.get("last_price", 0)),
                volume=int(raw.get("volume_traded", 0)),
                oi=int(raw.get("oi", 0)),
                bid=float(raw.get("depth", {}).get("buy", [{}])[0].get("price", 0)) if raw.get("depth") else 0,
                ask=float(raw.get("depth", {}).get("sell", [{}])[0].get("price", 0)) if raw.get("depth") else 0,
            )

            for cb in self._tick_subscribers:
                try:
                    cb(tick)
                except Exception as exc:
                    log.error("Tick subscriber error: %s", exc)

            completed = self._candle_builder.on_tick(tick)
            for candle in completed:
                for cb in self._candle_subscribers:
                    try:
                        cb(candle)
                    except Exception as exc:
                        log.error("Candle subscriber error: %s", exc)

    def _on_close(self, ws: Any, code: int, reason: str) -> None:
        log.warning("WebSocket closed: code=%s reason=%s", code, reason)

    def _on_error(self, ws: Any, code: int, reason: str) -> None:
        log.error("WebSocket error: code=%s reason=%s", code, reason)
