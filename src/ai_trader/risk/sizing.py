"""Position sizing algorithms.

Determines how many lots/shares to trade based on:
- Risk per trade (% of capital)
- Stop loss distance
- Kelly criterion (optional)
"""

from __future__ import annotations


def fixed_fraction_size(
    capital: float,
    risk_pct: float,
    entry: float,
    stop_loss: float,
    lot_size: int = 1,
) -> int:
    """Fixed fractional sizing — risk a fixed % of capital per trade.

    Returns number of shares/contracts (rounded down to lot_size).
    """
    risk_amount = capital * (risk_pct / 100)
    risk_per_unit = abs(entry - stop_loss)
    if risk_per_unit <= 0:
        return 0
    raw_qty = risk_amount / risk_per_unit
    lots = max(1, int(raw_qty // lot_size))
    return lots * lot_size


def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Kelly criterion — optimal fraction of capital to risk.

    Returns a fraction between 0 and 1.
    """
    if avg_loss == 0 or win_rate <= 0:
        return 0.0
    b = avg_win / avg_loss
    kelly = win_rate - (1 - win_rate) / b
    # Half-Kelly for safety
    return max(0.0, min(kelly * 0.5, 0.25))


def options_lot_size(
    capital: float,
    max_premium_pct: float,
    premium_per_lot: float,
    lot_size: int = 25,
) -> int:
    """Determine max lots for options based on premium budget.

    Ensures we don't spend more than max_premium_pct of capital on premium.
    """
    max_premium = capital * (max_premium_pct / 100)
    if premium_per_lot <= 0:
        return 0
    lots = int(max_premium / premium_per_lot)
    return max(1, lots)
