"""Tests for Black-Scholes pricing and Greeks."""

import math

from ai_trader.options.greeks import (
    calculate_greeks,
    call_price,
    delta,
    gamma,
    implied_volatility,
    put_price,
    theta,
    vega,
)


def test_call_price_basic():
    # ATM call, 1 year, 15% vol, 7% rate
    price = call_price(S=22000, K=22000, T=1.0, r=0.07, sigma=0.15)
    assert price > 0
    assert 1000 < price < 5000  # reasonable range for Nifty ATM call


def test_put_price_basic():
    price = put_price(S=22000, K=22000, T=1.0, r=0.07, sigma=0.15)
    assert price > 0


def test_put_call_parity():
    S, K, T, r, sigma = 22000, 22000, 0.1, 0.07, 0.15
    c = call_price(S, K, T, r, sigma)
    p = put_price(S, K, T, r, sigma)
    # Put-call parity: C - P = S - K*e^(-rT)
    expected = S - K * math.exp(-r * T)
    assert abs((c - p) - expected) < 1.0


def test_delta_call_atm():
    d = delta(S=22000, K=22000, T=0.1, r=0.07, sigma=0.15, option_type="CE")
    assert 0.4 < d < 0.7  # ATM call delta ~0.5


def test_delta_put_atm():
    d = delta(S=22000, K=22000, T=0.1, r=0.07, sigma=0.15, option_type="PE")
    assert -0.7 < d < -0.4  # ATM put delta ~-0.5


def test_gamma_positive():
    g = gamma(S=22000, K=22000, T=0.1, r=0.07, sigma=0.15)
    assert g > 0


def test_theta_negative_for_long():
    t = theta(S=22000, K=22000, T=0.1, r=0.07, sigma=0.15, option_type="CE")
    assert t < 0  # time decay


def test_vega_positive():
    v = vega(S=22000, K=22000, T=0.1, r=0.07, sigma=0.15)
    assert v > 0


def test_implied_volatility():
    # Price a call, then recover IV
    true_sigma = 0.20
    price = call_price(S=22000, K=22000, T=0.1, r=0.07, sigma=true_sigma)
    recovered = implied_volatility(price, S=22000, K=22000, T=0.1, r=0.07, option_type="CE")
    assert abs(recovered - true_sigma) < 0.01


def test_calculate_greeks_returns_all():
    g = calculate_greeks(S=22000, K=22000, T=0.1, r=0.07, sigma=0.15, option_type="CE")
    assert g.delta != 0
    assert g.gamma > 0
    assert g.theta != 0
    assert g.vega > 0
    assert g.iv == 15.0


def test_expired_option():
    c = call_price(S=22100, K=22000, T=0, r=0.07, sigma=0.15)
    assert c == 100.0  # intrinsic value
    p = put_price(S=22100, K=22000, T=0, r=0.07, sigma=0.15)
    assert p == 0.0
