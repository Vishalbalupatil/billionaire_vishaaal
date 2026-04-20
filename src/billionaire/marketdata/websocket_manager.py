"""Zerodha KiteTicker WebSocket manager with graceful reconnection.

Wraps the official ``KiteTicker`` class (when available), translates raw tick
payloads into typed :class:`Tick` objects, and fans them out to subscribers
(usually a :class:`CandleBuilder` and optional raw storage).

If ``kiteconnect`` is not importable or the session has no access token, this
manager logs a warning and stays idle — the rest of the app (analysis, paper
trading simulations, backtesting) continues to work.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

from billionaire.config import get_settings
from billionaire.models import Tick

log = logging.getLogger(__name__)

TickCallback = Callable[[Tick], None]


class WebSocketManager:
    def __init__(self, on_tick: TickCallback | None = None) -> None:
        self._settings = get_settings()
        self._subscribers: list[TickCallback] = []
        if on_tick:
            self._subscribers.append(on_tick)
        self._tokens: set[int] = set()
        self._mode_full: set[int] = set()
        self._ticker: Any | None = None
        self._connected = False
        self._reconnect_attempts = 0
        self._lock = threading.RLock()

    # ---- subscribers ----
    def subscribe(self, cb: TickCallback) -> None:
        self._subscribers.append(cb)

    def _fanout(self, tick: Tick) -> None:
        for cb in list(self._subscribers):
            try:
                cb(tick)
            except (RuntimeError, ValueError) as e:  # pragma: no cover
                log.exception("tick subscriber error: %s", e)

    # ---- tokens ----
    def set_tokens(self, tokens: list[int], full_depth: list[int] | None = None) -> None:
        with self._lock:
            self._tokens = set(tokens)
            self._mode_full = set(full_depth or [])
        if self._ticker and self._connected:
            self._apply_subscriptions()

    def _apply_subscriptions(self) -> None:
        t = self._ticker
        if not t:
            return
        try:
            tokens = list(self._tokens)
            if tokens:
                t.subscribe(tokens)
                quote_tokens = [tok for tok in tokens if tok not in self._mode_full]
                if quote_tokens:
                    t.set_mode(t.MODE_QUOTE, quote_tokens)
                if self._mode_full:
                    t.set_mode(t.MODE_FULL, list(self._mode_full))
        except (RuntimeError, ValueError) as e:  # pragma: no cover
            log.warning("apply_subscriptions failed: %s", e)

    # ---- lifecycle ----
    def connect(self) -> bool:
        """Start the WebSocket loop in a background thread. Returns True if
        the ticker was actually constructed, False if we stayed idle (no
        credentials or SDK missing)."""
        s = self._settings
        if not (s.kite_api_key and s.kite_access_token):
            log.warning("WebSocketManager idle — KITE_API_KEY/KITE_ACCESS_TOKEN not set.")
            return False
        try:
            from kiteconnect import KiteTicker
        except ImportError:  # pragma: no cover
            log.warning("kiteconnect not installed; WebSocketManager idle.")
            return False

        ticker = KiteTicker(s.kite_api_key, s.kite_access_token)
        self._ticker = ticker
        ticker.on_ticks = self._on_ticks
        ticker.on_connect = self._on_connect
        ticker.on_close = self._on_close
        ticker.on_error = self._on_error
        ticker.on_reconnect = self._on_reconnect
        ticker.on_order_update = self._on_order_update

        def _runner() -> None:
            while True:
                try:
                    ticker.connect(threaded=False)
                except (RuntimeError, OSError) as e:
                    log.exception("ticker crashed, retrying: %s", e)
                    self._connected = False
                # backoff up to 60s
                self._reconnect_attempts += 1
                time.sleep(min(60, 2 ** min(self._reconnect_attempts, 6)))

        threading.Thread(target=_runner, name="kite-ws", daemon=True).start()
        return True

    # ---- ticker callbacks ----
    def _on_connect(self, ws: Any, response: Any) -> None:
        log.info("KiteTicker connected")
        self._connected = True
        self._reconnect_attempts = 0
        self._apply_subscriptions()

    def _on_close(self, ws: Any, code: int, reason: str) -> None:
        log.warning("KiteTicker closed: %s %s", code, reason)
        self._connected = False

    def _on_error(self, ws: Any, code: int, reason: str) -> None:
        log.error("KiteTicker error: %s %s", code, reason)

    def _on_reconnect(self, ws: Any, attempts: int) -> None:
        log.info("KiteTicker reconnecting, attempt=%s", attempts)

    def _on_order_update(self, ws: Any, data: dict[str, Any]) -> None:
        log.info("Order update: %s", data.get("status"))

    def _on_ticks(self, ws: Any, ticks: list[dict[str, Any]]) -> None:
        for t in ticks:
            try:
                tick = Tick(
                    instrument_token=int(t["instrument_token"]),
                    ltp=float(t.get("last_price") or 0.0),
                    volume=int(t.get("volume_traded") or t.get("volume") or 0),
                    oi=int(t.get("oi") or 0),
                    bid=float((t.get("depth", {}).get("buy") or [{}])[0].get("price") or 0.0),
                    ask=float((t.get("depth", {}).get("sell") or [{}])[0].get("price") or 0.0),
                    ts=datetime.utcnow(),
                )
            except (KeyError, ValueError, TypeError) as e:
                log.debug("malformed tick: %s", e)
                continue
            self._fanout(tick)

    # ---- status ----
    @property
    def connected(self) -> bool:
        return self._connected

    def health(self) -> dict[str, Any]:
        return {
            "connected": self._connected,
            "tokens_subscribed": len(self._tokens),
            "reconnect_attempts": self._reconnect_attempts,
        }
