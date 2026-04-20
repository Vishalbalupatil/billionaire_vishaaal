"""Options analytics: option-chain summarisation, IV & simple greeks,
PCR, max-pain, and volatility regime classification.

Greeks use a plain Black-Scholes model (European, no dividends). Intended for
decision support — not for risk-book pricing.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

SQRT_2PI = math.sqrt(2 * math.pi)


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / SQRT_2PI


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs_price(spot: float, strike: float, t: float, r: float, sigma: float, opt: str) -> float:
    if sigma <= 0 or t <= 0 or spot <= 0 or strike <= 0:
        return max(0.0, (spot - strike) if opt == "CE" else (strike - spot))
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma * sigma) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    if opt == "CE":
        return spot * _norm_cdf(d1) - strike * math.exp(-r * t) * _norm_cdf(d2)
    return strike * math.exp(-r * t) * _norm_cdf(-d2) - spot * _norm_cdf(-d1)


def implied_vol(
    price: float, spot: float, strike: float, t: float, r: float, opt: str, lo: float = 0.01, hi: float = 5.0
) -> float:
    """Bisection IV; good enough for dashboard display."""
    if price <= 0 or t <= 0:
        return float("nan")
    for _ in range(80):
        mid = (lo + hi) / 2
        p = bs_price(spot, strike, t, r, mid, opt)
        if abs(p - price) < 1e-4:
            return mid
        if p > price:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def greeks(spot: float, strike: float, t: float, r: float, sigma: float, opt: str) -> dict[str, float]:
    if sigma <= 0 or t <= 0:
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    d1 = (math.log(spot / strike) + (r + 0.5 * sigma * sigma) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    pdf = _norm_pdf(d1)
    if opt == "CE":
        delta = _norm_cdf(d1)
        theta = (-spot * pdf * sigma / (2 * math.sqrt(t))) - r * strike * math.exp(-r * t) * _norm_cdf(d2)
    else:
        delta = _norm_cdf(d1) - 1
        theta = (-spot * pdf * sigma / (2 * math.sqrt(t))) + r * strike * math.exp(-r * t) * _norm_cdf(-d2)
    gamma = pdf / (spot * sigma * math.sqrt(t))
    vega = spot * pdf * math.sqrt(t) / 100.0  # per 1% vol change
    return {"delta": delta, "gamma": gamma, "theta": theta / 365.0, "vega": vega}


@dataclass
class OptionRow:
    strike: float
    ce_ltp: float = 0.0
    pe_ltp: float = 0.0
    ce_oi: int = 0
    pe_oi: int = 0
    ce_volume: int = 0
    pe_volume: int = 0
    ce_iv: float = 0.0
    pe_iv: float = 0.0


@dataclass
class OptionChainInsights:
    spot: float
    atm_strike: float
    pcr_oi: float
    pcr_volume: float
    max_pain: float
    total_ce_oi: int
    total_pe_oi: int
    call_wall: float      # strike with highest CE OI above spot
    put_wall: float       # strike with highest PE OI below spot
    bias: str             # "bullish" | "bearish" | "neutral"
    atm_ce_iv: float
    atm_pe_iv: float


class OptionsEngine:
    def __init__(self, r: float = 0.065) -> None:
        """r: risk-free rate used for IV/greeks (India 10Y approx)."""
        self.r = r

    @staticmethod
    def _nearest_strike(rows: list[OptionRow], spot: float) -> OptionRow:
        return min(rows, key=lambda x: abs(x.strike - spot))

    @staticmethod
    def _time_to_expiry_years(expiry: str | date | datetime) -> float:
        if isinstance(expiry, str):
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y%m%d"):
                try:
                    expiry_dt = datetime.strptime(expiry, fmt)
                    break
                except ValueError:
                    continue
            else:
                return 7 / 365.0
        elif isinstance(expiry, date) and not isinstance(expiry, datetime):
            expiry_dt = datetime.combine(expiry, datetime.min.time())
        else:
            expiry_dt = expiry
        delta = expiry_dt - datetime.utcnow()
        return max(delta.total_seconds() / (365 * 86400), 1 / (365 * 24))

    def insights(self, spot: float, rows: Iterable[OptionRow]) -> OptionChainInsights:
        rows = sorted(rows, key=lambda x: x.strike)
        if not rows:
            return OptionChainInsights(spot, spot, 0, 0, spot, 0, 0, spot, spot, "neutral", 0, 0)
        atm = self._nearest_strike(rows, spot)
        total_ce = sum(r.ce_oi for r in rows)
        total_pe = sum(r.pe_oi for r in rows)
        total_ce_vol = sum(r.ce_volume for r in rows) or 1
        total_pe_vol = sum(r.pe_volume for r in rows) or 1
        pcr_oi = total_pe / max(total_ce, 1)
        pcr_vol = total_pe_vol / max(total_ce_vol, 1)

        # Max pain: strike that minimises total writer pay-off at expiry
        def pain(k: float) -> float:
            return sum(max(0.0, k - r.strike) * r.ce_oi + max(0.0, r.strike - k) * r.pe_oi for r in rows)

        max_pain = min((r.strike for r in rows), key=pain)

        above = [r for r in rows if r.strike >= spot]
        below = [r for r in rows if r.strike <= spot]
        call_wall = max(above, key=lambda r: r.ce_oi).strike if above else atm.strike
        put_wall = max(below, key=lambda r: r.pe_oi).strike if below else atm.strike

        if pcr_oi > 1.3 and spot > max_pain:
            bias = "bullish"
        elif pcr_oi < 0.7 and spot < max_pain:
            bias = "bearish"
        else:
            bias = "neutral"

        return OptionChainInsights(
            spot=spot,
            atm_strike=atm.strike,
            pcr_oi=pcr_oi,
            pcr_volume=pcr_vol,
            max_pain=max_pain,
            total_ce_oi=total_ce,
            total_pe_oi=total_pe,
            call_wall=call_wall,
            put_wall=put_wall,
            bias=bias,
            atm_ce_iv=atm.ce_iv,
            atm_pe_iv=atm.pe_iv,
        )

    def enrich_iv(
        self, rows: list[OptionRow], spot: float, expiry: str | date | datetime
    ) -> list[OptionRow]:
        """Populate IV for each row using Black-Scholes bisection."""
        t = self._time_to_expiry_years(expiry)
        for row in rows:
            if row.ce_ltp > 0:
                row.ce_iv = implied_vol(row.ce_ltp, spot, row.strike, t, self.r, "CE")
            if row.pe_ltp > 0:
                row.pe_iv = implied_vol(row.pe_ltp, spot, row.strike, t, self.r, "PE")
        return rows

    @staticmethod
    def parse_kite_chain(quote: dict[str, Any], strike_key_fn=None) -> list[OptionRow]:
        """Convert a Kite ``quote`` payload of CE/PE instruments into rows.

        ``strike_key_fn`` takes an instrument symbol and returns (strike, 'CE'|'PE').
        """
        if strike_key_fn is None:
            def strike_key_fn(sym: str) -> tuple[float, str]:
                opt = sym[-2:]
                # naive parse — real code should use instrument master
                digits = ""
                for ch in reversed(sym[:-2]):
                    if ch.isdigit() or ch == ".":
                        digits = ch + digits
                    else:
                        break
                return (float(digits or 0), opt)

        rows: dict[float, OptionRow] = {}
        for sym, q in quote.items():
            strike, opt = strike_key_fn(sym)
            row = rows.setdefault(strike, OptionRow(strike=strike))
            ltp = float(q.get("last_price") or 0)
            oi = int(q.get("oi") or 0)
            vol = int(q.get("volume") or 0)
            if opt == "CE":
                row.ce_ltp, row.ce_oi, row.ce_volume = ltp, oi, vol
            else:
                row.pe_ltp, row.pe_oi, row.pe_volume = ltp, oi, vol
        return sorted(rows.values(), key=lambda r: r.strike)
