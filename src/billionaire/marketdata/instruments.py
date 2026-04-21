"""Instrument master data cache. Loads and refreshes from the broker."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterable

from billionaire.broker.base import BrokerClient
from billionaire.models import Instrument

log = logging.getLogger(__name__)


class InstrumentMaster:
    """In-memory instrument cache with symbol/token lookup."""

    def __init__(self, broker: BrokerClient, refresh_seconds: int = 6 * 3600) -> None:
        self._broker = broker
        self._refresh_seconds = refresh_seconds
        self._by_token: dict[int, Instrument] = {}
        self._by_symbol: dict[str, Instrument] = {}
        self._last_loaded: float = 0.0
        self._lock = threading.RLock()

    def load(self, exchanges: Iterable[str] = ("NSE", "NFO", "BSE", "BFO")) -> None:
        all_items: list[Instrument] = []
        for exch in exchanges:
            try:
                items = self._broker.instruments(exch)
                all_items.extend(items)
                log.info("Loaded %d instruments from %s", len(items), exch)
            except (RuntimeError, ValueError, KeyError) as e:
                log.warning("Failed to load %s instruments: %s", exch, e)
        with self._lock:
            self._by_token = {i.instrument_token: i for i in all_items}
            self._by_symbol = {f"{i.exchange.value}:{i.tradingsymbol}": i for i in all_items}
            self._last_loaded = time.time()

    def maybe_refresh(self) -> None:
        if time.time() - self._last_loaded >= self._refresh_seconds:
            self.load()

    def by_token(self, token: int) -> Instrument | None:
        with self._lock:
            return self._by_token.get(token)

    def by_symbol(self, symbol: str) -> Instrument | None:
        with self._lock:
            return self._by_symbol.get(symbol)

    def search(self, query: str, segment: str | None = None, limit: int = 25) -> list[Instrument]:
        q = query.upper()
        out: list[Instrument] = []
        with self._lock:
            for inst in self._by_symbol.values():
                if segment and inst.segment.value != segment:
                    continue
                if q in inst.tradingsymbol.upper() or q in (inst.name or "").upper():
                    out.append(inst)
                    if len(out) >= limit:
                        break
        return out

    def __len__(self) -> int:
        with self._lock:
            return len(self._by_token)

    def __iter__(self) -> Iterable[Instrument]:
        """Snapshot iterator over all loaded instruments.

        Returns a list snapshot (not a live view) so callers can iterate
        without holding the lock. Used by the ORB front-month futures
        resolver to scan the full NFO master.
        """
        with self._lock:
            return iter(list(self._by_token.values()))

    def by_underlying(self, underlying: str) -> list[Instrument]:
        """All instruments whose ``name`` matches ``underlying`` (e.g. NIFTY
        futures + options contracts). Case-insensitive; includes every
        segment, so callers must filter further if they only want FUT/OPT."""
        u = underlying.upper()
        with self._lock:
            return [i for i in self._by_token.values() if (i.name or "").upper() == u]
