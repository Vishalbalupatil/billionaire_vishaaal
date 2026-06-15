"""Tests for options chain analysis."""

from ai_trader.options.chain import (
    build_chain_from_quotes,
    call_wall,
    max_pain,
    pcr_overall,
    put_wall,
)


def _sample_chain():
    strikes = [21800, 21850, 21900, 21950, 22000, 22050, 22100, 22150, 22200]
    spot = 22000
    ce_prices = {s: max(10, 400 - (s - 21800) * 2.5) for s in strikes}
    pe_prices = {s: max(10, 10 + (s - 21800) * 2.5) for s in strikes}
    ce_oi = {21800: 10000, 21900: 20000, 22000: 50000, 22100: 80000, 22200: 30000}
    pe_oi = {21800: 60000, 21900: 40000, 22000: 30000, 22100: 10000, 22200: 5000}

    return build_chain_from_quotes(
        spot=spot,
        strikes=strikes,
        expiry_str="2025-01-30",
        ce_prices=ce_prices,
        pe_prices=pe_prices,
        ce_oi=ce_oi,
        pe_oi=pe_oi,
    )


def test_build_chain():
    chain = _sample_chain()
    assert len(chain) == 9
    assert chain[0].strike == 21800


def test_max_pain():
    chain = _sample_chain()
    mp = max_pain(chain)
    assert 21800 <= mp <= 22200


def test_pcr_overall():
    chain = _sample_chain()
    pcr = pcr_overall(chain)
    assert pcr > 0


def test_call_wall():
    chain = _sample_chain()
    cw = call_wall(chain)
    assert cw == 22100  # highest call OI


def test_put_wall():
    chain = _sample_chain()
    pw = put_wall(chain)
    assert pw == 21800  # highest put OI
