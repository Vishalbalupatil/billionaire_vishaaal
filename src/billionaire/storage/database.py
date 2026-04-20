"""Thin SQLite-backed storage layer. Synchronous, threadsafe-enough for the
background event loops in this project. Swappable for Postgres via SQLAlchemy
if needed."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

from billionaire.config import get_settings
from billionaire.models import Candle, Order, Signal, Trade

log = logging.getLogger(__name__)


def _sqlite_path_from_url(url: str) -> Path:
    # sqlite:///./data/billionaire.db -> ./data/billionaire.db
    if url.startswith("sqlite:///"):
        return Path(url.replace("sqlite:///", "", 1))
    if url.startswith("sqlite://"):
        return Path(url.replace("sqlite://", "", 1))
    return Path(url)


class Database:
    """Simple SQLite wrapper. For Postgres, replace with SQLAlchemy engine."""

    def __init__(self, url: str | None = None) -> None:
        settings = get_settings()
        self.url = url or settings.database_url
        self.path = _sqlite_path_from_url(self.url)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        try:
            schema_text = resources.files("billionaire.storage").joinpath("schema.sql").read_text(
                encoding="utf-8"
            )
        except (FileNotFoundError, ModuleNotFoundError):
            schema_text = Path(__file__).parent.joinpath("schema.sql").read_text(encoding="utf-8")
        with self._lock:
            self._conn.executescript(schema_text)

    @contextmanager
    def cursor(self) -> Iterator[sqlite3.Cursor]:
        with self._lock:
            cur = self._conn.cursor()
            try:
                yield cur
            finally:
                cur.close()

    # ---- inserts ----
    def save_candle(self, candle: Candle) -> None:
        with self.cursor() as cur:
            cur.execute(
                """INSERT OR REPLACE INTO candles
                   (instrument_token, timeframe, open, high, low, close, volume, oi, ts)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    candle.instrument_token,
                    candle.timeframe,
                    candle.open,
                    candle.high,
                    candle.low,
                    candle.close,
                    candle.volume,
                    candle.oi,
                    candle.ts.isoformat(),
                ),
            )

    def save_signal(self, signal: Signal) -> None:
        with self.cursor() as cur:
            cur.execute(
                """INSERT INTO signals
                   (strategy, symbol, setup, direction, entry, stop_loss, target1, target2,
                    confidence, regime, reasons, invalidation, qty, rr, payload, ts)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    signal.strategy,
                    signal.instrument.tradingsymbol,
                    signal.setup.value,
                    signal.direction.value,
                    signal.entry,
                    signal.stop_loss,
                    signal.target1,
                    signal.target2,
                    signal.confidence,
                    signal.regime.value,
                    json.dumps(signal.reasons),
                    json.dumps(signal.invalidation),
                    signal.suggested_qty,
                    signal.expected_rr,
                    signal.model_dump_json(),
                    signal.ts.isoformat(),
                ),
            )

    def save_order(self, order: Order) -> None:
        r = order.request
        with self.cursor() as cur:
            cur.execute(
                """INSERT OR REPLACE INTO orders
                   (order_id, symbol, side, qty, order_type, product, limit_price, trigger_price,
                    status, filled_qty, avg_price, broker, tag, message, ts)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    order.order_id,
                    r.instrument.tradingsymbol,
                    r.side.value,
                    r.quantity,
                    r.order_type.value,
                    r.product.value,
                    r.limit_price,
                    r.trigger_price,
                    order.status.value,
                    order.filled_qty,
                    order.avg_price,
                    order.broker,
                    r.tag,
                    order.message,
                    order.ts.isoformat(),
                ),
            )

    def save_trade(self, trade: Trade) -> None:
        with self.cursor() as cur:
            cur.execute(
                """INSERT INTO trades
                   (trade_id, order_id, symbol, side, qty, price, pnl, ts)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trade.trade_id,
                    trade.order_id,
                    trade.instrument.tradingsymbol,
                    trade.side.value,
                    trade.quantity,
                    trade.price,
                    trade.pnl,
                    trade.ts.isoformat(),
                ),
            )

    def audit(self, event: str, actor: str = "system", payload: dict[str, Any] | None = None) -> None:
        with self.cursor() as cur:
            cur.execute(
                "INSERT INTO audit_log (event, actor, payload, ts) VALUES (?, ?, ?, ?)",
                (event, actor, json.dumps(payload or {}, default=str), datetime.utcnow().isoformat()),
            )

    # ---- reads ----
    def recent_signals(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.cursor() as cur:
            cur.execute("SELECT * FROM signals ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def recent_orders(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.cursor() as cur:
            cur.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def recent_trades(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.cursor() as cur:
            cur.execute("SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.Error as e:
                log.warning("db close error: %s", e)


@lru_cache(maxsize=1)
def get_database() -> Database:
    return Database()
