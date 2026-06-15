"""Options pricing utilities and helpers."""

from __future__ import annotations

from datetime import datetime


def days_to_expiry(expiry_str: str) -> int:
    """Calculate trading days to expiry."""
    try:
        expiry = datetime.strptime(expiry_str, "%Y-%m-%d")
        delta = expiry - datetime.utcnow()
        return max(0, delta.days)
    except (ValueError, TypeError):
        return 0


def time_to_expiry_years(expiry_str: str) -> float:
    """Calculate time to expiry in years."""
    days = days_to_expiry(expiry_str)
    return max(1 / 365, days / 365)


def moneyness(spot: float, strike: float, option_type: str = "CE") -> str:
    """Classify option moneyness."""
    pct = (spot - strike) / spot * 100
    if option_type == "CE":
        if pct > 1:
            return "ITM"
        elif pct < -1:
            return "OTM"
        return "ATM"
    else:  # PE
        if pct < -1:
            return "ITM"
        elif pct > 1:
            return "OTM"
        return "ATM"


def nifty_strikes(spot: float, count: int = 20, step: float = 50.0) -> list[float]:
    """Generate Nifty 50 strike prices around the spot price.

    Nifty strikes are at 50-point intervals.
    """
    atm = round(spot / step) * step
    half = count // 2
    return [atm + (i - half) * step for i in range(count)]
