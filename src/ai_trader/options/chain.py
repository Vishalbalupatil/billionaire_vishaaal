"""Options chain analysis — PCR, max pain, call/put walls, IV skew."""

from __future__ import annotations

import logging
from datetime import datetime

from ai_trader.models.options import Greeks, OptionChainRow
from ai_trader.options.greeks import calculate_greeks, implied_volatility

log = logging.getLogger(__name__)

# Risk-free rate for Indian markets (approximate)
RISK_FREE_RATE = 0.07


def build_chain_from_quotes(
    spot: float,
    strikes: list[float],
    expiry_str: str,
    ce_prices: dict[float, float],
    pe_prices: dict[float, float],
    ce_oi: dict[float, int] | None = None,
    pe_oi: dict[float, int] | None = None,
    ce_volume: dict[float, int] | None = None,
    pe_volume: dict[float, int] | None = None,
) -> list[OptionChainRow]:
    """Build an options chain from market quotes.

    Parameters
    ----------
    spot : Current spot price of underlying.
    strikes : List of strike prices.
    expiry_str : Expiry date string (e.g. "2024-06-27").
    ce_prices / pe_prices : Strike → LTP mappings.
    ce_oi / pe_oi : Strike → OI mappings.
    ce_volume / pe_volume : Strike → volume mappings.
    """
    ce_oi = ce_oi or {}
    pe_oi = pe_oi or {}
    ce_volume = ce_volume or {}
    pe_volume = pe_volume or {}

    # Days to expiry → years
    try:
        expiry_dt = datetime.strptime(expiry_str, "%Y-%m-%d")
        days = max(1, (expiry_dt - datetime.utcnow()).days)
    except (ValueError, TypeError):
        days = 7
    T = days / 365

    chain: list[OptionChainRow] = []
    for strike in sorted(strikes):
        ce_ltp = ce_prices.get(strike, 0.0)
        pe_ltp = pe_prices.get(strike, 0.0)

        ce_iv_val = 0.0
        pe_iv_val = 0.0
        ce_greeks = Greeks()
        pe_greeks = Greeks()

        if ce_ltp > 0:
            ce_iv_val = implied_volatility(ce_ltp, spot, strike, T, RISK_FREE_RATE, "CE")
            ce_greeks = calculate_greeks(spot, strike, T, RISK_FREE_RATE, ce_iv_val, "CE")

        if pe_ltp > 0:
            pe_iv_val = implied_volatility(pe_ltp, spot, strike, T, RISK_FREE_RATE, "PE")
            pe_greeks = calculate_greeks(spot, strike, T, RISK_FREE_RATE, pe_iv_val, "PE")

        put_oi = pe_oi.get(strike, 0)
        call_oi = ce_oi.get(strike, 0)
        pcr = put_oi / call_oi if call_oi > 0 else 0.0

        chain.append(OptionChainRow(
            strike=strike,
            expiry=expiry_str,
            ce_ltp=ce_ltp,
            ce_oi=call_oi,
            ce_volume=ce_volume.get(strike, 0),
            ce_iv=round(ce_iv_val * 100, 2),
            ce_greeks=ce_greeks,
            pe_ltp=pe_ltp,
            pe_oi=put_oi,
            pe_volume=pe_volume.get(strike, 0),
            pe_iv=round(pe_iv_val * 100, 2),
            pe_greeks=pe_greeks,
            pcr=round(pcr, 2),
        ))

    return chain


def max_pain(chain: list[OptionChainRow], lot_size: int = 25) -> float:
    """Calculate max pain strike from options chain.

    Max pain = the strike at which total loss for option writers is minimized
    (equivalently, total premium expiring worthless is maximized).
    """
    if not chain:
        return 0.0

    strikes = [row.strike for row in chain]
    min_pain = float("inf")
    max_pain_strike = strikes[0]

    for test_strike in strikes:
        total_pain = 0.0
        for row in chain:
            # CE writers pain: if expiry above strike, CE buyers profit
            if test_strike > row.strike:
                total_pain += (test_strike - row.strike) * row.ce_oi * lot_size
            # PE writers pain: if expiry below strike, PE buyers profit
            if test_strike < row.strike:
                total_pain += (row.strike - test_strike) * row.pe_oi * lot_size

        if total_pain < min_pain:
            min_pain = total_pain
            max_pain_strike = test_strike

    return max_pain_strike


def pcr_overall(chain: list[OptionChainRow]) -> float:
    """Calculate overall Put-Call Ratio from chain OI."""
    total_ce_oi = sum(r.ce_oi for r in chain)
    total_pe_oi = sum(r.pe_oi for r in chain)
    if total_ce_oi == 0:
        return 0.0
    return round(total_pe_oi / total_ce_oi, 3)


def call_wall(chain: list[OptionChainRow]) -> float:
    """Strike with highest call OI — acts as resistance."""
    if not chain:
        return 0.0
    return max(chain, key=lambda r: r.ce_oi).strike


def put_wall(chain: list[OptionChainRow]) -> float:
    """Strike with highest put OI — acts as support."""
    if not chain:
        return 0.0
    return max(chain, key=lambda r: r.pe_oi).strike


def iv_skew(chain: list[OptionChainRow], spot: float) -> float:
    """IV skew: difference between OTM put IV and OTM call IV.

    Positive skew = puts are more expensive (fear/hedging demand).
    """
    otm_put_ivs = [r.pe_iv for r in chain if r.strike < spot and r.pe_iv > 0]
    otm_call_ivs = [r.ce_iv for r in chain if r.strike > spot and r.ce_iv > 0]

    avg_put_iv = sum(otm_put_ivs) / len(otm_put_ivs) if otm_put_ivs else 0
    avg_call_iv = sum(otm_call_ivs) / len(otm_call_ivs) if otm_call_ivs else 0

    return round(avg_put_iv - avg_call_iv, 2)
