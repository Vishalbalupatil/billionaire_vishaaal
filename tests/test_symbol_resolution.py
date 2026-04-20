"""Tests for the forecast endpoint's symbol → instrument_token resolution.

Devin Review flagged that ``/api/forecast`` was always hitting the synthetic
fallback because the InstrumentMaster indexes the index as ``NSE:NIFTY 50``
while the UI calls the endpoint with ``symbol="NIFTY"``. These tests lock in
the alias map so future refactors don't regress it.
"""

from __future__ import annotations

from billionaire.api.routes import SYMBOL_ALIASES, resolve_instrument_token
from billionaire.models import Exchange, Instrument, Segment


class _FakeInstruments:
    def __init__(self, items: dict[str, Instrument]) -> None:
        self._by_symbol = items

    def by_symbol(self, symbol: str) -> Instrument | None:
        return self._by_symbol.get(symbol)


def _inst(token: int, tradingsymbol: str, exchange: Exchange = Exchange.NSE) -> Instrument:
    return Instrument(
        instrument_token=token,
        tradingsymbol=tradingsymbol,
        exchange=exchange,
        segment=Segment.EQUITY,
    )


def test_nifty_short_name_resolves_to_index_token() -> None:
    """``symbol="NIFTY"`` must hit the ``NSE:NIFTY 50`` entry in the master."""
    master = _FakeInstruments({"NSE:NIFTY 50": _inst(256265, "NIFTY 50")})
    assert resolve_instrument_token(master, "NIFTY") == 256265
    assert resolve_instrument_token(master, "NIFTY50") == 256265
    assert resolve_instrument_token(master, "NIFTY 50") == 256265
    assert resolve_instrument_token(master, "nifty") == 256265


def test_constituent_equity_falls_back_to_nse_prefix() -> None:
    """Equities like ``RELIANCE`` still resolve without an alias."""
    master = _FakeInstruments({"NSE:RELIANCE": _inst(738561, "RELIANCE")})
    assert resolve_instrument_token(master, "RELIANCE") == 738561


def test_explicit_exchange_prefix_is_honoured() -> None:
    master = _FakeInstruments({"NSE:HDFCBANK": _inst(341249, "HDFCBANK")})
    assert resolve_instrument_token(master, "NSE:HDFCBANK") == 341249


def test_unknown_symbol_returns_zero_not_error() -> None:
    master = _FakeInstruments({})
    assert resolve_instrument_token(master, "DOES_NOT_EXIST") == 0


def test_none_instruments_returns_zero() -> None:
    assert resolve_instrument_token(None, "NIFTY") == 0


def test_alias_table_declares_every_ui_short_name() -> None:
    # Every short name the UI ships with must be in the alias table so the
    # live-data branch can actually fire.
    for short in ("NIFTY", "NIFTY50", "NIFTY 50"):
        assert short in SYMBOL_ALIASES
