"""Tests for options strategy selection."""

from ai_trader.models.domain import MarketRegime, SignalDirection
from ai_trader.models.options import OptionStrategyType
from ai_trader.options.chain import build_chain_from_quotes
from ai_trader.options.strategies import select_strategy


def _chain(spot: float = 22000):
    strikes = list(range(21600, 22400, 50))
    ce_prices = {s: max(5, (spot - s + 200) * 0.6) for s in strikes}
    pe_prices = {s: max(5, (s - spot + 200) * 0.6) for s in strikes}
    return build_chain_from_quotes(
        spot=spot,
        strikes=strikes,
        expiry_str="2025-01-30",
        ce_prices=ce_prices,
        pe_prices=pe_prices,
    )


def test_bull_call_spread_on_trend_up():
    chain = _chain()
    strategy = select_strategy(
        spot=22000, chain=chain,
        regime=MarketRegime.TRENDING_UP,
        direction=SignalDirection.BULLISH,
        confidence=0.8, vix=16.0,
    )
    assert strategy is not None
    assert strategy.strategy_type == OptionStrategyType.BULL_CALL_SPREAD


def test_bear_put_spread_on_trend_down():
    chain = _chain()
    strategy = select_strategy(
        spot=22000, chain=chain,
        regime=MarketRegime.TRENDING_DOWN,
        direction=SignalDirection.BEARISH,
        confidence=0.8, vix=16.0,
    )
    assert strategy is not None
    assert strategy.strategy_type == OptionStrategyType.BEAR_PUT_SPREAD


def test_iron_condor_on_range():
    chain = _chain()
    strategy = select_strategy(
        spot=22000, chain=chain,
        regime=MarketRegime.RANGE_BOUND,
        direction=SignalDirection.NEUTRAL,
        confidence=0.5, vix=22.0,
    )
    assert strategy is not None
    assert strategy.strategy_type == OptionStrategyType.IRON_CONDOR


def test_short_straddle_on_volatile():
    chain = _chain()
    strategy = select_strategy(
        spot=22000, chain=chain,
        regime=MarketRegime.VOLATILE,
        direction=SignalDirection.NEUTRAL,
        confidence=0.5, vix=28.0,
    )
    assert strategy is not None
    assert strategy.strategy_type == OptionStrategyType.SHORT_STRADDLE


def test_strategy_has_legs():
    chain = _chain()
    strategy = select_strategy(
        spot=22000, chain=chain,
        regime=MarketRegime.TRENDING_UP,
        direction=SignalDirection.BULLISH,
        confidence=0.8,
    )
    assert strategy is not None
    assert len(strategy.legs) >= 2
    assert strategy.max_profit > 0
    assert strategy.payoff  # payoff computed


def test_long_straddle_quiet_low_iv():
    chain = _chain()
    strategy = select_strategy(
        spot=22000, chain=chain,
        regime=MarketRegime.QUIET,
        direction=SignalDirection.NEUTRAL,
        confidence=0.5, vix=12.0,
    )
    assert strategy is not None
    assert strategy.strategy_type == OptionStrategyType.LONG_STRADDLE
