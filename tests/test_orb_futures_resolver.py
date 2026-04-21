"""Regression tests for the front-month futures resolver.

The original resolver silently returned ``0`` when the instrument master
couldn't be iterated (no ``__iter__`` / ``by_underlying``), which led the
``backtest-orb`` CLI to hand ``token=0`` to Kite and get back "invalid
token" with no actionable error. These tests pin the fix.
"""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from billionaire.marketdata.historical_fetcher import (
    resolve_front_month_future_token,
)


def _fut(token: int, expiry: date, symbol: str = "NIFTY25APRFUT") -> SimpleNamespace:
    return SimpleNamespace(
        instrument_token=token,
        tradingsymbol=symbol,
        name="NIFTY",
        segment=SimpleNamespace(value="FUTURES"),
        expiry=expiry,
    )


def _spot() -> SimpleNamespace:
    return SimpleNamespace(
        instrument_token=256265,
        tradingsymbol="NIFTY 50",
        name="NIFTY 50",
        segment=SimpleNamespace(value="INDEX"),
        expiry=None,
    )


class _FakeMaster:
    """Minimal stand-in for :class:`InstrumentMaster` that implements the
    two entrypoints the resolver actually uses."""

    def __init__(self, items: list[SimpleNamespace]) -> None:
        self._items = items

    def __iter__(self):  # noqa: D401 — list snapshot
        return iter(self._items)

    def by_underlying(self, underlying: str) -> list[SimpleNamespace]:
        u = underlying.upper()
        return [i for i in self._items if (i.name or "").upper() == u]


def test_resolver_picks_nearest_future_expiry_on_or_after_today() -> None:
    now = datetime(2025, 4, 20)
    master = _FakeMaster([
        _fut(111, date(2025, 4, 24), "NIFTY25APRFUT"),
        _fut(222, date(2025, 5, 29), "NIFTY25MAYFUT"),
        _fut(333, date(2025, 6, 26), "NIFTY25JUNFUT"),
        _spot(),
    ])
    assert resolve_front_month_future_token(master, "NIFTY", now=now) == 111


def test_resolver_skips_expired_contracts() -> None:
    now = datetime(2025, 4, 25)  # APR expiry already passed
    master = _FakeMaster([
        _fut(111, date(2025, 4, 24), "NIFTY25APRFUT"),
        _fut(222, date(2025, 5, 29), "NIFTY25MAYFUT"),
    ])
    assert resolve_front_month_future_token(master, "NIFTY", now=now) == 222


def test_resolver_raises_lookup_error_when_no_matches() -> None:
    """Previously this returned 0 silently, which Kite rejected downstream
    with an opaque "invalid token" error."""
    master = _FakeMaster([_spot()])
    with pytest.raises(LookupError):
        resolve_front_month_future_token(master, "NIFTY")


def test_resolver_raises_when_all_candidates_expired() -> None:
    now = datetime(2026, 1, 1)
    master = _FakeMaster([_fut(111, date(2025, 4, 24), "NIFTY25APRFUT")])
    with pytest.raises(LookupError):
        resolve_front_month_future_token(master, "NIFTY", now=now)


def test_resolver_falls_back_to_tradingsymbol_suffix() -> None:
    """Belt-and-suspenders: if Kite ships a schema tweak and ``segment``
    stops matching, an instrument whose ``tradingsymbol`` ends in ``FUT``
    should still be picked up."""
    now = datetime(2025, 4, 20)
    weird = SimpleNamespace(
        instrument_token=999,
        tradingsymbol="NIFTY25APRFUT",
        name="NIFTY",
        segment=SimpleNamespace(value="NFO-FUT"),  # unnormalised
        expiry=date(2025, 4, 24),
    )
    master = _FakeMaster([weird])
    assert resolve_front_month_future_token(master, "NIFTY", now=now) == 999


def test_resolver_handles_instruments_none() -> None:
    with pytest.raises(LookupError):
        resolve_front_month_future_token(None, "NIFTY")
