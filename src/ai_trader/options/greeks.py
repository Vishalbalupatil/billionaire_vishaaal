"""Black-Scholes options pricing and Greeks calculator.

Provides:
- European call/put pricing
- Implied Volatility (Newton-Raphson)
- Delta, Gamma, Theta, Vega
"""

from __future__ import annotations

import math

from scipy.stats import norm

from ai_trader.models.options import Greeks


def _d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
    if T <= 0 or sigma <= 0:
        return 0.0
    return (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))


def _d2(S: float, K: float, T: float, r: float, sigma: float) -> float:
    return _d1(S, K, T, r, sigma) - sigma * math.sqrt(T)


def call_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes European call price.

    Parameters
    ----------
    S : spot price
    K : strike price
    T : time to expiry in years
    r : risk-free rate (annual, e.g. 0.07 for 7%)
    sigma : volatility (annual, e.g. 0.15 for 15%)
    """
    if T <= 0:
        return max(S - K, 0.0)
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)
    return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)


def put_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes European put price."""
    if T <= 0:
        return max(K - S, 0.0)
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def implied_volatility(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: str = "CE",
    max_iter: int = 100,
    tol: float = 1e-6,
) -> float:
    """Calculate implied volatility using Newton-Raphson method."""
    if T <= 0 or market_price <= 0:
        return 0.0

    sigma = 0.20  # initial guess
    price_fn = call_price if option_type == "CE" else put_price

    for _ in range(max_iter):
        price = price_fn(S, K, T, r, sigma)
        v = vega(S, K, T, r, sigma)
        if v < 1e-10:
            break
        diff = price - market_price
        if abs(diff) < tol:
            break
        sigma -= diff / v
        sigma = max(0.01, min(sigma, 5.0))  # clamp

    return sigma


def delta(S: float, K: float, T: float, r: float, sigma: float, option_type: str = "CE") -> float:
    if T <= 0 or sigma <= 0:
        if option_type == "CE":
            return 1.0 if S > K else 0.0
        return -1.0 if S < K else 0.0
    d1 = _d1(S, K, T, r, sigma)
    if option_type == "CE":
        return float(norm.cdf(d1))
    return float(norm.cdf(d1) - 1)


def gamma(S: float, K: float, T: float, r: float, sigma: float) -> float:
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma)
    return float(norm.pdf(d1) / (S * sigma * math.sqrt(T)))


def theta(S: float, K: float, T: float, r: float, sigma: float, option_type: str = "CE") -> float:
    """Theta per calendar day (divide by 365)."""
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma)
    d2 = _d2(S, K, T, r, sigma)
    term1 = -(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T))
    if option_type == "CE":
        term2 = -r * K * math.exp(-r * T) * norm.cdf(d2)
    else:
        term2 = r * K * math.exp(-r * T) * norm.cdf(-d2)
    return float((term1 + term2) / 365)


def vega(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Vega per 1% move in volatility."""
    if T <= 0 or sigma <= 0:
        return 0.0
    d1 = _d1(S, K, T, r, sigma)
    return float(S * math.sqrt(T) * norm.pdf(d1) / 100)


def calculate_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str = "CE",
) -> Greeks:
    """Calculate all Greeks for an option."""
    return Greeks(
        delta=round(delta(S, K, T, r, sigma, option_type), 4),
        gamma=round(gamma(S, K, T, r, sigma), 6),
        theta=round(theta(S, K, T, r, sigma, option_type), 4),
        vega=round(vega(S, K, T, r, sigma), 4),
        iv=round(sigma * 100, 2),
    )
