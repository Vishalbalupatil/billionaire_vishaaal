"""Instrument master — caches and resolves Nifty 50 options instruments."""

from __future__ import annotations

import logging
from datetime import datetime

from ai_trader.models.domain import Exchange, Instrument, Segment

log = logging.getLogger(__name__)


class InstrumentMaster:
    """In-memory cache of instruments from broker."""

    def __init__(self) -> None:
        self._instruments: list[Instrument] = []
        self._by_token: dict[int, Instrument] = {}
        self._by_symbol: dict[str, Instrument] = {}

    def load(self, instruments: list[Instrument]) -> None:
        self._instruments = instruments
        self._by_token = {i.instrument_token: i for i in instruments}
        self._by_symbol = {f"{i.exchange.value}:{i.tradingsymbol}": i for i in instruments}
        log.info("Loaded %d instruments", len(instruments))

    def get_by_token(self, token: int) -> Instrument | None:
        return self._by_token.get(token)

    def get_by_symbol(self, exchange: str, symbol: str) -> Instrument | None:
        return self._by_symbol.get(f"{exchange}:{symbol}")

    def nifty_index(self) -> Instrument | None:
        return self.get_by_symbol("NSE", "NIFTY 50") or self.get_by_symbol("NSE", "NIFTY")

    def nifty_options(self, expiry: str | None = None) -> list[Instrument]:
        """Get all Nifty options, optionally filtered by expiry."""
        result: list[Instrument] = []
        for inst in self._instruments:
            if inst.exchange != Exchange.NFO or inst.segment != Segment.OPTIONS:
                continue
            if "NIFTY" not in inst.tradingsymbol:
                continue
            if "BANKNIFTY" in inst.tradingsymbol:
                continue
            if expiry and inst.expiry != expiry:
                continue
            result.append(inst)
        return result

    def nearest_expiry(self) -> str | None:
        """Find nearest weekly expiry for Nifty options."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        expiries: set[str] = set()
        for inst in self.nifty_options():
            if inst.expiry and inst.expiry >= today:
                expiries.add(inst.expiry)
        if not expiries:
            return None
        return min(expiries)

    def options_for_strike(self, strike: float, expiry: str) -> tuple[Instrument | None, Instrument | None]:
        """Get CE and PE instruments for a given strike and expiry."""
        ce, pe = None, None
        for inst in self.nifty_options(expiry):
            if inst.strike == strike:
                if inst.option_type == "CE":
                    ce = inst
                elif inst.option_type == "PE":
                    pe = inst
        return ce, pe
