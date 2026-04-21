"""Black-Scholes option pricing for the options leg of the ORB backtest.

Why Black-Scholes and not real historical option fills?

Kite Connect's historical_data endpoint takes an ``instrument_token``. Option
tokens change per (strike, expiry, call/put) and Kite only publishes the
**current** instruments master — there is no API to discover what tokens
existed on a given historical date. The only ways to backtest real option
prices are:

    * Scrape & store instruments dumps daily (2+ years of history = not
      possible retroactively);
    * Subscribe to a paid historical options vendor (~lakhs/year);
    * Approximate theoretical option prices from historical spot + VIX.

This module takes the third route. India VIX is available via Kite's
historical_data (instrument_token ``264969``), so for any (spot, strike, VIX,
time-to-expiry) tuple we can compute the theoretical ATM call/put premium.

Accuracy: for liquid ATM Nifty options within the last 60 days of expiry,
Black-Scholes with India-VIX volatility typically sits within 5-15% of
realised premia. It systematically under-prices deep ITM options (ignores
skew) and over-prices deep OTM ones — neither of which matter for ATM ORB.

The module deliberately has no dependencies beyond ``math`` for numerical
stability and unit-testability on constrained hosts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum


class OptionType(str, Enum):
    CALL = "CE"
    PUT = "PE"


# ATM strike step for Nifty. Nifty options are listed at 50-point intervals
# (except weekly-expiry weeks where step varies; we conservatively use 50
# throughout — close enough for ATM backtesting).
NIFTY_STRIKE_STEP = 50

# Risk-free rate used in Black-Scholes. 10y GoI yield has been 6.9-7.5%
# through 2023-2024; 7.5% is a defensible flat assumption that keeps the
# options leg reproducible.
DEFAULT_RISK_FREE_RATE = 0.075

# Dividend yield on the Nifty 50 index: spot price accrues dividends out
# over the year. Historically 1.2-1.5% — use 1.3% flat.
DEFAULT_DIVIDEND_YIELD = 0.013

# ``VIX`` is quoted in percentage terms (e.g. ``18.5`` means 18.5% annualised
# vol). Convert to the decimal ``sigma`` Black-Scholes expects.
def vix_to_sigma(vix_value: float) -> float:
    return max(vix_value, 0.0) / 100.0


def atm_strike(spot: float, step: int = NIFTY_STRIKE_STEP) -> int:
    """Round ``spot`` to the nearest listed strike.

    Breaking ties upwards (bankers' rounding would be artifically pessimistic
    on calls half the time). Returns int because listed strikes are integer.
    """
    return int(round(spot / step) * step)


# Standard normal cumulative distribution. Using ``math.erf`` avoids pulling
# scipy into the backend purely for this call.
def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


@dataclass(frozen=True)
class BSInputs:
    """Inputs to Black-Scholes. Spot, strike, time-to-expiry (in years),
    annualised volatility, risk-free rate, dividend yield."""

    S: float  # spot
    K: float  # strike
    T: float  # time to expiry in years
    sigma: float  # annualised vol, decimal
    r: float = DEFAULT_RISK_FREE_RATE
    q: float = DEFAULT_DIVIDEND_YIELD


@dataclass(frozen=True)
class OptionQuote:
    """Theoretical premium + key greeks at a point in time."""

    premium: float
    delta: float
    gamma: float
    theta: float  # per day
    vega: float  # per 1-vol-point
    intrinsic: float
    time_value: float


def _bs_core(inp: BSInputs) -> tuple[float, float]:
    """Return (d1, d2) from the Black-Scholes model. Separated to make
    call/put pricing share the same numerical core."""
    if inp.T <= 0 or inp.sigma <= 0:
        # Degenerate cases: at/after expiry or zero vol — no time value.
        return (float("inf"), float("inf"))
    sqrt_t = math.sqrt(inp.T)
    d1 = (
        math.log(inp.S / inp.K)
        + (inp.r - inp.q + 0.5 * inp.sigma**2) * inp.T
    ) / (inp.sigma * sqrt_t)
    d2 = d1 - inp.sigma * sqrt_t
    return (d1, d2)


def price_call(inp: BSInputs) -> OptionQuote:
    """Black-Scholes European call with continuous dividend yield."""
    intrinsic = max(inp.S - inp.K, 0.0)
    if inp.T <= 0:
        return OptionQuote(
            premium=intrinsic, delta=1.0 if inp.S > inp.K else 0.0,
            gamma=0.0, theta=0.0, vega=0.0,
            intrinsic=intrinsic, time_value=0.0,
        )
    d1, d2 = _bs_core(inp)
    call = (
        inp.S * math.exp(-inp.q * inp.T) * _norm_cdf(d1)
        - inp.K * math.exp(-inp.r * inp.T) * _norm_cdf(d2)
    )
    pdf_d1 = math.exp(-d1 * d1 / 2.0) / math.sqrt(2.0 * math.pi)
    delta = math.exp(-inp.q * inp.T) * _norm_cdf(d1)
    gamma = (
        math.exp(-inp.q * inp.T) * pdf_d1 / (inp.S * inp.sigma * math.sqrt(inp.T))
    )
    # Theta expressed per day to match how human traders think about decay.
    theta_year = (
        -inp.S * math.exp(-inp.q * inp.T) * pdf_d1 * inp.sigma
        / (2.0 * math.sqrt(inp.T))
        - inp.r * inp.K * math.exp(-inp.r * inp.T) * _norm_cdf(d2)
        + inp.q * inp.S * math.exp(-inp.q * inp.T) * _norm_cdf(d1)
    )
    theta = theta_year / 365.0
    vega = inp.S * math.exp(-inp.q * inp.T) * pdf_d1 * math.sqrt(inp.T) / 100.0
    return OptionQuote(
        premium=max(call, 0.0),
        delta=delta,
        gamma=gamma,
        theta=theta,
        vega=vega,
        intrinsic=intrinsic,
        time_value=max(call - intrinsic, 0.0),
    )


def price_put(inp: BSInputs) -> OptionQuote:
    """Black-Scholes European put with continuous dividend yield."""
    intrinsic = max(inp.K - inp.S, 0.0)
    if inp.T <= 0:
        return OptionQuote(
            premium=intrinsic, delta=-1.0 if inp.S < inp.K else 0.0,
            gamma=0.0, theta=0.0, vega=0.0,
            intrinsic=intrinsic, time_value=0.0,
        )
    d1, d2 = _bs_core(inp)
    put = (
        inp.K * math.exp(-inp.r * inp.T) * _norm_cdf(-d2)
        - inp.S * math.exp(-inp.q * inp.T) * _norm_cdf(-d1)
    )
    pdf_d1 = math.exp(-d1 * d1 / 2.0) / math.sqrt(2.0 * math.pi)
    delta = math.exp(-inp.q * inp.T) * (_norm_cdf(d1) - 1.0)
    gamma = (
        math.exp(-inp.q * inp.T) * pdf_d1 / (inp.S * inp.sigma * math.sqrt(inp.T))
    )
    theta_year = (
        -inp.S * math.exp(-inp.q * inp.T) * pdf_d1 * inp.sigma
        / (2.0 * math.sqrt(inp.T))
        + inp.r * inp.K * math.exp(-inp.r * inp.T) * _norm_cdf(-d2)
        - inp.q * inp.S * math.exp(-inp.q * inp.T) * _norm_cdf(-d1)
    )
    theta = theta_year / 365.0
    vega = inp.S * math.exp(-inp.q * inp.T) * pdf_d1 * math.sqrt(inp.T) / 100.0
    return OptionQuote(
        premium=max(put, 0.0),
        delta=delta,
        gamma=gamma,
        theta=theta,
        vega=vega,
        intrinsic=intrinsic,
        time_value=max(put - intrinsic, 0.0),
    )


def price(option_type: OptionType, inp: BSInputs) -> OptionQuote:
    if option_type == OptionType.CALL:
        return price_call(inp)
    return price_put(inp)


def last_thursday_of_month(year: int, month: int) -> date:
    """Nifty monthly options expire on the last Thursday of the contract
    month (NSE circular: shifted to prior business day on holidays; we
    conservatively return the last Thursday and let callers skip holidays
    since the backtest only uses the day as a ceiling for time-to-expiry)."""
    next_month = date(year, month, 28) + timedelta(days=4)
    first_of_next = next_month.replace(day=1)
    last_day = first_of_next - timedelta(days=1)
    # Thursday's weekday() == 3.
    offset = (last_day.weekday() - 3) % 7
    return last_day - timedelta(days=offset)


def current_month_expiry(now: datetime) -> date:
    """Return the current-month expiry date for a given instant in IST.

    If ``now`` is *after* this month's expiry, the contract has already
    rolled — return next month's expiry.
    """
    exp = last_thursday_of_month(now.year, now.month)
    if now.date() > exp:
        # Rolled into next month already.
        if now.month == 12:
            return last_thursday_of_month(now.year + 1, 1)
        return last_thursday_of_month(now.year, now.month + 1)
    return exp


def years_to_expiry(now: datetime, expiry: date, *, hours_per_day: float = 6.25) -> float:
    """Time to expiry in years, using calendar-day convention.

    6.25 trading hours per day (09:15-15:30) is the NSE equity-options
    convention. We blend calendar days with intraday fractional time so a
    09:20 entry on expiry day correctly reports ~6 hours of time value left.
    """
    if expiry < now.date():
        return 0.0
    # Calendar days remaining (inclusive of today up to expiry).
    days = (expiry - now.date()).days
    # Fractional day remaining from ``now`` to 15:30 IST.
    open_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
    close_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
    if now < open_time:
        frac_today = 1.0
    elif now >= close_time:
        frac_today = 0.0
    else:
        elapsed_hours = (now - open_time).total_seconds() / 3600.0
        frac_today = max(0.0, 1.0 - elapsed_hours / hours_per_day)
    total_days = max(0.0, days - 1) + frac_today
    return total_days / 365.0
