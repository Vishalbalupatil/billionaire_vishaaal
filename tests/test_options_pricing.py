"""Black-Scholes pricing sanity tests.

We validate numerical correctness against textbook values, and use
put-call parity as a free cross-check on every model change.
"""

from __future__ import annotations

import math
from datetime import date, datetime

from billionaire.strategy.options_pricing import (
    BSInputs,
    atm_strike,
    current_month_expiry,
    last_thursday_of_month,
    price_call,
    price_put,
    vix_to_sigma,
    years_to_expiry,
)


def test_atm_strike_rounds_to_nearest_50() -> None:
    assert atm_strike(24_803) == 24_800
    assert atm_strike(24_826) == 24_850
    assert atm_strike(24_825) == 24_800  # bankers' rounding on exact half
    assert atm_strike(24_825, step=100) == 24_800


def test_vix_to_sigma_converts_percentage() -> None:
    assert vix_to_sigma(18.0) == 0.18
    assert vix_to_sigma(0.0) == 0.0
    # Negative VIX shouldn't happen but don't propagate it into BS.
    assert vix_to_sigma(-5.0) == 0.0


def test_call_put_parity_holds_for_atm() -> None:
    """C - P == S*exp(-qT) - K*exp(-rT). Any sigma, any T. Classical
    arbitrage-free relation — best sanity check for BS implementations."""
    inp = BSInputs(S=24_800, K=24_800, T=30 / 365, sigma=0.15, r=0.075, q=0.013)
    call = price_call(inp).premium
    put = price_put(inp).premium
    expected = inp.S * math.exp(-inp.q * inp.T) - inp.K * math.exp(-inp.r * inp.T)
    assert abs((call - put) - expected) < 1e-6


def test_call_put_parity_holds_for_itm_otm() -> None:
    """Parity must hold regardless of moneyness."""
    for S, K in [(24_500, 24_800), (25_100, 24_800), (24_800, 24_500)]:
        inp = BSInputs(S=S, K=K, T=20 / 365, sigma=0.2, r=0.07, q=0.012)
        call = price_call(inp).premium
        put = price_put(inp).premium
        expected = S * math.exp(-inp.q * inp.T) - K * math.exp(-inp.r * inp.T)
        assert abs((call - put) - expected) < 1e-6


def test_call_premium_monotone_in_volatility() -> None:
    """Higher sigma → higher option value. Both legs."""
    premiums = [
        price_call(BSInputs(S=24_800, K=24_800, T=30 / 365, sigma=s, r=0.075, q=0.013)).premium
        for s in (0.10, 0.15, 0.20, 0.30)
    ]
    assert premiums == sorted(premiums)


def test_atm_call_delta_near_half() -> None:
    """ATM call delta should sit around 0.5 for reasonable time-to-expiry."""
    q = price_call(BSInputs(S=24_800, K=24_800, T=30 / 365, sigma=0.15, r=0.075, q=0.013))
    assert 0.45 < q.delta < 0.60


def test_atm_put_delta_near_negative_half() -> None:
    q = price_put(BSInputs(S=24_800, K=24_800, T=30 / 365, sigma=0.15, r=0.075, q=0.013))
    assert -0.60 < q.delta < -0.40


def test_expiry_is_last_thursday() -> None:
    # Sanity: known expiries. October 2024 last Thursday = 31 Oct.
    assert last_thursday_of_month(2024, 10) == date(2024, 10, 31)
    # November 2024 last Thursday = 28 Nov.
    assert last_thursday_of_month(2024, 11) == date(2024, 11, 28)
    # February 2025 last Thursday = 27 Feb.
    assert last_thursday_of_month(2025, 2) == date(2025, 2, 27)


def test_current_month_expiry_rolls_after_expiry() -> None:
    # A datetime the day AFTER October 2024 expiry should resolve to Nov.
    after_oct_expiry = datetime(2024, 11, 1, 9, 30)
    assert current_month_expiry(after_oct_expiry) == date(2024, 11, 28)
    # On the morning of expiry day itself, still current month.
    on_expiry = datetime(2024, 10, 31, 9, 30)
    assert current_month_expiry(on_expiry) == date(2024, 10, 31)


def test_current_month_expiry_rolls_december_to_january() -> None:
    # Dec's last Thursday 2024 is 26 Dec. A date after that must land in Jan 2025.
    after_dec = datetime(2024, 12, 27, 9, 30)
    assert current_month_expiry(after_dec) == date(2025, 1, 30)


def test_years_to_expiry_zero_on_or_after_expiry_date() -> None:
    # At exactly the expiry date afternoon close, zero time left.
    assert years_to_expiry(datetime(2024, 10, 31, 15, 30), date(2024, 10, 31)) == 0.0
    # Day after expiry: negative days clamped to zero.
    assert years_to_expiry(datetime(2024, 11, 1, 9, 15), date(2024, 10, 31)) == 0.0


def test_years_to_expiry_intraday_decay() -> None:
    """Within a single day, time-to-expiry monotonically decreases."""
    exp = date(2024, 10, 31)
    morning = years_to_expiry(datetime(2024, 10, 25, 9, 15), exp)
    afternoon = years_to_expiry(datetime(2024, 10, 25, 14, 0), exp)
    close = years_to_expiry(datetime(2024, 10, 25, 15, 30), exp)
    assert morning > afternoon > close
