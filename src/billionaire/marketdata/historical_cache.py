"""SQLite-backed cache of historical OHLCV bars.

Why a cache?

A single Kite historical_data request for 5-minute bars is capped at 100
days. Pulling 2 years of 5m data for NIFTY 50 + NIFTY-FUT + INDIA VIX =
~7-10 HTTP round-trips, each ~300-500 ms. If the backtest re-pulls every
time the user refreshes the dashboard, the UX collapses.

Design:
    * Single sqlite file at ``data/historical_bars.db`` (created on demand).
    * One table keyed on (instrument_token, timeframe, ts). UPSERT semantics
      so re-pulling an overlapping window is idempotent.
    * No indexes beyond the PK — reads are always token+timeframe+range
      scans which the PK covers.
    * Timestamps stored naive (IST local time), matching how the ORB
      strategy reasons about "09:15 IST".

Tests use an in-memory sqlite (``:memory:``) and the same public API.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CachedBar:
    """One OHLCV bar, returned by :meth:`HistoricalCache.get_bars`."""

    instrument_token: int
    timeframe: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    oi: int


_DDL = """
CREATE TABLE IF NOT EXISTS bars (
    instrument_token INTEGER NOT NULL,
    timeframe        TEXT    NOT NULL,
    ts               TEXT    NOT NULL,
    open             REAL    NOT NULL,
    high             REAL    NOT NULL,
    low              REAL    NOT NULL,
    close            REAL    NOT NULL,
    volume           INTEGER NOT NULL,
    oi               INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (instrument_token, timeframe, ts)
);
"""


class HistoricalCache:
    """Durable cache for OHLCV bars.

    Instances hold a single long-lived sqlite connection (sqlite handles
    concurrency at the cursor level; we additionally lock writes with a
    threading.Lock to make parallel upserts from the Kite fetcher safe).

    Pass ``db_path=":memory:"`` for isolated per-test caches.
    """

    def __init__(self, db_path: str | Path = "data/historical_bars.db") -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        # ``check_same_thread=False`` because the fetcher runs in a worker
        # thread but instances live in the FastAPI main thread.
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute(_DDL)
        self._conn.commit()
        self._write_lock = Lock()

    def close(self) -> None:
        self._conn.close()

    # ---- reads ----
    def get_bars(
        self,
        instrument_token: int,
        timeframe: str,
        from_ts: datetime,
        to_ts: datetime,
    ) -> list[CachedBar]:
        """Return bars in [from_ts, to_ts] inclusive, chronological order."""
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                """
                SELECT ts, open, high, low, close, volume, oi
                FROM bars
                WHERE instrument_token = ?
                  AND timeframe        = ?
                  AND ts              >= ?
                  AND ts              <= ?
                ORDER BY ts ASC
                """,
                (
                    instrument_token,
                    timeframe,
                    from_ts.isoformat(),
                    to_ts.isoformat(),
                ),
            )
            rows = cur.fetchall()
        return [
            CachedBar(
                instrument_token=instrument_token,
                timeframe=timeframe,
                ts=datetime.fromisoformat(r[0]),
                open=float(r[1]),
                high=float(r[2]),
                low=float(r[3]),
                close=float(r[4]),
                volume=int(r[5]),
                oi=int(r[6]),
            )
            for r in rows
        ]

    def last_ts(self, instrument_token: int, timeframe: str) -> datetime | None:
        """Return the most recent cached ts for a (token, timeframe),
        or ``None`` when the cache is empty. Used by the fetcher to compute
        the smallest incremental window it must pull."""
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                """
                SELECT MAX(ts) FROM bars
                WHERE instrument_token = ? AND timeframe = ?
                """,
                (instrument_token, timeframe),
            )
            row = cur.fetchone()
        if row is None or row[0] is None:
            return None
        return datetime.fromisoformat(row[0])

    def count(self, instrument_token: int, timeframe: str) -> int:
        """Number of cached bars for a (token, timeframe). Useful for
        status endpoints and tests."""
        with closing(self._conn.cursor()) as cur:
            cur.execute(
                "SELECT COUNT(*) FROM bars WHERE instrument_token = ? AND timeframe = ?",
                (instrument_token, timeframe),
            )
            row = cur.fetchone()
        return int(row[0]) if row else 0

    # ---- writes ----
    def upsert_bars(self, bars: list[CachedBar]) -> int:
        """Insert or overwrite ``bars``. Returns the number of rows processed.

        Overwrite semantics (``INSERT OR REPLACE``) ensure re-pulling an
        already-cached range is idempotent, and that broker-side corrections
        to a stale bar land in the cache on the next refresh.
        """
        if not bars:
            return 0
        rows = [
            (
                b.instrument_token,
                b.timeframe,
                b.ts.isoformat(),
                b.open,
                b.high,
                b.low,
                b.close,
                b.volume,
                b.oi,
            )
            for b in bars
        ]
        with self._write_lock, self._conn:
            self._conn.executemany(
                """
                    INSERT OR REPLACE INTO bars
                        (instrument_token, timeframe, ts,
                         open, high, low, close, volume, oi)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                rows,
            )
        return len(rows)
