"""SQLite database for persisting signals, orders, trades, and P&L."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from ai_trader.models.domain import Signal

log = logging.getLogger(__name__)

DB_PATH = Path("data/ai_trader.db")
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class Database:
    def __init__(self, db_path: Path | None = None) -> None:
        self._path = db_path or DB_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        log.info("Database connected: %s", self._path)

    def _init_schema(self) -> None:
        if not self._conn:
            return
        if SCHEMA_PATH.exists():
            schema = SCHEMA_PATH.read_text()
            self._conn.executescript(schema)
            self._conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()

    def save_signal(self, signal: Signal) -> None:
        if not self._conn:
            return
        self._conn.execute(
            """INSERT INTO signals (ts, instrument, direction, entry, stop_loss, target1, target2,
               confidence, regime, strategy_name, reasons) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                signal.ts.isoformat(),
                signal.instrument.tradingsymbol,
                signal.direction.value,
                signal.entry,
                signal.stop_loss,
                signal.target1,
                signal.target2,
                signal.confidence,
                signal.regime.value,
                signal.strategy_name,
                json.dumps(signal.reasons),
            ),
        )
        self._conn.commit()

    def save_daily_pnl(self, date: str, realized: float, unrealized: float, total: int, wins: int, losses: int) -> None:
        if not self._conn:
            return
        self._conn.execute(
            """INSERT OR REPLACE INTO daily_pnl (date, realized_pnl, unrealized_pnl, total_trades,
               winning_trades, losing_trades) VALUES (?, ?, ?, ?, ?, ?)""",
            (date, realized, unrealized, total, wins, losses),
        )
        self._conn.commit()

    def get_recent_signals(self, limit: int = 50) -> list[dict]:
        if not self._conn:
            return []
        rows = self._conn.execute(
            "SELECT * FROM signals ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_daily_pnl(self, days: int = 30) -> list[dict]:
        if not self._conn:
            return []
        rows = self._conn.execute(
            "SELECT * FROM daily_pnl ORDER BY date DESC LIMIT ?", (days,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_trade_stats(self) -> dict:
        if not self._conn:
            return {}
        row = self._conn.execute(
            """SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing,
                SUM(pnl) as total_pnl,
                AVG(pnl) as avg_pnl,
                MAX(pnl) as best_trade,
                MIN(pnl) as worst_trade
            FROM trades"""
        ).fetchone()
        return dict(row) if row else {}
