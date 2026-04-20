"""Watchlist loader.

Reads the ``watchlist:`` section of ``config/config.yaml`` and resolves each
``EXCHANGE:TRADINGSYMBOL`` entry to an instrument token via the live broker's
instrument master. Used by the startup routine to subscribe the KiteTicker
WebSocket to the configured symbols so the dashboard actually streams.

Derivatives with ``auto_load_current_expiry: true`` are recognised but not
resolved here — that needs an option-chain picker which is out of scope for
this module.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from billionaire.marketdata.instruments import InstrumentMaster

log = logging.getLogger(__name__)


def load_watchlist_symbols(config_path: Path) -> list[str]:
    """Return a list of ``EXCHANGE:TRADINGSYMBOL`` strings from config.yaml.

    Missing file / empty section returns ``[]`` (not an error — the platform
    still boots, the WebSocket just has nothing to subscribe to).
    """
    if not config_path.exists():
        log.warning("Watchlist config not found at %s; subscribing to nothing.", config_path)
        return []
    try:
        data = yaml.safe_load(config_path.read_text()) or {}
    except yaml.YAMLError as e:
        log.warning("Watchlist config %s is not valid YAML: %s", config_path, e)
        return []

    wl = data.get("watchlist") or {}
    symbols: list[str] = []
    for section_name in ("indices", "equity"):
        section = wl.get(section_name) or []
        if isinstance(section, list):
            symbols.extend(str(s) for s in section if isinstance(s, str) and ":" in s)
    return symbols


def resolve_tokens(
    symbols: list[str], master: InstrumentMaster
) -> tuple[list[int], list[str]]:
    """Return (tokens_found, symbols_missing).

    ``InstrumentMaster`` indexes its cache as ``EXCHANGE:TRADINGSYMBOL``, so we
    pass the config values through unchanged.
    """
    tokens: list[int] = []
    missing: list[str] = []
    for sym in symbols:
        inst = master.by_symbol(sym)
        if inst is None or not inst.instrument_token:
            missing.append(sym)
            continue
        tokens.append(inst.instrument_token)
    return tokens, missing
