"""Tests for config/watchlist loader and token resolver."""

from __future__ import annotations

from pathlib import Path

from billionaire.marketdata.watchlist import load_watchlist_symbols, resolve_tokens
from billionaire.models import Exchange, Instrument, Segment


class _FakeMaster:
    """Minimal stand-in for InstrumentMaster.by_symbol."""

    def __init__(self, mapping: dict[str, Instrument]) -> None:
        self._m = mapping

    def by_symbol(self, symbol: str) -> Instrument | None:
        return self._m.get(symbol)


def test_load_watchlist_symbols_reads_indices_and_equity(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        """
watchlist:
  indices:
    - NSE:NIFTY 50
    - NSE:NIFTY BANK
  equity:
    - NSE:RELIANCE
    - NSE:INFY
  derivatives:
    auto_load_current_expiry: true
""".strip()
    )
    symbols = load_watchlist_symbols(cfg)
    assert symbols == [
        "NSE:NIFTY 50",
        "NSE:NIFTY BANK",
        "NSE:RELIANCE",
        "NSE:INFY",
    ]


def test_load_watchlist_symbols_missing_file_returns_empty(tmp_path: Path) -> None:
    assert load_watchlist_symbols(tmp_path / "nope.yaml") == []


def test_load_watchlist_symbols_ignores_malformed_entries(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        """
watchlist:
  indices:
    - NSE:NIFTY 50
    - 12345
    - NO_COLON_HERE
  equity: null
""".strip()
    )
    assert load_watchlist_symbols(cfg) == ["NSE:NIFTY 50"]


def test_resolve_tokens_splits_found_and_missing() -> None:
    master = _FakeMaster(
        {
            "NSE:RELIANCE": Instrument(
                instrument_token=738561,
                tradingsymbol="RELIANCE",
                exchange=Exchange.NSE,
                segment=Segment.EQUITY,
            ),
            "NSE:INFY": Instrument(
                instrument_token=408065,
                tradingsymbol="INFY",
                exchange=Exchange.NSE,
                segment=Segment.EQUITY,
            ),
        }
    )
    tokens, missing = resolve_tokens(
        ["NSE:RELIANCE", "NSE:INFY", "NSE:NIFTY 50"], master  # type: ignore[arg-type]
    )
    assert sorted(tokens) == [408065, 738561]
    assert missing == ["NSE:NIFTY 50"]


def test_resolve_tokens_skips_zero_token() -> None:
    master = _FakeMaster(
        {
            "NSE:FOO": Instrument(
                instrument_token=0,
                tradingsymbol="FOO",
                exchange=Exchange.NSE,
                segment=Segment.EQUITY,
            ),
        }
    )
    tokens, missing = resolve_tokens(["NSE:FOO"], master)  # type: ignore[arg-type]
    assert tokens == []
    assert missing == ["NSE:FOO"]
